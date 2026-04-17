import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.forecast import router as forecast_router
from app.api.health import router as health_router
from app.clients.iiko import IikoClient
from app.clients.openrouter import OpenRouterClient
from app.clients.weather import WeatherClient
from app.config import Settings
from sqlalchemy import text

from app.db import Base, WeatherRecord, create_engine, create_session_factory
from app.utils.dt import today as today_msk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()

    # Database
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate: add new columns if missing
        await conn.execute(text(
            "ALTER TABLE products ADD COLUMN IF NOT EXISTS"
            " included_in_menu BOOLEAN DEFAULT FALSE"
        ))
        await conn.execute(text(
            "ALTER TABLE forecasts ADD COLUMN IF NOT EXISTS"
            " price FLOAT"
        ))
        await conn.execute(text(
            "ALTER TABLE forecasts ADD COLUMN IF NOT EXISTS"
            " method VARCHAR(10) DEFAULT 'ml'"
        ))
        await conn.execute(text(
            "ALTER TABLE forecasts ALTER COLUMN method SET DEFAULT 'ml'"
        ))
    app.state.session_factory = create_session_factory(engine)
    app.state.settings = settings

    # Clients
    iiko = IikoClient(
        server_url=settings.iiko_server_url,
        login=settings.iiko_login,
        password=settings.iiko_password,
    )
    await iiko.__aenter__()
    app.state.iiko_client = iiko

    openrouter = OpenRouterClient(
        api_key=settings.openrouter_api_key.get_secret_value(),
        model=settings.openrouter_model,
    )
    app.state.openrouter_client = openrouter

    weather = WeatherClient(
        lat=settings.restaurant_lat,
        lon=settings.restaurant_lon,
        timeout=60.0,
    )
    await weather.__aenter__()
    app.state.weather_client = weather

    logger.info("Application started")

    # Backfill sales, weather, train models in background
    asyncio.create_task(_startup_backfill(iiko, weather, app.state.session_factory, settings))

    yield

    # Shutdown
    await weather.__aexit__(None, None, None)
    await iiko.__aexit__(None, None, None)
    await openrouter.close()
    await engine.dispose()
    logger.info("Application stopped")


async def _startup_backfill(
    iiko_client: IikoClient,
    weather_client: WeatherClient,
    session_factory,
    settings: Settings,
) -> None:
    """On startup: backfill sales, weather, and train ML models if needed."""
    from sqlalchemy import func, select
    from app.db import SaleRecordDb, MLModelRecord
    from app.repositories.sales import SalesRepository
    from app.repositories.weather import WeatherRepository
    from app.services.backfill import BackfillService
    from app.services.data_collector import DataCollector

    today = today_msk()

    # 1. Sales backfill — if empty or stale
    try:
        async with session_factory() as session:
            sales_count = await session.scalar(select(func.count()).select_from(SaleRecordDb))
            max_date = await session.scalar(select(func.max(SaleRecordDb.date)))

        stale = max_date and (today - max_date).days > 1
        if not sales_count or sales_count < 1000 or stale:
            logger.info("Sales backfill: %d records, max_date=%s — backfilling...", sales_count or 0, max_date)
            async with session_factory() as session:
                repo = SalesRepository(session)
                service = BackfillService(
                    iiko_client=iiko_client,
                    sales_repo=repo,
                    department_id=settings.iiko_department_id,
                )
                result = await service.backfill(
                    date_from=datetime.date(2015, 1, 1),
                    date_to=today,
                )
                await session.commit()
                logger.info("Sales backfill done: %s", result)
        else:
            logger.info("Sales backfill: %d records up to %s, OK", sales_count, max_date)
    except Exception:
        logger.warning("Sales backfill failed", exc_info=True)

    # 2. Weather backfill — if not enough
    try:
        async with session_factory() as session:
            weather_count = await session.scalar(select(func.count()).select_from(WeatherRecord))

        if not weather_count or weather_count < 3000:
            logger.info("Weather backfill: %d records — fetching archive...", weather_count or 0)
            days = await weather_client.get_historical_range(
                datetime.date(2015, 5, 1), today,
            )
            async with session_factory() as session:
                repo = WeatherRepository(session)
                for day in days:
                    await repo.save_daily_weather(day)
                await session.commit()
            logger.info("Weather backfill: saved %d days", len(days))
        else:
            logger.info("Weather backfill: %d records, OK", weather_count)
    except Exception:
        logger.warning("Weather backfill failed", exc_info=True)

    # 3. ML models — train if empty
    try:
        async with session_factory() as session:
            models_count = await session.scalar(select(func.count()).select_from(MLModelRecord))

        if not models_count or models_count == 0:
            logger.info("ML models: none found — training...")
            from app.repositories.forecasts import ForecastsRepository
            from app.repositories.ml_models import MLModelsRepository
            from app.repositories.products import ProductsRepository
            from app.services.ml_forecast import MLForecastService

            async with session_factory() as session:
                collector = DataCollector(
                    iiko_client=iiko_client,
                    weather_client=weather_client,
                    sales_repo=SalesRepository(session),
                    products_repo=ProductsRepository(session),
                    weather_repo=WeatherRepository(session),
                    settings=settings,
                )
                service = MLForecastService(
                    data_collector=collector,
                    forecasts_repo=ForecastsRepository(session),
                    ml_models_repo=MLModelsRepository(session),
                    sales_repo=SalesRepository(session),
                    weather_repo=WeatherRepository(session),
                    settings=settings,
                )
                result = await service.train_models(force=True)
                await session.commit()
                logger.info("ML training done: %s", result)
        else:
            logger.info("ML models: %d exist, OK", models_count)
    except Exception:
        logger.warning("ML training failed", exc_info=True)


app = FastAPI(
    title="Gurman Analytics",
    description="Restaurant demand forecasting API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(forecast_router)
