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
from app.db import Base, create_engine, create_session_factory

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings()

    # Database
    engine = create_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
        api_key=settings.owm_api_key.get_secret_value(),
        lat=settings.restaurant_lat,
        lon=settings.restaurant_lon,
    )
    await weather.__aenter__()
    app.state.weather_client = weather

    logger.info("Application started")

    yield

    # Shutdown
    await weather.__aexit__(None, None, None)
    await iiko.__aexit__(None, None, None)
    await openrouter.close()
    await engine.dispose()
    logger.info("Application stopped")


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
