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

    # Backfill weather data in background
    asyncio.create_task(_backfill_weather(weather, app.state.session_factory))

    yield

    # Shutdown
    await weather.__aexit__(None, None, None)
    await iiko.__aexit__(None, None, None)
    await openrouter.close()
    await engine.dispose()
    logger.info("Application stopped")


async def _backfill_weather(weather_client: WeatherClient, session_factory) -> None:
    """Fetch historical weather for the past year if missing."""
    from sqlalchemy import func, select
    from app.repositories.weather import WeatherRepository

    try:
        async with session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(WeatherRecord))
            if count and count >= 80:
                logger.info("Weather backfill: %d records exist, skipping", count)
                return

        today = datetime.date.today()
        date_from = today - datetime.timedelta(days=90)
        logger.info("Weather backfill: fetching %s — %s", date_from, today)

        days = await weather_client.get_range(date_from, today)
        logger.info("Weather backfill: got %d days from API", len(days))

        async with session_factory() as session:
            repo = WeatherRepository(session)
            for day in days:
                await repo.save_daily_weather(day)
            await session.commit()

        logger.info("Weather backfill: saved %d days", len(days))
    except Exception:
        logger.warning("Weather backfill failed", exc_info=True)


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
