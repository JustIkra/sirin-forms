import datetime
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session,
    get_forecasts_repo,
    get_iiko_client,
    get_ml_models_repo,
    get_openrouter_client,
    get_products_repo,
    get_sales_repo,
    get_settings,
    get_weather_client,
    get_weather_repo,
)
from app.clients.iiko import IikoClient
from app.clients.openrouter import OpenRouterClient
from app.clients.weather import WeatherClient
from app.config import Settings
from app.exceptions import ApiClientError, ForecastError
from app.models.forecast import (
    AccuracyDayRecord,
    AccuracyHistoryResponse,
    AccuracyHistorySummary,
    DailyForecastResult,
    DishTrend,
    MethodAccuracy,
    PlanFactResponse,
    PlanFactSummary,
)
from app.models.iiko import OlapReportType, OlapV2Request
from app.repositories.forecasts import ForecastsRepository
from app.repositories.ml_models import MLModelsRepository
from app.repositories.products import ProductsRepository
from app.repositories.sales import SalesRepository
from app.repositories.weather import WeatherRepository
from app.services.backfill import BackfillService
from app.services.data_collector import DataCollector
from app.services.forecast import ForecastService
from app.services.ml_forecast import MLForecastService
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["forecast"])


class ForecastRequest(BaseModel):
    date: datetime.date
    force: bool = False
    method: str = "llm"


@router.post("/forecast", response_model=DailyForecastResult)
async def create_forecast(
    body: ForecastRequest,
    iiko_client: IikoClient = Depends(get_iiko_client),
    weather_client: WeatherClient = Depends(get_weather_client),
    openrouter_client: OpenRouterClient = Depends(get_openrouter_client),
    sales_repo: SalesRepository = Depends(get_sales_repo),
    products_repo: ProductsRepository = Depends(get_products_repo),
    weather_repo: WeatherRepository = Depends(get_weather_repo),
    forecasts_repo: ForecastsRepository = Depends(get_forecasts_repo),
    ml_models_repo: MLModelsRepository = Depends(get_ml_models_repo),
    settings: Settings = Depends(get_settings),
) -> DailyForecastResult:
    collector = DataCollector(
        iiko_client=iiko_client,
        weather_client=weather_client,
        sales_repo=sales_repo,
        products_repo=products_repo,
        weather_repo=weather_repo,
        settings=settings,
    )

    try:
        if body.method == "ml":
            service = MLForecastService(
                data_collector=collector,
                forecasts_repo=forecasts_repo,
                ml_models_repo=ml_models_repo,
                sales_repo=sales_repo,
                weather_repo=weather_repo,
                settings=settings,
            )
        else:
            service = ForecastService(
                data_collector=collector,
                prompt_builder=PromptBuilder(),
                openrouter_client=openrouter_client,
                forecasts_repo=forecasts_repo,
                settings=settings,
            )
        return await service.generate_forecast(body.date, force=body.force)
    except ForecastError as exc:
        logger.error("Forecast error: %s", exc)
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    except ApiClientError as exc:
        logger.error("API client error: %s", exc)
        return JSONResponse(status_code=502, content={"detail": str(exc)})


def _quality_rating(mape: float) -> str:
    if mape < 10:
        return "Отлично"
    if mape < 20:
        return "Хорошо"
    if mape < 30:
        return "Удовлетворительно"
    return "Плохо"


@router.get("/plan-fact", response_model=PlanFactResponse)
async def get_plan_fact(
    date: datetime.date = Query(...),
    method: str = Query("llm"),
    iiko_client: IikoClient = Depends(get_iiko_client),
    sales_repo: SalesRepository = Depends(get_sales_repo),
    forecasts_repo: ForecastsRepository = Depends(get_forecasts_repo),
    settings: Settings = Depends(get_settings),
) -> PlanFactResponse | JSONResponse:
    today = datetime.date.today()
    if date > today:
        return JSONResponse(
            status_code=422,
            content={"detail": "Дата в будущем — фактических данных нет"},
        )

    forecast = await forecasts_repo.get_forecast(date, method=method)
    if not forecast:
        return JSONResponse(
            status_code=404,
            content={"detail": "Прогноз на эту дату не найден"},
        )

    # Fetch actual sales from iiko, fallback to DB cache
    try:
        report = await iiko_client.get_olap_report_v2(
            OlapV2Request(
                report_type=OlapReportType.SALES,
                date_from=date,
                date_to=date,
                group_by_row_fields=["DishName", "DishId", "OpenDate.Typed"],
                aggregate_fields=["DishAmountInt", "DishSumInt"],
                filters={"OpenDate.Typed": {
                    "filterType": "DateRange",
                    "periodType": "CUSTOM",
                    "from": date.isoformat(),
                    "to": date.isoformat(),
                    "includeLow": True,
                    "includeHigh": True,
                }},
            ),
        )
        sales = DataCollector._parse_olap_sales(report.data)
        if sales:
            await sales_repo.bulk_upsert_sales(sales)
    except Exception:
        logger.warning("iiko unavailable for plan-fact %s, using DB cache", date, exc_info=True)
        sales = await sales_repo.get_sales_by_period(date, date)

    actual_sales = [
        {"date": s.date, "dish_id": s.dish_id, "dish_name": s.dish_name, "quantity": s.quantity}
        for s in sales
    ]
    records = await forecasts_repo.get_plan_fact(date, date, actual_sales, method=method)

    # Calculate MAPE using max(actual, predicted) as denominator
    deviations = [
        abs(r.actual_quantity - r.predicted_quantity) / max(r.actual_quantity, r.predicted_quantity)
        for r in records
        if r.actual_quantity > 0
    ]
    mape = (sum(deviations) / len(deviations) * 100) if deviations else 0.0
    accuracy = max(0.0, 100.0 - mape)

    total_predicted = sum(r.predicted_quantity for r in records)
    total_actual = sum(r.actual_quantity for r in records)

    summary = PlanFactSummary(
        total_predicted=round(total_predicted, 1),
        total_actual=round(total_actual, 1),
        mape=round(mape, 1),
        accuracy=round(accuracy, 1),
        quality_rating=_quality_rating(mape),
        dish_count=len(records),
    )

    return PlanFactResponse(date=date, records=records, summary=summary)


