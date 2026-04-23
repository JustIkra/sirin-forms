"""Unit tests for DailyForecaster — thresholds + nonzero-day counting."""
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.iiko import SaleRecord
from app.services.features import CATEGORICAL_FEATURES, FEATURE_NAMES
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


def _forecaster(settings: SimpleNamespace | None = None) -> DailyForecaster:
    return DailyForecaster(
        settings=settings or _settings(),
        sales_repo=AsyncMock(),
        ml_models_repo=AsyncMock(),
        weather_repo=AsyncMock(),
        menu_repo=AsyncMock(),
    )


def _sale(date: datetime.date, qty: float = 1.0) -> SaleRecord:
    return SaleRecord(
        date=date,
        dish_id="d1",
        dish_name="Борщ",
        quantity=qty,
        price=350.0,
        total=qty * 350.0,
    )


class TestThresholdsFromSettings:
    def test_granularity_is_daily(self):
        assert _forecaster().granularity == "daily"

    def test_max_history_months_from_settings(self):
        f = _forecaster(_settings(daily_max_history_months=6))
        assert f.max_history_months == 6

    def test_min_samples_from_settings(self):
        f = _forecaster(_settings(daily_min_samples=21))
        assert f.min_samples == 21

    def test_min_sales_pct_from_settings(self):
        f = _forecaster(_settings(daily_min_sales_pct=0.08))
        assert f.min_sales_pct == 0.08

    def test_min_accuracy_from_settings(self):
        f = _forecaster(_settings(daily_min_accuracy=25.0))
        assert f.min_accuracy == 25.0

    def test_feature_names_match_daily(self):
        assert _forecaster().feature_names == FEATURE_NAMES

    def test_categorical_features_match_daily(self):
        assert _forecaster().categorical_features == CATEGORICAL_FEATURES


class TestCountNonzeroDays:
    def test_empty_sales_returns_zero(self):
        assert _forecaster()._count_nonzero_samples([]) == 0

    def test_single_day_single_sale(self):
        sales = [_sale(datetime.date(2026, 4, 13), 5.0)]
        assert _forecaster()._count_nonzero_samples(sales) == 1

    def test_same_day_multiple_records_count_as_one(self):
        day = datetime.date(2026, 4, 13)
        sales = [_sale(day, 2.0), _sale(day, 3.0), _sale(day, 1.0)]
        assert _forecaster()._count_nonzero_samples(sales) == 1

    def test_different_days_counted_separately(self):
        sales = [
            _sale(datetime.date(2026, 4, 13), 5.0),
            _sale(datetime.date(2026, 4, 14), 5.0),
            _sale(datetime.date(2026, 4, 15), 5.0),
        ]
        assert _forecaster()._count_nonzero_samples(sales) == 3

    def test_zero_quantity_day_not_counted(self):
        sales = [
            _sale(datetime.date(2026, 4, 13), 0.0),
            _sale(datetime.date(2026, 4, 14), 5.0),
        ]
        assert _forecaster()._count_nonzero_samples(sales) == 1
