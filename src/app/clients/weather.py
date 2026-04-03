import datetime
import logging

from app.clients.base import BaseHttpClient
from app.exceptions import WeatherApiError
from app.models.weather import DailyWeather
from app.utils.dt import now

logger = logging.getLogger(__name__)

OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1"

_DAILY_FIELDS = ",".join([
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "weathercode",
    "windspeed_10m_max",
    "relative_humidity_2m_mean",
])

# WMO weather codes → human-readable main category
_WMO_CODES: dict[int, str] = {
    0: "Clear",
    1: "Clouds", 2: "Clouds", 3: "Clouds",
    45: "Fog", 48: "Fog",
    51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    56: "Drizzle", 57: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Rain",
    66: "Rain", 67: "Rain",
    71: "Snow", 73: "Snow", 75: "Snow",
    77: "Snow",
    80: "Rain", 81: "Rain", 82: "Rain",
    85: "Snow", 86: "Snow",
    95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
}

_MAX_PAST_DAYS = 92


class WeatherClient(BaseHttpClient):
    """Client for Open-Meteo API (free, no API key required)."""

    def __init__(self, lat: float, lon: float, **kwargs: object) -> None:
        super().__init__(base_url=OPEN_METEO_BASE_URL, **kwargs)
        self._lat = lat
        self._lon = lon

    async def get_weather(self, target_date: datetime.date) -> DailyWeather | None:
        """Fetch weather for a specific date (past up to 92 days or future up to 16)."""
        today = now().date()
        delta = (target_date - today).days

        if delta > 16 or delta < -_MAX_PAST_DAYS:
            return None

        past_days = max(0, -delta + 1)
        forecast_days = max(1, delta + 1)
        daily = await self._fetch(past_days, forecast_days)

        for day in daily:
            if day.date == target_date:
                return day
        return None

    async def get_range(
        self, date_from: datetime.date, date_to: datetime.date,
    ) -> list[DailyWeather]:
        """Fetch weather for a date range (up to 92 past days per chunk)."""
        today = now().date()
        all_days: list[DailyWeather] = []
        seen_dates: set[datetime.date] = set()

        # Split into chunks of max 92 past_days
        chunk_end = date_to
        while chunk_end >= date_from:
            delta_end = (chunk_end - today).days
            delta_from = (date_from - today).days
            chunk_past = min(_MAX_PAST_DAYS, max(0, -delta_from))
            chunk_start = today - datetime.timedelta(days=chunk_past)
            if chunk_start < date_from:
                chunk_start = date_from

            past_days = max(0, (today - chunk_start).days)
            forecast_days = max(1, delta_end + 1) if delta_end >= 0 else 1

            if past_days > _MAX_PAST_DAYS:
                # Can't go further back with forecast endpoint
                break

            days = await self._fetch(past_days, forecast_days)
            for d in days:
                if date_from <= d.date <= date_to and d.date not in seen_dates:
                    all_days.append(d)
                    seen_dates.add(d.date)

            # Move to next chunk
            chunk_end = chunk_start - datetime.timedelta(days=1)

        all_days.sort(key=lambda d: d.date)
        return all_days

    async def _fetch(self, past_days: int, forecast_days: int) -> list[DailyWeather]:
        params = {
            "latitude": str(self._lat),
            "longitude": str(self._lon),
            "daily": _DAILY_FIELDS,
            "timezone": "Europe/Moscow",
            "past_days": str(min(past_days, _MAX_PAST_DAYS)),
            "forecast_days": str(min(forecast_days, 16)),
        }
        response = await self._request("GET", "/forecast", params=params)
        if response.status_code != 200:
            raise WeatherApiError(
                f"Open-Meteo API error: {response.text}",
                status_code=response.status_code,
            )
        return self._parse_daily(response.json())

    @staticmethod
    def _parse_daily(data: dict) -> list[DailyWeather]:
        daily_data = data.get("daily", {})
        dates = daily_data.get("time", [])
        temp_maxs = daily_data.get("temperature_2m_max", [])
        temp_mins = daily_data.get("temperature_2m_min", [])
        precips = daily_data.get("precipitation_sum", [])
        codes = daily_data.get("weathercode", [])
        winds = daily_data.get("windspeed_10m_max", [])
        humidities = daily_data.get("relative_humidity_2m_mean", [])

        result: list[DailyWeather] = []
        for i, date_str in enumerate(dates):
            temp_min = temp_mins[i] if i < len(temp_mins) else None
            temp_max = temp_maxs[i] if i < len(temp_maxs) else None
            if temp_min is None or temp_max is None:
                continue
            code = codes[i] if i < len(codes) and codes[i] is not None else 0
            precip = precips[i] if i < len(precips) and precips[i] is not None else 0.0
            humidity = humidities[i] if i < len(humidities) and humidities[i] is not None else None
            wind = winds[i] if i < len(winds) and winds[i] is not None else None
            result.append(DailyWeather(
                date=datetime.date.fromisoformat(date_str),
                temp_min=temp_min,
                temp_max=temp_max,
                temp_avg=round((temp_min + temp_max) / 2, 1),
                precipitation=precip,
                weather_main=_WMO_CODES.get(code, "Unknown"),
                humidity=round(humidity) if humidity is not None else None,
                wind_speed=round(wind / 3.6, 1) if wind is not None else None,
            ))
        return result
