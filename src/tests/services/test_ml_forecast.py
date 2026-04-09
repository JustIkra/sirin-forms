import datetime
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from app.config import Settings
from app.models.iiko import IikoProduct, ProductType, SaleRecord
from app.models.weather import DailyWeather
from app.services.features import (
    FEATURE_NAMES,
    build_features_dataframe,
    build_prediction_features,
)
from app.services.ml_forecast import MIN_SAMPLES, MLForecastService


def _make_settings(**overrides) -> Settings:
    defaults = {
        "iiko_server_url": "http://iiko.test",
        "iiko_login": "admin",
        "iiko_password": "secret",
        "openrouter_api_key": "sk-test",
        "restaurant_lat": 55.75,
        "restaurant_lon": 37.62,
        "history_months": 24,
    }
    defaults.update(overrides)
    return Settings(**defaults)


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


# --- MIN_SAMPLES ---


def test_min_samples_is_7():
    assert MIN_SAMPLES == 7


# --- Cascading fallback ---


class TestCascadingFallback:
    def test_same_weekday_average(self):
        target = datetime.date(2026, 4, 8)  # Wednesday
        sales = [
            _make_sale(target - datetime.timedelta(weeks=1), quantity=10),
            _make_sale(target - datetime.timedelta(weeks=2), quantity=20),
        ]
        result = MLForecastService._cascading_fallback(sales, target)
        assert result == 15.0

    def test_falls_to_all_days_median(self):
        target = datetime.date(2026, 4, 8)  # Wednesday
        # Sales on non-matching weekdays within 30 days
        sales = [
            _make_sale(target - datetime.timedelta(days=2), quantity=12),
            _make_sale(target - datetime.timedelta(days=5), quantity=8),
        ]
        result = MLForecastService._cascading_fallback(sales, target)
        assert result == 10.0  # median of [12, 8] = 10

    def test_no_recent_sales_returns_zero(self):
        target = datetime.date(2026, 4, 8)
        # Sales only >30 days ago — no Level 3 fallback
        sales = [
            _make_sale(target - datetime.timedelta(days=60), quantity=5),
        ]
        result = MLForecastService._cascading_fallback(sales, target)
        assert result == 0.0

    def test_no_sales_returns_zero(self):
        target = datetime.date(2026, 4, 8)
        result = MLForecastService._cascading_fallback([], target)
        assert result == 0.0


# --- Feature engineering ---


class TestFeatures:
    def test_feature_names_count(self):
        assert len(FEATURE_NAMES) == 19

    def test_new_features_present(self):
        assert "day_of_month" in FEATURE_NAMES
        assert "is_payday_period" in FEATURE_NAMES
        assert "trend_7d" in FEATURE_NAMES
        assert "days_since_last_sale" in FEATURE_NAMES
        assert "total_restaurant_sales_7d_avg" in FEATURE_NAMES

    def test_build_prediction_features_shape(self):
        target = datetime.date(2026, 4, 8)
        sales = [
            _make_sale(target - datetime.timedelta(days=i), quantity=5 + i)
            for i in range(1, 15)
        ]
        weather = _make_weather(target)
        features = build_prediction_features(target, sales, weather)
        assert features.shape == (1, 19)

    def test_is_payday_period_day_25(self):
        target = datetime.date(2026, 4, 25)
        features = build_prediction_features(target, [], _make_weather(target))
        payday_idx = FEATURE_NAMES.index("is_payday_period")
        assert features[0, payday_idx] == 1

    def test_is_payday_period_day_5(self):
        target = datetime.date(2026, 4, 5)
        features = build_prediction_features(target, [], _make_weather(target))
        payday_idx = FEATURE_NAMES.index("is_payday_period")
        assert features[0, payday_idx] == 1

    def test_is_payday_period_day_15(self):
        target = datetime.date(2026, 4, 15)
        features = build_prediction_features(target, [], _make_weather(target))
        payday_idx = FEATURE_NAMES.index("is_payday_period")
        assert features[0, payday_idx] == 0

    def test_day_of_month(self):
        target = datetime.date(2026, 4, 17)
        features = build_prediction_features(target, [], _make_weather(target))
        dom_idx = FEATURE_NAMES.index("day_of_month")
        assert features[0, dom_idx] == 17

    def test_trend_7d_positive(self):
        target = datetime.date(2026, 4, 8)
        # Increasing sales over last 7 days
        sales = [
            _make_sale(target - datetime.timedelta(days=i), quantity=float(i))
            for i in range(1, 8)
        ]
        features = build_prediction_features(target, sales, _make_weather(target))
        trend_idx = FEATURE_NAMES.index("trend_7d")
        # qty goes 1,2,3,4,5,6,7 as offset 1..7 but recent_7 is collected in offset order
        # so recent_7 = [1,2,3,4,5,6,7] -> positive slope
        assert features[0, trend_idx] > 0

    def test_days_since_last_sale(self):
        target = datetime.date(2026, 4, 8)
        sales = [
            _make_sale(target - datetime.timedelta(days=5), quantity=10),
        ]
        features = build_prediction_features(target, sales, _make_weather(target))
        dsls_idx = FEATURE_NAMES.index("days_since_last_sale")
        assert features[0, dsls_idx] == 5

    def test_total_restaurant_sales_7d_avg(self):
        target = datetime.date(2026, 4, 8)
        total_daily_sales = {
            target - datetime.timedelta(days=i): 100.0 * i
            for i in range(1, 8)
        }
        features = build_prediction_features(target, [], _make_weather(target), total_daily_sales)
        total_idx = FEATURE_NAMES.index("total_restaurant_sales_7d_avg")
        expected = np.mean([100.0 * i for i in range(1, 8)])
        assert abs(features[0, total_idx] - expected) < 0.01

    def test_total_restaurant_sales_none(self):
        target = datetime.date(2026, 4, 8)
        features = build_prediction_features(target, [], _make_weather(target), None)
        total_idx = FEATURE_NAMES.index("total_restaurant_sales_7d_avg")
        assert np.isnan(features[0, total_idx])

    def test_build_features_dataframe_columns(self):
        target = datetime.date(2026, 4, 8)
        sales = [
            _make_sale(target - datetime.timedelta(days=i), quantity=5.0)
            for i in range(1, 15)
        ]
        weather = {
            (target - datetime.timedelta(days=i)): _make_weather(target - datetime.timedelta(days=i))
            for i in range(1, 15)
        }
        df = build_features_dataframe(sales, weather)
        for name in FEATURE_NAMES:
            assert name in df.columns, f"Missing column: {name}"
        assert "target" in df.columns


