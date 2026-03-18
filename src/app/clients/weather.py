import datetime
import logging
from itertools import groupby

from app.clients.base import BaseHttpClient
from app.exceptions import WeatherApiError
from app.models.weather import CurrentWeather, DailyWeather, WeatherForecast
from app.utils.dt import MSK, now

logger = logging.getLogger(__name__)

OWM_BASE_URL = "https://api.openweathermap.org/data/2.5"


class WeatherClient(BaseHttpClient):
    """Client for OpenWeatherMap API 2.5 (free plan)."""

    def __init__(self, api_key: str, lat: float, lon: float, **kwargs: object) -> None:
        super().__init__(base_url=OWM_BASE_URL, **kwargs)
        self._api_key = api_key
        self._lat = lat
        self._lon = lon

    def _base_params(self) -> dict:
        return {
            "appid": self._api_key,
            "lat": str(self._lat),
            "lon": str(self._lon),
            "units": "metric",
            "lang": "ru",
        }

    async def get_current(self) -> CurrentWeather:
        response = await self._request("GET", "/weather", params=self._base_params())
        if response.status_code != 200:
            raise WeatherApiError(
                f"Weather API error: {response.text}",
                status_code=response.status_code,
            )
        data = response.json()
        weather_info = data.get("weather", [{}])[0]
        rain = data.get("rain", {}).get("1h", 0.0)
        snow = data.get("snow", {}).get("1h", 0.0)

        return CurrentWeather(
            dt=datetime.datetime.fromtimestamp(data["dt"], tz=MSK),
            temp=data["main"]["temp"],
            feels_like=data["main"]["feels_like"],
            humidity=data["main"]["humidity"],
            pressure=data["main"]["pressure"],
            weather_main=weather_info.get("main", "Unknown"),
            weather_description=weather_info.get("description", ""),
            wind_speed=data.get("wind", {}).get("speed", 0.0),
            precipitation=rain + snow,
        )

    async def get_forecast_5day(self) -> WeatherForecast:
        response = await self._request("GET", "/forecast", params=self._base_params())
        if response.status_code != 200:
            raise WeatherApiError(
                f"Weather forecast API error: {response.text}",
                status_code=response.status_code,
            )
        data = response.json()
        items = data.get("list", [])

        daily: list[DailyWeather] = []
        for date_str, group in groupby(items, key=lambda x: x["dt_txt"][:10]):
            entries = list(group)
            temps = [e["main"]["temp"] for e in entries]
            precip = sum(
                e.get("rain", {}).get("3h", 0.0) + e.get("snow", {}).get("3h", 0.0)
                for e in entries
            )
            humidities = [e["main"]["humidity"] for e in entries]
            winds = [e.get("wind", {}).get("speed", 0.0) for e in entries]
            weather_mains = [e["weather"][0]["main"] for e in entries if e.get("weather")]
            most_common_weather = max(set(weather_mains), key=weather_mains.count) if weather_mains else "Unknown"

            daily.append(DailyWeather(
                date=datetime.date.fromisoformat(date_str),
                temp_min=min(temps),
                temp_max=max(temps),
                temp_avg=sum(temps) / len(temps),
                precipitation=precip,
                weather_main=most_common_weather,
                humidity=round(sum(humidities) / len(humidities)),
                wind_speed=round(sum(winds) / len(winds), 1),
            ))

        return WeatherForecast(fetched_at=now(), daily=daily)
