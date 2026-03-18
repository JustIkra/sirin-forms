class GurmanError(Exception):
    """Base exception for Gurman Analytics."""


class ApiClientError(GurmanError):
    """Base exception for API client errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class IikoAuthError(ApiClientError):
    """Failed to authenticate with iiko server."""


class IikoApiError(ApiClientError):
    """iiko API returned an error."""


class TokenExpiredError(IikoApiError):
    """iiko session token has expired."""


class OpenRouterApiError(ApiClientError):
    """OpenRouter API returned an error."""


class WeatherApiError(ApiClientError):
    """OpenWeatherMap API returned an error."""


class ForecastError(GurmanError):
    """Error during forecast generation."""
