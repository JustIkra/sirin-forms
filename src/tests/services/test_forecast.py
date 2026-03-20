import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.models.forecast import DailyForecastResult, DishForecast
from app.models.iiko import IikoProduct, OlapReportType, ProductType, SaleRecord
from app.models.weather import DailyWeather
from app.services.data_collector import DataCollector
from app.services.forecast import ForecastService
from app.services.prompt_builder import PromptBuilder


def _make_settings(**overrides) -> Settings:
    defaults = {
        "iiko_server_url": "http://iiko.test",
        "iiko_login": "admin",
        "iiko_password": "secret",
        "openrouter_api_key": "sk-test",
        "owm_api_key": "owm-test",
        "restaurant_lat": 55.75,
        "restaurant_lon": 37.62,
        "history_months": 24,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_dishes() -> list[IikoProduct]:
    return [
        IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
        IikoProduct(id="d2", name="Цезарь", product_type=ProductType.DISH, price=450),
    ]


def _make_forecast_result(target_date: datetime.date) -> DailyForecastResult:
    return DailyForecastResult(
        date=target_date,
        forecasts=[
            DishForecast(
                dish_id="d1",
                dish_name="Борщ",
                predicted_quantity=25,
                confidence=0.85,
                key_factors=["среда", "весна"],
            ),
            DishForecast(
                dish_id="d2",
                dish_name="Цезарь",
                predicted_quantity=18,
                confidence=0.78,
                key_factors=["тренд вверх"],
            ),
        ],
        notes="Стабильный спрос",
    )


def _make_sale(
    date: datetime.date,
    dish_id: str = "d1",
    dish_name: str = "Борщ",
    quantity: float = 10,
) -> SaleRecord:
    return SaleRecord(
        date=date,
        dish_id=dish_id,
        dish_name=dish_name,
        quantity=quantity,
        price=350,
        total=quantity * 350,
    )


def _make_weather(date: datetime.date) -> DailyWeather:
    return DailyWeather(
        date=date,
        temp_min=-2,
        temp_max=5,
        temp_avg=1.5,
        precipitation=0.0,
        weather_main="Clear",
        humidity=65,
        wind_speed=3.2,
    )


@pytest.fixture
def settings():
    return _make_settings()


@pytest.fixture
def mock_collector():
    collector = MagicMock(spec=DataCollector)
    collector.collect_products = AsyncMock()
    collector.collect_historical_sales = AsyncMock()
    collector.collect_recent_sales = AsyncMock()
    collector.collect_weather = AsyncMock()
    return collector


@pytest.fixture
def mock_openrouter():
    client = MagicMock()
    client.generate_daily_forecast = AsyncMock()
    return client


@pytest.fixture
def mock_forecasts_repo():
    repo = MagicMock()
    repo.get_forecast = AsyncMock()
    repo.save_forecast = AsyncMock()
    return repo


@pytest.fixture
def service(mock_collector, mock_openrouter, mock_forecasts_repo, settings):
    return ForecastService(
        data_collector=mock_collector,
        prompt_builder=PromptBuilder(),
        openrouter_client=mock_openrouter,
        forecasts_repo=mock_forecasts_repo,
        settings=settings,
    )


# --- Tests ---


async def test_generate_forecast_returns_cached(
    service, mock_forecasts_repo, mock_collector,
):
    target = datetime.date(2026, 3, 20)
    cached = _make_forecast_result(target)
    mock_forecasts_repo.get_forecast.return_value = cached

    result = await service.generate_forecast(target)

    assert result is cached
    mock_collector.collect_products.assert_not_called()
    mock_forecasts_repo.save_forecast.assert_not_called()


async def test_generate_forecast_force_regenerates(
    service, mock_collector, mock_openrouter, mock_forecasts_repo,
):
    target = datetime.date(2026, 3, 20)
    cached = _make_forecast_result(target)
    mock_forecasts_repo.get_forecast.return_value = cached

    dishes = _make_dishes()
    mock_collector.collect_products.return_value = dishes
    mock_collector.collect_historical_sales.return_value = []
    mock_collector.collect_recent_sales.return_value = []
    mock_collector.collect_weather.return_value = None

    new_forecast = _make_forecast_result(target)
    mock_openrouter.generate_daily_forecast.return_value = new_forecast

    result = await service.generate_forecast(target, force=True)

    mock_forecasts_repo.get_forecast.assert_not_called()
    mock_collector.collect_products.assert_called_once()
    mock_openrouter.generate_daily_forecast.assert_called_once()
    mock_forecasts_repo.save_forecast.assert_called_once()
    assert result.date == target


async def test_generate_forecast_full_pipeline(
    service, mock_collector, mock_openrouter, mock_forecasts_repo,
):
    target = datetime.date(2026, 3, 20)
    mock_forecasts_repo.get_forecast.return_value = None

    dishes = _make_dishes()
    mock_collector.collect_products.return_value = dishes
    mock_collector.collect_historical_sales.return_value = [
        _make_sale(datetime.date(2025, 3, 21)),  # Friday, same weekday as 2026-03-20
        _make_sale(datetime.date(2025, 3, 21), dish_id="d2", dish_name="Цезарь", quantity=8),
    ]
    mock_collector.collect_recent_sales.return_value = [
        _make_sale(datetime.date(2026, 3, 15)),
        _make_sale(datetime.date(2026, 3, 15), dish_id="d2", dish_name="Цезарь", quantity=6),
    ]
    weather = _make_weather(target)
    mock_collector.collect_weather.return_value = weather

    llm_result = _make_forecast_result(target)
    mock_openrouter.generate_daily_forecast.return_value = llm_result

    result = await service.generate_forecast(target)

    assert result.date == target
    assert len(result.forecasts) == 2
    mock_openrouter.generate_daily_forecast.assert_called_once()
    # Verify prompt args contain data
    call_kwargs = mock_openrouter.generate_daily_forecast.call_args
    assert "Борщ" in call_kwargs.kwargs["sales_data"]
    assert "Clear" in call_kwargs.kwargs["weather_data"] or "°C" in call_kwargs.kwargs["weather_data"]
    assert "пятница" in call_kwargs.kwargs["calendar_info"]
    assert "Борщ" in call_kwargs.kwargs["menu_info"]


def test_historical_ranges_correct():
    target = datetime.date(2026, 3, 20)
    ranges = DataCollector._build_historical_ranges(target, history_months=24)

    assert len(ranges) == 2
    # Year 1: center=2025-03-20, ±7 days
    assert ranges[0] == (datetime.date(2025, 3, 13), datetime.date(2025, 3, 27))
    # Year 2: center=2024-03-20, ±7 days
    assert ranges[1] == (datetime.date(2024, 3, 13), datetime.date(2024, 3, 27))


def test_historical_ranges_12_months():
    target = datetime.date(2026, 3, 20)
    ranges = DataCollector._build_historical_ranges(target, history_months=12)

    assert len(ranges) == 1
    assert ranges[0] == (datetime.date(2025, 3, 13), datetime.date(2025, 3, 27))


async def test_post_process_removes_unknown_dishes():
    target = datetime.date(2026, 3, 20)
    dishes = _make_dishes()  # d1, d2

    result = DailyForecastResult(
        date=target,
        forecasts=[
            DishForecast(dish_id="d1", dish_name="Борщ", predicted_quantity=25, confidence=0.85),
            DishForecast(dish_id="d2", dish_name="Цезарь", predicted_quantity=18, confidence=0.78),
            DishForecast(dish_id="d999", dish_name="Несуществующее", predicted_quantity=10, confidence=0.5),
        ],
    )

    processed = ForecastService._post_process_forecast(result, dishes, None, target)

    assert len(processed.forecasts) == 2
    assert all(d.dish_id in ("d1", "d2") for d in processed.forecasts)


async def test_post_process_clamps_values():
    target = datetime.date(2026, 3, 20)
    dishes = _make_dishes()

    result = DailyForecastResult(
        date=target,
        forecasts=[
            DishForecast(dish_id="d1", dish_name="Борщ", predicted_quantity=-5, confidence=1.5),
        ],
    )

    processed = ForecastService._post_process_forecast(result, dishes, None, target)

    assert processed.forecasts[0].predicted_quantity == 0.0
    assert processed.forecasts[0].confidence == 1.0


async def test_weather_fallback_when_unavailable(
    service, mock_collector, mock_openrouter, mock_forecasts_repo,
):
    target = datetime.date(2026, 3, 20)
    mock_forecasts_repo.get_forecast.return_value = None

    dishes = _make_dishes()
    mock_collector.collect_products.return_value = dishes
    mock_collector.collect_historical_sales.return_value = []
    mock_collector.collect_recent_sales.return_value = []
    mock_collector.collect_weather.return_value = None  # Weather unavailable

    llm_result = _make_forecast_result(target)
    mock_openrouter.generate_daily_forecast.return_value = llm_result

    result = await service.generate_forecast(target)

    assert result.date == target
    # Weather data in prompt should be the fallback text
    call_kwargs = mock_openrouter.generate_daily_forecast.call_args
    assert "недоступен" in call_kwargs.kwargs["weather_data"]


def test_prompt_builder_sales_data():
    target = datetime.date(2026, 3, 18)  # Wednesday
    historical = [
        _make_sale(datetime.date(2025, 3, 19), quantity=20),  # Wednesday
        _make_sale(datetime.date(2025, 3, 12), quantity=15),  # Wednesday
        _make_sale(datetime.date(2025, 3, 20), quantity=30),  # Thursday — excluded
    ]
    recent = [_make_sale(datetime.date(2026, 3, 10), quantity=12)]

    text = PromptBuilder.build_sales_data(historical, recent, target)

    assert "Борщ" in text
    assert "17.5" in text  # average of 20 and 15
    assert "Выручка" in text


def test_prompt_builder_weather_data():
    weather = _make_weather(datetime.date(2026, 3, 18))
    text = PromptBuilder.build_weather_data(weather)

    assert "-2°C" in text
    assert "5°C" in text
    assert "Clear" in text
    assert "65%" in text


def test_prompt_builder_weather_none():
    text = PromptBuilder.build_weather_data(None)
    assert "недоступен" in text


def test_prompt_builder_calendar_info():
    text = PromptBuilder.build_calendar_info(datetime.date(2026, 3, 8))
    assert "воскресенье" in text
    assert "Международный женский день" in text


def test_prompt_builder_menu_info():
    dishes = _make_dishes()
    text = PromptBuilder.build_menu_info(dishes)
    assert "Борщ" in text
    assert "Цезарь" in text
    assert "d1" in text