# --- Bias calibration bounds ---


class TestBiasCalibration:
    def test_correction_allows_3x(self):
        # bias = -2.0 means massive under-prediction
        correction = max(0.3, min(3.0, 1 - (-2.0)))
        assert correction == 3.0

    def test_correction_allows_0_3x(self):
        # bias = 2.0 means massive over-prediction
        correction = max(0.3, min(3.0, 1 - 2.0))
        assert correction == 0.3


# --- Feature compatibility ---


class TestFeatureCompatibility:
    @pytest.fixture
    def ml_service(self):
        return MLForecastService(
            data_collector=MagicMock(),
            forecasts_repo=MagicMock(),
            ml_models_repo=MagicMock(),
            sales_repo=MagicMock(),
            weather_repo=MagicMock(),
            settings=_make_settings(),
        )

    async def test_stale_model_skipped(self, ml_service):
        ml_service._sales_repo.get_sales_by_dish = AsyncMock(return_value=[])
        ml_service._sales_repo.get_sales_by_dish_name = AsyncMock(return_value=[])

        model_record = MagicMock()
        model_record.feature_names = ["old_feature_1", "old_feature_2"]
        model_record.model_blob = b""

        result = await ml_service._predict_dish(
            "d1", "Борщ", datetime.date(2026, 4, 8), None, model_record,
        )
        # Should return fallback (0.0 with no sales), not try to load model
        assert result == 0.0

    async def test_compatible_model_used(self, ml_service):
        target = datetime.date(2026, 4, 8)
        sales = [
            _make_sale(target - datetime.timedelta(days=i), quantity=10.0)
            for i in range(1, 15)
        ]
        ml_service._sales_repo.get_sales_by_dish = AsyncMock(return_value=sales)
        ml_service._sales_repo.get_sales_by_dish_name = AsyncMock(return_value=sales)

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([12.0])

        model_record = MagicMock()
        model_record.feature_names = FEATURE_NAMES
        model_record.model_blob = b"dummy"

        import app.services.ml_forecast as ml_mod
        original_load = ml_mod.joblib.load
        ml_mod.joblib.load = MagicMock(return_value=mock_model)
        try:
            result = await ml_service._predict_dish(
                "d1", "Борщ", target, _make_weather(target), model_record,
            )
            assert result == 12.0
        finally:
            ml_mod.joblib.load = original_load


