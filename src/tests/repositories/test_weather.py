import datetime

import pytest

from app.models.weather import DailyWeather
from app.repositories.weather import WeatherRepository


def _make_weather(date: datetime.date, temp: float = 5.0) -> DailyWeather:
    return DailyWeather(
        date=date,
        temp_min=temp - 2,
        temp_max=temp + 2,
        temp_avg=temp,
        precipitation=0.0,
        weather_main="Clear",
    )


async def test_save_and_get_latest(session):
    repo = WeatherRepository(session)

    w1 = _make_weather(datetime.date(2026, 3, 17))
    w2 = _make_weather(datetime.date(2026, 3, 18), temp=8.0)

    await repo.save_daily_weather(w1)
    await repo.save_daily_weather(w2)

    latest = await repo.get_latest()
    assert latest is not None
    assert latest.date == datetime.date(2026, 3, 18)
    assert latest.temp_avg == 8.0


async def test_save_upsert(session):
    repo = WeatherRepository(session)

    date = datetime.date(2026, 3, 18)
    w1 = _make_weather(date, temp=5.0)
    await repo.save_daily_weather(w1)

    w2 = _make_weather(date, temp=10.0)
    await repo.save_daily_weather(w2)

    latest = await repo.get_latest()
    assert latest is not None
    assert latest.temp_avg == 10.0


async def test_get_weather_range(session):
    repo = WeatherRepository(session)

    for day in range(15, 21):
        await repo.save_daily_weather(
            _make_weather(datetime.date(2026, 3, day), temp=float(day)),
        )

    result = await repo.get_weather_range(
        datetime.date(2026, 3, 16),
        datetime.date(2026, 3, 19),
    )
    assert len(result) == 4
    assert result[0].date == datetime.date(2026, 3, 16)
    assert result[-1].date == datetime.date(2026, 3, 19)


async def test_get_latest_empty(session):
    repo = WeatherRepository(session)
    latest = await repo.get_latest()
    assert latest is None
