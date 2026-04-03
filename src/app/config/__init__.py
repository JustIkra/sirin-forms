from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # iiko Server API
    iiko_server_url: str
    iiko_login: str
    iiko_password: str

    # OpenRouter (LLM)
    openrouter_api_key: SecretStr
    openrouter_model: str = "google/gemini-3-flash-preview"

    # Weather (Open-Meteo, no key needed)
    restaurant_lat: float
    restaurant_lon: float

    # Forecasting parameters
    procurement_buffer_pct: float = 0.10
    forecast_horizon_days: int = 30
    history_months: int = 24

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/gurman"
