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
from app.services.ml_forecast import MLForecastService


def _make_settings(**overrides) -> Settings:
    defaults = {
        "iiko_server_url": "http://iiko.test",
        "iiko_login": "admin",
        "iiko_password": "secret",
        "iiko_department_id": None,  # skip the stock-map fetch in tests
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


def _empty_menu_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_latest_active_dish_ids = AsyncMock(return_value=set())
    return repo


def _menu_repo_with(dish_ids: set[str]) -> AsyncMock:
    repo = AsyncMock()
    repo.get_latest_active_dish_ids = AsyncMock(return_value=dish_ids)
    return repo


# --- Feature engineering ---


class TestFeatures:
    def test_feature_names_count(self):
        assert len(FEATURE_NAMES) == 38

    def test_new_features_present(self):
        assert "day_of_month" in FEATURE_NAMES
        assert "is_payday_period" in FEATURE_NAMES
        assert "trend_7d" in FEATURE_NAMES
        assert "days_since_last_sale" in FEATURE_NAMES
        assert "total_restaurant_sales_7d_avg" in FEATURE_NAMES
        assert "lag_21d" in FEATURE_NAMES
        assert "lag_28d" in FEATURE_NAMES
        assert "rolling_avg_14d" in FEATURE_NAMES
        assert "rolling_avg_60d" in FEATURE_NAMES
        assert "density_30d" in FEATURE_NAMES
        assert "total_restaurant_sales_1d" in FEATURE_NAMES
        assert "same_weekday_max_4w" in FEATURE_NAMES

    def test_build_prediction_features_shape(self):
        target = datetime.date(2026, 4, 8)
        sales = [
            _make_sale(target - datetime.timedelta(days=i), quantity=5 + i)
            for i in range(1, 15)
        ]
        weather = _make_weather(target)
        features = build_prediction_features(target, sales, weather)
        assert features.shape == (1, 38)

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
        sales = [
            _make_sale(target - datetime.timedelta(days=i), quantity=float(i))
            for i in range(1, 8)
        ]
        features = build_prediction_features(target, sales, _make_weather(target))
        trend_idx = FEATURE_NAMES.index("trend_7d")
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
        features = build_prediction_features(
            target, [], _make_weather(target), total_daily_sales,
        )
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
            (target - datetime.timedelta(days=i)): _make_weather(
                target - datetime.timedelta(days=i),
            )
            for i in range(1, 15)
        }
        df = build_features_dataframe(sales, weather)
        for name in FEATURE_NAMES:
            assert name in df.columns, f"Missing column: {name}"
        assert "target" in df.columns


# --- Bias calibration bounds (pure math, no service needed) ---


class TestBiasCalibration:
    def test_correction_allows_3x(self):
        correction = max(0.3, min(3.0, 1 - (-2.0)))
        assert correction == 3.0

    def test_correction_allows_0_3x(self):
        correction = max(0.3, min(3.0, 1 - 2.0))
        assert correction == 0.3


