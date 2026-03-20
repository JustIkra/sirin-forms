import datetime
import logging

from app.clients.iiko import IikoClient
from app.clients.weather import WeatherClient
from app.config import Settings
from app.exceptions import ApiClientError
from app.models.iiko import (
    IikoProduct,
    OlapReportType,
    OlapV2Request,
    ProductType,
    SaleRecord,
)
from app.models.weather import DailyWeather
from app.repositories.products import ProductsRepository
from app.repositories.sales import SalesRepository
from app.repositories.weather import WeatherRepository

logger = logging.getLogger(__name__)


class DataCollector:

    def __init__(
        self,
        iiko_client: IikoClient,
        weather_client: WeatherClient,
        sales_repo: SalesRepository,
        products_repo: ProductsRepository,
        weather_repo: WeatherRepository,
        settings: Settings,
    ) -> None:
        self._iiko = iiko_client
        self._weather = weather_client
        self._sales_repo = sales_repo
        self._products_repo = products_repo
        self._weather_repo = weather_repo
        self._history_months = settings.history_months

    async def collect_products(self) -> list[IikoProduct]:
        products = await self._iiko.get_products()
        await self._products_repo.sync_products(products)
        return [p for p in products if p.product_type == ProductType.DISH]

    async def collect_historical_sales(
        self,
        target_date: datetime.date,
    ) -> list[SaleRecord]:
        ranges = self._build_historical_ranges(target_date, self._history_months)
        all_sales: list[SaleRecord] = []

        for date_from, date_to in ranges:
            try:
                report = await self._iiko.get_olap_report_v2(
                    OlapV2Request(
                        report_type=OlapReportType.SALES,
                        date_from=date_from,
                        date_to=date_to,
                        group_by_row_fields=["DishName", "DishId", "OpenDate.Typed"],
                        aggregate_fields=["DishAmountInt", "DishSumInt"],
                        filters={"OpenDate.Typed": {
                            "filterType": "DateRange",
                            "periodType": "CUSTOM",
                            "from": date_from.isoformat(),
                            "to": date_to.isoformat(),
                            "includeLow": True,
                            "includeHigh": True,
                        }},
                    ),
                )
                sales = self._parse_olap_sales(report.data)
                logger.info(
                    "OLAP %s–%s: %d rows, %d sales parsed",
                    date_from, date_to, len(report.data), len(sales),
                )
                if sales:
                    await self._sales_repo.bulk_upsert_sales(sales)
                all_sales.extend(sales)
            except Exception as exc:
                logger.warning(
                    "iiko OLAP failed for %s — %s: %s",
                    date_from, date_to, exc, exc_info=True,
                )
                cached = await self._sales_repo.get_sales_by_period(date_from, date_to)
                all_sales.extend(cached)

        logger.info("Historical: %d records from %d ranges", len(all_sales), len(ranges))
        return all_sales

    async def collect_recent_sales(
        self,
        target_date: datetime.date,
        days_back: int = 30,
    ) -> list[SaleRecord]:
        date_from = target_date - datetime.timedelta(days=days_back)
        date_to = target_date - datetime.timedelta(days=1)

        try:
            report = await self._iiko.get_olap_report_v2(
                OlapV2Request(
                    report_type=OlapReportType.SALES,
                    date_from=date_from,
                    date_to=date_to,
                    group_by_row_fields=["DishName", "DishId", "OpenDate.Typed"],
                    aggregate_fields=["DishAmountInt", "DishSumInt"],
                    filters={"OpenDate.Typed": {
                        "filterType": "DateRange",
                        "periodType": "CUSTOM",
                        "from": date_from.isoformat(),
                        "to": date_to.isoformat(),
                        "includeLow": True,
                        "includeHigh": True,
                    }},
                ),
            )
            sales = self._parse_olap_sales(report.data)
            logger.info(
                "Recent: %d records for %s–%s",
                len(sales), date_from, date_to,
            )
            if sales:
                await self._sales_repo.bulk_upsert_sales(sales)
            return sales
        except Exception as exc:
            logger.warning(
                "iiko OLAP failed for recent sales %s–%s: %s",
                date_from, date_to, exc, exc_info=True,
            )
            return await self._sales_repo.get_sales_by_period(date_from, date_to)

    async def collect_weather(
        self,
        target_date: datetime.date,
    ) -> DailyWeather | None:
        # Check DB cache first
        cached = await self._weather_repo.get_weather_range(target_date, target_date)
        if cached:
            return cached[0]

        # Fetch from API and save all days
        try:
            forecast = await self._weather.get_forecast_5day()
            for day in forecast.daily:
                await self._weather_repo.save_daily_weather(day)
        except ApiClientError:
            logger.warning("Weather API unavailable", exc_info=True)
            return None

        # Find the target date
        for day in forecast.daily:
            if day.date == target_date:
                return day

        return None

    @staticmethod
    def _build_historical_ranges(
        target_date: datetime.date,
        history_months: int,
    ) -> list[tuple[datetime.date, datetime.date]]:
        years_back = max(1, history_months // 12)
        ranges: list[tuple[datetime.date, datetime.date]] = []
        for year_offset in range(1, years_back + 1):
            center = target_date.replace(year=target_date.year - year_offset)
            date_from = center - datetime.timedelta(days=7)
            date_to = center + datetime.timedelta(days=7)
            ranges.append((date_from, date_to))
        return ranges

    @staticmethod
    def _parse_olap_sales(data: list[dict]) -> list[SaleRecord]:
        sales: list[SaleRecord] = []
        for row in data:
            try:
                date_raw = row.get("OpenDate.Typed") or row.get("OpenDate")
                if not date_raw:
                    continue
                sales.append(SaleRecord(
                    date=datetime.date.fromisoformat(str(date_raw)[:10]),
                    dish_id=row.get("DishId", ""),
                    dish_name=row.get("DishName", ""),
                    quantity=float(row.get("DishAmountInt", 0)),
                    price=0.0,
                    total=float(row.get("DishSumInt", 0)),
                ))
            except (ValueError, TypeError):
                logger.warning("Failed to parse OLAP row: %s", row, exc_info=True)
        return sales
