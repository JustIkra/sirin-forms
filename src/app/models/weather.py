import datetime

from pydantic import BaseModel


class DailyWeather(BaseModel):
    date: datetime.date
    temp_min: float
    temp_max: float
    temp_avg: float
    precipitation: float
    weather_main: str
    weather_description: str | None = None
    humidity: int | None = None
    wind_speed: float | None = None


class CurrentWeather(BaseModel):
    dt: datetime.datetime
    temp: float
    feels_like: float
    humidity: int
    pressure: int
    weather_main: str
    weather_description: str
    wind_speed: float
    precipitation: float = 0.0


class WeatherForecast(BaseModel):
    fetched_at: datetime.datetime
    daily: list[DailyWeather]