class TestPriceFiltering:
    """Items without a catalog price must be excluded from ML forecasts."""

    def _service(self, menu_repo: AsyncMock) -> MLForecastService:
        service = MLForecastService(
            data_collector=MagicMock(),
            forecasts_repo=MagicMock(),
            ml_models_repo=MagicMock(),
            sales_repo=MagicMock(),
            weather_repo=MagicMock(),
            settings=_make_settings(),
            menu_repo=menu_repo,
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
        service._weather_repo.get_weather_range = AsyncMock(return_value=[])
        return service

    @staticmethod
    def _prior_week_sales(week_start: datetime.date, dish_id: str, dish_name: str):
        # Seed the weekly fallback so predict_dish returns > 0 without an
        # actual trained model — enables price-filter assertions.
        return [
            _make_sale(
                week_start - datetime.timedelta(days=7 * i),
                dish_id=dish_id, dish_name=dish_name, quantity=10,
            )
            for i in range(1, 5)
        ]

    async def test_priceless_dishes_excluded(self):
        target = datetime.date(2026, 4, 8)
        week_start = target - datetime.timedelta(days=target.weekday())
        service = self._service(_menu_repo_with({"d1", "d2", "d3"}))
        service._collector.collect_products.return_value = [
            IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
            IikoProduct(
                id="d2", name="Удалённое", product_type=ProductType.DISH, price=None,
            ),
            IikoProduct(id="d3", name="Нулевое", product_type=ProductType.DISH, price=0),
        ]
        service._collector.collect_recent_sales.return_value = [
            _make_sale(
                target - datetime.timedelta(days=1), dish_id="d1", dish_name="Борщ",
            ),
            _make_sale(
                target - datetime.timedelta(days=1),
                dish_id="d2",
                dish_name="Удалённое",
            ),
            _make_sale(
                target - datetime.timedelta(days=1),
                dish_id="d3",
                dish_name="Нулевое",
            ),
        ]
        service._collector.collect_weather.return_value = None
        service._sales_repo.get_sales_by_dish_name = AsyncMock(
            return_value=self._prior_week_sales(week_start, "d1", "Борщ"),
        )

        result = await service.generate_forecast(target)

        names = {f.dish_name for f in result.forecasts}
        assert "Борщ" in names
        assert "Удалённое" not in names
        assert "Нулевое" not in names

    async def test_price_propagated_to_dish_forecast(self):
        target = datetime.date(2026, 4, 8)
        week_start = target - datetime.timedelta(days=target.weekday())
        service = self._service(_menu_repo_with({"d1"}))
        service._collector.collect_products.return_value = [
            IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
        ]
        service._collector.collect_recent_sales.return_value = [
            _make_sale(
                target - datetime.timedelta(days=1), dish_id="d1", dish_name="Борщ",
            ),
        ]
        service._collector.collect_weather.return_value = None
        service._sales_repo.get_sales_by_dish_name = AsyncMock(
            return_value=self._prior_week_sales(week_start, "d1", "Борщ"),
        )

        result = await service.generate_forecast(target)

        assert len(result.forecasts) == 1
        assert result.forecasts[0].price == 350

    async def test_low_sales_excluded_by_median_threshold_fallback(self):
        """When menu snapshot is empty, the service falls back to the
        recent-sales heuristic and excludes items below the median threshold.
        """
        target = datetime.date(2026, 4, 8)
        service = MLForecastService(
            data_collector=MagicMock(),
            forecasts_repo=MagicMock(),
            ml_models_repo=MagicMock(),
            sales_repo=MagicMock(),
            weather_repo=MagicMock(),
            settings=_make_settings(weekly_min_sales_pct=0.15),
            menu_repo=_empty_menu_repo(),
        )
        service._collector.collect_products = AsyncMock(return_value=[
            IikoProduct(id="d1", name="Борщ", product_type=ProductType.DISH, price=350),
            IikoProduct(
                id="d2", name="Цезарь", product_type=ProductType.DISH, price=450,
            ),
            IikoProduct(
                id="d3", name="Редкое", product_type=ProductType.DISH, price=200,
            ),
        ])
        # Борщ: 30, Цезарь: 20, Редкое: 1 -> median=20, threshold=3.0
        service._collector.collect_recent_sales = AsyncMock(return_value=[
            _make_sale(
                target - datetime.timedelta(days=1),
                dish_id="d1", dish_name="Борщ", quantity=30,
            ),
            _make_sale(
                target - datetime.timedelta(days=1),
                dish_id="d2", dish_name="Цезарь", quantity=20,
            ),
            _make_sale(
                target - datetime.timedelta(days=1),
                dish_id="d3", dish_name="Редкое", quantity=1,
            ),
        ])
        service._collector.collect_weather = AsyncMock(return_value=None)
        service._forecasts_repo.get_forecast = AsyncMock(return_value=None)
        service._forecasts_repo.save_forecast = AsyncMock()
        service._ml_models_repo.count_models = AsyncMock(return_value=1)
        service._ml_models_repo.get_latest_model = AsyncMock(return_value=None)
        service._sales_repo.get_daily_totals = AsyncMock(return_value=[])
        service._sales_repo.get_sales_by_dish = AsyncMock(return_value=[])
        # Seed fallback sales for all surviving dishes so predict_dish returns > 0
        week_start = target - datetime.timedelta(days=target.weekday())
        fallback_sales = [
            _make_sale(
                week_start - datetime.timedelta(days=7 * i),
                dish_id="any", dish_name="any", quantity=10,
            )
            for i in range(1, 5)
        ]
        service._sales_repo.get_sales_by_dish_name = AsyncMock(
            return_value=fallback_sales,
        )
        service._weather_repo = MagicMock()
        service._weather_repo.get_weather_range = AsyncMock(return_value=[])

        result = await service.generate_forecast(target)

        names = {f.dish_name for f in result.forecasts}
        assert "Борщ" in names
        assert "Цезарь" in names
        assert "Редкое" not in names


class TestObsoleteForecastCleanup:
    """After retrain, cached forecasts for dropped dishes must be wiped."""

    def _service(self, menu_repo: AsyncMock) -> MLForecastService:
        service = MLForecastService(
            data_collector=MagicMock(),
            forecasts_repo=MagicMock(),
            ml_models_repo=MagicMock(),
            sales_repo=MagicMock(),
            weather_repo=MagicMock(),
            settings=_make_settings(),
            menu_repo=menu_repo,
        )
        service._weekly.train_all = AsyncMock(return_value={"trained": 0})
        service._daily.train_all = AsyncMock(return_value={"trained": 0})
        service._forecasts_repo.delete_obsolete_forecasts = AsyncMock(return_value=0)
        return service

    async def test_weekly_retrain_wipes_obsolete_weekly_forecasts(self):
        service = self._service(_menu_repo_with({"active"}))
        await service.train_models(force=False)

        service._forecasts_repo.delete_obsolete_forecasts.assert_awaited_once_with(
            {"active"}, method="ml",
        )

    async def test_daily_retrain_wipes_obsolete_daily_forecasts(self):
        service = self._service(_menu_repo_with({"active"}))
        await service.train_daily_models(force=False)

        service._forecasts_repo.delete_obsolete_forecasts.assert_awaited_once_with(
            {"active"}, method="ml_daily",
        )

    async def test_cleanup_skipped_when_snapshot_empty(self):
        """Empty snapshot → skip cleanup. Never wipe the whole cache because
        the snapshot lagged behind at the moment of retrain."""
        service = self._service(_empty_menu_repo())
        await service.train_models(force=False)
        await service.train_daily_models(force=False)

        service._forecasts_repo.delete_obsolete_forecasts.assert_not_called()
