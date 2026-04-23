"""Cascading fallback tests for DailyForecaster._fallback.

Moved from the legacy `test_ml_forecast.py::TestCascadingFallback` suite.
The fallback logic now lives on the granularity-specific forecaster,
so the assertions here target `DailyForecaster._fallback` directly.
"""
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.models.iiko import SaleRecord
from app.services.forecasters.daily import DailyForecaster


def _settings(**overrides) -> SimpleNamespace:
    defaults = dict(
        weekly_max_history_months=36,
        weekly_min_samples=4,
        weekly_min_sales_pct=0.05,
        weekly_min_accuracy=0.0,
        daily_max_history_months=12,
        daily_min_samples=14,
        daily_min_sales_pct=0.05,
        daily_min_accuracy=20.0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _forecaster() -> DailyForecaster:
    return DailyForecaster(
        settings=_settings(),
        sales_repo=AsyncMock(),
        ml_models_repo=AsyncMock(),
        weather_repo=AsyncMock(),
        menu_repo=AsyncMock(),
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
        price=350.0,
        total=quantity * 350.0,
    )


class TestCascadingFallback:
    def test_same_weekday_average(self):
        target = datetime.date(2026, 4, 8)  # Wednesday
        sales = [
            _make_sale(target - datetime.timedelta(weeks=1), quantity=10),
            _make_sale(target - datetime.timedelta(weeks=2), quantity=20),
        ]
        assert _forecaster()._fallback(sales, target) == 15.0

    def test_falls_to_all_days_median(self):
        target = datetime.date(2026, 4, 8)  # Wednesday
        # Non-matching weekdays within 30 days (Monday & Friday)
        sales = [
            _make_sale(target - datetime.timedelta(days=2), quantity=12),
            _make_sale(target - datetime.timedelta(days=5), quantity=8),
        ]
        assert _forecaster()._fallback(sales, target) == 10.0

    def test_no_recent_sales_returns_zero(self):
        target = datetime.date(2026, 4, 8)
        sales = [_make_sale(target - datetime.timedelta(days=60), quantity=5)]
        assert _forecaster()._fallback(sales, target) == 0.0

    def test_no_sales_returns_zero(self):
        target = datetime.date(2026, 4, 8)
        assert _forecaster()._fallback([], target) == 0.0
