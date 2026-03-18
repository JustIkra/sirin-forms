import pytest
import respx
from httpx import Response

from app.clients.weather import WeatherClient
from app.exceptions import WeatherApiError


@pytest.fixture
async def client():
    c = WeatherClient(
        api_key="test-key",
        lat=55.75,
        lon=37.62,
        max_retries=1,
    )
    await c.__aenter__()
    yield c
    await c.__aexit__(None, None, None)


CURRENT_WEATHER_RESPONSE = {
    "dt": 1742310000,
    "main": {
        "temp": 5.2,
        "feels_like": 2.1,
        "humidity": 78,
        "pressure": 1013,
    },
    "weather": [{"main": "Clouds", "description": "облачно"}],
    "wind": {"speed": 4.5},
}

FORECAST_RESPONSE = {
    "list": [
        {
            "dt_txt": "2026-03-18 09:00:00",
            "main": {"temp": 3.0, "humidity": 80},
            "weather": [{"main": "Clouds"}],
            "wind": {"speed": 3.0},
        },
        {
            "dt_txt": "2026-03-18 12:00:00",
            "main": {"temp": 6.0, "humidity": 70},
            "weather": [{"main": "Clear"}],
            "wind": {"speed": 2.0},
        },
        {
            "dt_txt": "2026-03-18 15:00:00",
            "main": {"temp": 7.0, "humidity": 65},
            "weather": [{"main": "Clear"}],
            "wind": {"speed": 2.5},
        },
        {
            "dt_txt": "2026-03-19 09:00:00",
            "main": {"temp": 1.0, "humidity": 90},
            "weather": [{"main": "Rain"}],
            "wind": {"speed": 5.0},
            "rain": {"3h": 2.5},
        },
    ],
}


@respx.mock
async def test_get_current(client):
    respx.get("https://api.openweathermap.org/data/2.5/weather").mock(
        return_value=Response(200, json=CURRENT_WEATHER_RESPONSE),
    )

    weather = await client.get_current()
    assert weather.temp == 5.2
    assert weather.weather_main == "Clouds"
    assert weather.humidity == 78


@respx.mock
async def test_get_current_api_error(client):
    respx.get("https://api.openweathermap.org/data/2.5/weather").mock(
        return_value=Response(401, text="Invalid API key"),
    )

    with pytest.raises(WeatherApiError):
        await client.get_current()


@respx.mock
async def test_get_forecast_5day(client):
    respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
        return_value=Response(200, json=FORECAST_RESPONSE),
    )

    forecast = await client.get_forecast_5day()
    assert len(forecast.daily) == 2

    day1 = forecast.daily[0]
    assert day1.date.isoformat() == "2026-03-18"
    assert day1.temp_min == 3.0
    assert day1.temp_max == 7.0
    assert day1.weather_main == "Clear"  # most common

    day2 = forecast.daily[1]
    assert day2.date.isoformat() == "2026-03-19"
    assert day2.precipitation == 2.5


@respx.mock
async def test_get_forecast_api_error(client):
    respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(
        return_value=Response(500, text="Server Error"),
    )

    with pytest.raises(WeatherApiError):
        await client.get_forecast_5day()
