import datetime
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db_session,
    get_forecasts_repo,
    get_iiko_client,
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
from app.models.forecast import DailyForecastResult
from app.repositories.forecasts import ForecastsRepository
from app.repositories.products import ProductsRepository
from app.repositories.sales import SalesRepository
from app.repositories.weather import WeatherRepository
from app.services.data_collector import DataCollector
from app.services.forecast import ForecastService
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["forecast"])


class ForecastRequest(BaseModel):
    date: datetime.date
    force: bool = False


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
    service = ForecastService(
        data_collector=collector,
        prompt_builder=PromptBuilder(),
        openrouter_client=openrouter_client,
        forecasts_repo=forecasts_repo,
        settings=settings,
    )

    try:
        return await service.generate_forecast(body.date, force=body.force)
    except ForecastError as exc:
        logger.error("Forecast error: %s", exc)
        return JSONResponse(status_code=422, content={"detail": str(exc)})
    except ApiClientError as exc:
        logger.error("API client error: %s", exc)
        return JSONResponse(status_code=502, content={"detail": str(exc)})
