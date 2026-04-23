"""Unit tests for WeeklyForecaster — thresholds + nonzero-week counting."""
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.iiko import SaleRecord
from app.services.features_weekly import (
    WEEKLY_CATEGORICAL_FEATURES,
    WEEKLY_FEATURE_NAMES,
)
from app.services.forecasters.weekly import WeeklyForecaster


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


def _forecaster(settings: SimpleNamespace | None = None) -> WeeklyForecaster:
    return WeeklyForecaster(
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


class TestThresholdsComeFromSettings:
    def test_granularity_is_weekly(self):
        assert _forecaster().granularity == "weekly"

    def test_max_history_months_from_settings(self):
        f = _forecaster(_settings(weekly_max_history_months=24))
        assert f.max_history_months == 24

    def test_min_samples_from_settings(self):
        f = _forecaster(_settings(weekly_min_samples=6))
        assert f.min_samples == 6

    def test_min_sales_pct_from_settings(self):
        f = _forecaster(_settings(weekly_min_sales_pct=0.10))
        assert f.min_sales_pct == 0.10

    def test_min_accuracy_from_settings(self):
        f = _forecaster(_settings(weekly_min_accuracy=15.0))
        assert f.min_accuracy == 15.0

    def test_feature_names_match_weekly(self):
        assert _forecaster().feature_names == WEEKLY_FEATURE_NAMES

    def test_categorical_features_match_weekly(self):
        assert _forecaster().categorical_features == WEEKLY_CATEGORICAL_FEATURES


class TestCountNonzeroWeeksGroupsByMonday:
    def test_empty_sales_returns_zero(self):
        assert _forecaster()._count_nonzero_samples([]) == 0

    def test_single_sale_is_one_week(self):
        sales = [_sale(datetime.date(2026, 4, 13), 5.0)]
        assert _forecaster()._count_nonzero_samples(sales) == 1

    def test_same_week_sales_count_as_one(self):
        monday = datetime.date(2026, 4, 13)
        sales = [
            _sale(monday, 2.0),
            _sale(monday + datetime.timedelta(days=1), 3.0),
            _sale(monday + datetime.timedelta(days=4), 1.0),
        ]
        assert _forecaster()._count_nonzero_samples(sales) == 1

    def test_different_weeks_counted_separately(self):
        sales = [
            _sale(datetime.date(2026, 4, 6), 5.0),
            _sale(datetime.date(2026, 4, 13), 5.0),
            _sale(datetime.date(2026, 4, 20), 5.0),
        ]
        assert _forecaster()._count_nonzero_samples(sales) == 3

    def test_zero_quantity_week_not_counted(self):
        sales = [
            _sale(datetime.date(2026, 4, 6), 0.0),
            _sale(datetime.date(2026, 4, 13), 5.0),
        ]
        assert _forecaster()._count_nonzero_samples(sales) == 1

    def test_sunday_and_monday_are_different_weeks(self):
        sunday = datetime.date(2026, 4, 12)
        monday = datetime.date(2026, 4, 13)
        sales = [_sale(sunday, 1.0), _sale(monday, 1.0)]
        assert _forecaster()._count_nonzero_samples(sales) == 2
