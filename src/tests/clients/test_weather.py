import datetime

import pytest
import respx
from httpx import Response

from app.clients.weather import WeatherClient
from app.exceptions import WeatherApiError


@pytest.fixture
async def client():
    c = WeatherClient(
        lat=55.75,
        lon=37.62,
        max_retries=1,
        timeout=10.0,
    )
    await c.__aenter__()
    yield c
    await c.__aexit__(None, None, None)


FORECAST_RESPONSE = {
    "daily": {
        "time": ["2026-03-18", "2026-03-19"],
        "temperature_2m_max": [7.0, 2.0],
        "temperature_2m_min": [3.0, 1.0],
        "precipitation_sum": [0.0, 2.5],
        "weathercode": [1, 61],
        "windspeed_10m_max": [9.0, 18.0],
        "relative_humidity_2m_mean": [72, 90],
    },
}


@respx.mock
async def test_get_weather(client, monkeypatch):
    # Mock "today" so target_date falls within forecast range
    import app.clients.weather as wmod

    mock_now = datetime.datetime(2026, 3, 18, 12, 0, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(wmod, "now", lambda: mock_now)

    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=Response(200, json=FORECAST_RESPONSE),
    )

    day = await client.get_weather(datetime.date(2026, 3, 18))
    assert day is not None
    assert day.temp_min == 3.0
    assert day.temp_max == 7.0
    assert day.weather_main == "Clouds"
    assert day.humidity == 72
    assert day.wind_speed == 2.5  # 9 km/h → 2.5 m/s


@respx.mock
async def test_get_weather_not_found(client, monkeypatch):
    import app.clients.weather as wmod

    mock_now = datetime.datetime(2026, 3, 18, 12, 0, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(wmod, "now", lambda: mock_now)

    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=Response(200, json=FORECAST_RESPONSE),
    )

    day = await client.get_weather(datetime.date(2026, 3, 20))
    assert day is None


@respx.mock
async def test_get_weather_api_error(client, monkeypatch):
    import app.clients.weather as wmod

    mock_now = datetime.datetime(2026, 3, 18, 12, 0, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(wmod, "now", lambda: mock_now)

    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=Response(500, text="Server Error"),
    )

    with pytest.raises(WeatherApiError):
        await client.get_weather(datetime.date(2026, 3, 18))