@router.get("/accuracy-history", response_model=AccuracyHistoryResponse)
async def get_accuracy_history(
    days: int = Query(30, ge=1, le=365),
    sales_repo: SalesRepository = Depends(get_sales_repo),
    forecasts_repo: ForecastsRepository = Depends(get_forecasts_repo),
):
    from app.utils.calendar import get_calendar_context

    today = datetime.date.today()
    date_from = today - datetime.timedelta(days=days)

    # Get all dates that have forecasts
    forecast_dates = await forecasts_repo.get_forecast_dates(date_from, today)
    dates_with_forecasts: dict[datetime.date, set[str]] = {}
    for d, method in forecast_dates:
        dates_with_forecasts.setdefault(d, set()).add(method)

    records: list[AccuracyDayRecord] = []
    for d, methods in sorted(dates_with_forecasts.items()):
        # Get actual sales for this date from DB
        sales = await sales_repo.get_sales_by_period(d, d)
        actual_sales = [
            {"date": s.date, "dish_id": s.dish_id, "dish_name": s.dish_name, "quantity": s.quantity}
            for s in sales
        ]
        actual_total = sum(s.quantity for s in sales)

        cal = get_calendar_context(d)
        ml_acc = None
        llm_acc = None

        for method in methods:
            pf_records = await forecasts_repo.get_plan_fact(d, d, actual_sales, method=method)
            deviations = [
                abs(r.actual_quantity - r.predicted_quantity) / max(r.actual_quantity, r.predicted_quantity)
                for r in pf_records if r.actual_quantity > 0
            ]
            mape = (sum(deviations) / len(deviations) * 100) if deviations else 0.0
            accuracy = max(0.0, 100.0 - mape)
            ma = MethodAccuracy(
                accuracy=round(accuracy, 1),
                mape=round(mape, 1),
                dish_count=len(pf_records),
            )
            if method == "ml":
                ml_acc = ma
            else:
                llm_acc = ma

        records.append(AccuracyDayRecord(
            date=d,
            weekday=cal["weekday"],
            is_holiday=cal["is_holiday"],
            holiday_name=cal.get("holiday_name"),
            ml=ml_acc,
            llm=llm_acc,
            actual_total=round(actual_total, 1),
        ))

    ml_accs = [r.ml.accuracy for r in records if r.ml]
    llm_accs = [r.llm.accuracy for r in records if r.llm]
    summary = AccuracyHistorySummary(
        ml_avg_accuracy=round(sum(ml_accs) / len(ml_accs), 1) if ml_accs else 0.0,
        llm_avg_accuracy=round(sum(llm_accs) / len(llm_accs), 1) if llm_accs else 0.0,
        days_count=len(records),
    )

    return AccuracyHistoryResponse(days=records, summary=summary)


@router.get("/trends")
async def get_trends(
    weeks: int = Query(12, ge=4, le=52),
    top_n: int = Query(20, ge=5, le=50),
    sales_repo: SalesRepository = Depends(get_sales_repo),
):
    from app.services.trend_analysis import TrendAnalyzer

    analyzer = TrendAnalyzer(sales_repo=sales_repo)
    trends = await analyzer.get_dish_trends(weeks=weeks, top_n=top_n)
    growing = [t for t in trends if t.trend_direction == "growing"]
    declining = [t for t in trends if t.trend_direction == "declining"]
    return {
        "weeks": weeks,
        "growing": [t.model_dump() for t in growing],
        "declining": [t.model_dump() for t in declining],
    }