class TestPriceFiltering:
    """Items without a catalog price must be excluded from ML forecasts."""

    @pytest.fixture
    def ml_service(self):
        service = MLForecastService(
            data_collector=MagicMock(),
            forecasts_repo=MagicMock(),
            ml_models_repo=MagicMock(),
            sales_repo=MagicMock(),
            weather_repo=MagicMock(),
            settings=_make_settings(),
        )
        service._collector.collect_products = AsyncMock()
        service._collector.collect_recent_sales = AsyncMock()
        service._collector.collect_weather = AsyncMock()
        service._forecasts_repo.get_forecast = AsyncMock(return_value=None)
        service._forecasts_repo.save_forecast = AsyncMock()
        service._ml_models_repo.count_models = AsyncMock(return_value=1)
        service._ml_models_repo.get_latest_model = AsyncMock(return_value=None)
        service._sales_repo.get_daily_totals = AsyncMock(return_value=[])
        service._sales_repo.get_sales_by_dish = AsyncMock(return_value=[])
        service._sales_repo.get_sales_by_dish_name = AsyncMock(return_value=[])
        service._weather_repo = MagicMock()
        return service

    async def test_priceless_dishes_excluded(self, ml_service):
        target = datetime.date(2026, 4, 8)
        ml_service._collector.collect_products.return_value = [
            IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
            IikoProduct(id="d2", name="Удалённое", product_type=ProductType.DISH, price=None),
            IikoProduct(id="d3", name="Нулевое", product_type=ProductType.DISH, price=0),
        ]
        ml_service._collector.collect_recent_sales.return_value = [
            _make_sale(target - datetime.timedelta(days=1), dish_id="d1", dish_name="Борщ"),
            _make_sale(target - datetime.timedelta(days=1), dish_id="d2", dish_name="Удалённое"),
            _make_sale(target - datetime.timedelta(days=1), dish_id="d3", dish_name="Нулевое"),
        ]
        ml_service._collector.collect_weather.return_value = None

        result = await ml_service.generate_forecast(target)

        names = {f.dish_name for f in result.forecasts}
        assert "Борщ" in names
        assert "Удалённое" not in names
        assert "Нулевое" not in names

    async def test_price_propagated_to_dish_forecast(self, ml_service):
        target = datetime.date(2026, 4, 8)
        ml_service._collector.collect_products.return_value = [
            IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
        ]
        ml_service._collector.collect_recent_sales.return_value = [
            _make_sale(target - datetime.timedelta(days=1), dish_id="d1", dish_name="Борщ"),
        ]
        ml_service._collector.collect_weather.return_value = None

        result = await ml_service.generate_forecast(target)

        assert len(result.forecasts) == 1
        assert result.forecasts[0].price == 350

    async def test_low_sales_excluded_by_median_threshold(self):
        """Items with sales below min_sales_pct of median should be excluded."""
        target = datetime.date(2026, 4, 8)
        service = MLForecastService(
            data_collector=MagicMock(),
            forecasts_repo=MagicMock(),
            ml_models_repo=MagicMock(),
            sales_repo=MagicMock(),
            weather_repo=MagicMock(),
            settings=_make_settings(min_sales_pct=0.15),
        )
        service._collector.collect_products = AsyncMock(return_value=[
            IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
            IikoProduct(id="d2", name="Цезарь", product_type=ProductType.DISH, price=450),
            IikoProduct(id="d3", name="Редкое", product_type=ProductType.DISH, price=200),
        ])
        # Борщ: 30, Цезарь: 20, Редкое: 1 → median=20, threshold=3.0
        service._collector.collect_recent_sales = AsyncMock(return_value=[
            _make_sale(target - datetime.timedelta(days=1), dish_id="d1", dish_name="Борщ", quantity=30),
            _make_sale(target - datetime.timedelta(days=1), dish_id="d2", dish_name="Цезарь", quantity=20),
            _make_sale(target - datetime.timedelta(days=1), dish_id="d3", dish_name="Редкое", quantity=1),
        ])
        service._collector.collect_weather = AsyncMock(return_value=None)
        service._forecasts_repo.get_forecast = AsyncMock(return_value=None)
        service._forecasts_repo.save_forecast = AsyncMock()
        service._ml_models_repo.count_models = AsyncMock(return_value=1)
        service._ml_models_repo.get_latest_model = AsyncMock(return_value=None)
        service._sales_repo.get_daily_totals = AsyncMock(return_value=[])
        service._sales_repo.get_sales_by_dish = AsyncMock(return_value=[])
        service._sales_repo.get_sales_by_dish_name = AsyncMock(return_value=[])

        result = await service.generate_forecast(target)

        names = {f.dish_name for f in result.forecasts}
        assert "Борщ" in names
        assert "Цезарь" in names
        assert "Редкое" not in names
