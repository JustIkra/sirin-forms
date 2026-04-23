from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate legacy keys in .env (e.g. removed MIN_SALES_PCT)
    )

    # iiko Server API
    iiko_server_url: str
    iiko_login: str
    iiko_password: str
    iiko_department_id: str | None = None

    # OpenRouter (LLM)
    openrouter_api_key: SecretStr
    openrouter_model: str = "google/gemini-3-flash-preview"

    # Weather (Open-Meteo, no key needed)
    restaurant_lat: float
    restaurant_lon: float

    # Forecasting — shared
    procurement_buffer_pct: float = 0.10
    forecast_horizon_days: int = 30
    history_months: int = 24

    # Weekly forecaster thresholds (Domain 2)
    weekly_max_history_months: int = 36
    weekly_min_samples: int = 4
    weekly_min_sales_pct: float = 0.05
    weekly_min_accuracy: float = 0.0

    # Daily forecaster thresholds (Domain 2)
    daily_max_history_months: int = 12
    daily_min_samples: int = 90
    daily_min_sales_pct: float = 0.05
    daily_min_accuracy: float = 10.0

    # Daily retraining scheduler
    auto_retrain_enabled: bool = True
    auto_retrain_hour_msk: int = 4  # час в MSK, когда переобучать (0-23)

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/gurman"