class ProcurementRequest(BaseModel):
    date: datetime.date
    method: str = "ml"


@router.post("/procurement")
async def generate_procurement(
    body: ProcurementRequest,
    iiko_client: IikoClient = Depends(get_iiko_client),
    forecasts_repo: ForecastsRepository = Depends(get_forecasts_repo),
    sales_repo: SalesRepository = Depends(get_sales_repo),
    settings: Settings = Depends(get_settings),
):
    from app.services.procurement import ProcurementService

    service = ProcurementService(
        iiko_client=iiko_client,
        forecasts_repo=forecasts_repo,
        sales_repo=sales_repo,
        settings=settings,
    )
    try:
        result = await service.generate_list(body.date, method=body.method)
        return result
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    except Exception as exc:
        logger.error("Procurement error: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": str(exc)})


class BackfillRequest(BaseModel):
    date_from: datetime.date
    date_to: datetime.date


@router.post("/backfill")
async def run_backfill(
    body: BackfillRequest,
    iiko_client: IikoClient = Depends(get_iiko_client),
    sales_repo: SalesRepository = Depends(get_sales_repo),
):
    service = BackfillService(iiko_client=iiko_client, sales_repo=sales_repo)
    result = await service.backfill(body.date_from, body.date_to)
    return result


@router.post("/ml/train")
async def train_ml_models(
    iiko_client: IikoClient = Depends(get_iiko_client),
    weather_client: WeatherClient = Depends(get_weather_client),
    sales_repo: SalesRepository = Depends(get_sales_repo),
    products_repo: ProductsRepository = Depends(get_products_repo),
    weather_repo: WeatherRepository = Depends(get_weather_repo),
    forecasts_repo: ForecastsRepository = Depends(get_forecasts_repo),
    ml_models_repo: MLModelsRepository = Depends(get_ml_models_repo),
    settings: Settings = Depends(get_settings),
):
    collector = DataCollector(
        iiko_client=iiko_client,
        weather_client=weather_client,
        sales_repo=sales_repo,
        products_repo=products_repo,
        weather_repo=weather_repo,
        settings=settings,
    )
    service = MLForecastService(
        data_collector=collector,
        forecasts_repo=forecasts_repo,
        ml_models_repo=ml_models_repo,
        sales_repo=sales_repo,
        weather_repo=weather_repo,
        settings=settings,
    )
    result = await service.train_models(force=True)
    return result


@router.get("/export")
async def export_data(
    date: datetime.date = Query(...),
    method: str = Query("ml"),
    type: str = Query("forecast"),  # forecast | plan-fact
    format: str = Query("json"),    # json | csv | xlsx
    iiko_client: IikoClient = Depends(get_iiko_client),
    sales_repo: SalesRepository = Depends(get_sales_repo),
    forecasts_repo: ForecastsRepository = Depends(get_forecasts_repo),
):
    import csv
    import io

    # Get data based on type
    if type == "forecast":
        forecast = await forecasts_repo.get_forecast(date, method=method)
        if not forecast:
            return JSONResponse(status_code=404, content={"detail": "Прогноз не найден"})
        rows = [
            {"dish_name": d.dish_name, "predicted_quantity": d.predicted_quantity,
             "confidence": d.confidence, "key_factors": ", ".join(d.key_factors)}
            for d in forecast.forecasts
        ]
        columns = ["dish_name", "predicted_quantity", "confidence", "key_factors"]
    elif type == "plan-fact":
        forecast = await forecasts_repo.get_forecast(date, method=method)
        if not forecast:
            return JSONResponse(status_code=404, content={"detail": "Прогноз не найден"})
        sales = await sales_repo.get_sales_by_period(date, date)
        actual_sales = [
            {"date": s.date, "dish_id": s.dish_id, "dish_name": s.dish_name, "quantity": s.quantity}
            for s in sales
        ]
        records = await forecasts_repo.get_plan_fact(date, date, actual_sales, method=method)
        rows = [
            {"dish_name": r.dish_name, "predicted_quantity": r.predicted_quantity,
             "actual_quantity": r.actual_quantity, "deviation_pct": r.deviation_pct}
            for r in records
        ]
        columns = ["dish_name", "predicted_quantity", "actual_quantity", "deviation_pct"]
    else:
        return JSONResponse(status_code=400, content={"detail": f"Unknown type: {type}"})

    filename = f"{type}_{date}_{method}"

    if format == "json":
        return JSONResponse(
            content={"date": date.isoformat(), "method": method, "type": type, "data": rows},
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    if format == "xlsx":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = type
        ws.append(columns)
        for row in rows:
            ws.append([row.get(c, "") for c in columns])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    return JSONResponse(status_code=400, content={"detail": f"Unknown format: {format}"})
