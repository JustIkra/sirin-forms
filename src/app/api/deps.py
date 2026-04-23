from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.iiko import IikoClient
from app.clients.openrouter import OpenRouterClient
from app.clients.weather import WeatherClient
from app.repositories.forecasts import ForecastsRepository
from app.repositories.menu_snapshots import MenuSnapshotsRepository
from app.repositories.ml_models import MLModelsRepository
from app.repositories.products import ProductsRepository
from app.repositories.sales import SalesRepository
from app.config import Settings
from app.repositories.weather import WeatherRepository


async def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        async with session.begin():
            yield session


async def get_iiko_client(request: Request) -> IikoClient:
    return request.app.state.iiko_client


async def get_openrouter_client(request: Request) -> OpenRouterClient:
    return request.app.state.openrouter_client


async def get_weather_client(request: Request) -> WeatherClient:
    return request.app.state.weather_client


async def get_weather_repo(
    session: AsyncSession = Depends(get_db_session),
) -> WeatherRepository:
    return WeatherRepository(session)


async def get_sales_repo(
    session: AsyncSession = Depends(get_db_session),
) -> SalesRepository:
    return SalesRepository(session)


async def get_products_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ProductsRepository:
    return ProductsRepository(session)


async def get_forecasts_repo(
    session: AsyncSession = Depends(get_db_session),
) -> ForecastsRepository:
    return ForecastsRepository(session)


async def get_ml_models_repo(
    session: AsyncSession = Depends(get_db_session),
) -> MLModelsRepository:
    return MLModelsRepository(session)


async def get_menu_snapshots_repo(
    session: AsyncSession = Depends(get_db_session),
) -> MenuSnapshotsRepository:
    return MenuSnapshotsRepository(session)
