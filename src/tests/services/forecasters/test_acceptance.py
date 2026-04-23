"""Acceptance tests for BaseForecaster — Domain-1 filter, training window, cleanup."""
import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.iiko import SaleRecord
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


def _sale(
    date: datetime.date,
    dish_id: str = "d1",
    dish_name: str = "Борщ",
    qty: float = 5.0,
) -> SaleRecord:
    return SaleRecord(
        date=date,
        dish_id=dish_id,
        dish_name=dish_name,
        quantity=qty,
        price=350.0,
        total=qty * 350.0,
    )


class TestDomain1FilterSkipsNonMenuDish:
    async def test_train_all_skips_dish_not_in_active_set(self):
        today = datetime.date(2026, 4, 20)
        # Active menu has only dish-keep. dish-skip sold historically but is not in menu.
        active_ids = {"dish-keep"}

        history: list[SaleRecord] = []
        for week in range(0, 20):
            monday = today - datetime.timedelta(days=7 * (week + 1))
            history.append(_sale(monday, dish_id="dish-keep", dish_name="Keep", qty=10))
            history.append(_sale(monday, dish_id="dish-skip", dish_name="Skip", qty=10))

        sales_repo = AsyncMock()
        sales_repo.get_sales_by_period = AsyncMock(return_value=history)
        sales_repo.get_daily_totals = AsyncMock(return_value=[])

        weather_repo = AsyncMock()
        weather_repo.get_weather_range = AsyncMock(return_value=[])

        menu_repo = AsyncMock()
        menu_repo.get_latest_active_dish_ids = AsyncMock(return_value=active_ids)

        ml_models_repo = AsyncMock()
        ml_models_repo.get_latest_model = AsyncMock(return_value=None)
        ml_models_repo.save_model = AsyncMock()
        ml_models_repo.get_all_models = AsyncMock(return_value=[])
        ml_models_repo.delete_models = AsyncMock()

        forecaster = WeeklyForecaster(
            settings=_settings(),
            sales_repo=sales_repo,
            ml_models_repo=ml_models_repo,
            weather_repo=weather_repo,
            menu_repo=menu_repo,
        )
        # Patch _fit_and_save to record which dishes it saw, avoid actual sklearn training
        trained_dishes: list[str] = []

        async def fake_fit(dish_id, dish_sales, dish_name, nonzero):
            trained_dishes.append(dish_id)
            return 90.0

        forecaster._fit_and_save = fake_fit  # type: ignore[assignment]

        await forecaster.train_all(force=True)

        assert "dish-keep" in trained_dishes
        assert "dish-skip" not in trained_dishes


class TestTrainingWindowBoundedByMaxHistoryMonths:
    def test_window_end_is_yesterday(self):
        today = datetime.date(2026, 4, 20)
        forecaster = WeeklyForecaster(
            settings=_settings(weekly_max_history_months=12),
            sales_repo=AsyncMock(),
            ml_models_repo=AsyncMock(),
            weather_repo=AsyncMock(),
            menu_repo=AsyncMock(),
        )
        window = forecaster._training_window(today)
        assert window.date_to == today - datetime.timedelta(days=1)

    def test_window_start_is_months_x_30_days_before_end(self):
        today = datetime.date(2026, 4, 20)
        forecaster = WeeklyForecaster(
            settings=_settings(weekly_max_history_months=12),
            sales_repo=AsyncMock(),
            ml_models_repo=AsyncMock(),
            weather_repo=AsyncMock(),
            menu_repo=AsyncMock(),
        )
        window = forecaster._training_window(today)
        expected_span_days = 12 * 30
        actual_span_days = (window.date_to - window.date_from).days
        assert actual_span_days == expected_span_days

    def test_smaller_history_produces_shorter_window(self):
        today = datetime.date(2026, 4, 20)
        short = WeeklyForecaster(
            settings=_settings(weekly_max_history_months=6),
            sales_repo=AsyncMock(),
            ml_models_repo=AsyncMock(),
            weather_repo=AsyncMock(),
            menu_repo=AsyncMock(),
        )._training_window(today)
        long_ = WeeklyForecaster(
            settings=_settings(weekly_max_history_months=24),
            sales_repo=AsyncMock(),
            ml_models_repo=AsyncMock(),
            weather_repo=AsyncMock(),
            menu_repo=AsyncMock(),
        )._training_window(today)
        assert (short.date_to - short.date_from).days == 6 * 30
        assert (long_.date_to - long_.date_from).days == 24 * 30
        assert short.date_from > long_.date_from


class TestCleanupObsoleteModelsRemovesDropped:
    async def test_delete_called_for_non_active_dish(self):
        active_ids = {"dish-keep"}

        existing_models = [
            SimpleNamespace(dish_id="dish-keep", dish_name="Keep"),
            SimpleNamespace(dish_id="dish-gone", dish_name="Gone"),
        ]
        ml_models_repo = AsyncMock()
        ml_models_repo.get_all_models = AsyncMock(return_value=existing_models)
        ml_models_repo.delete_models = AsyncMock()

        forecaster = WeeklyForecaster(
            settings=_settings(),
            sales_repo=AsyncMock(),
            ml_models_repo=ml_models_repo,
            weather_repo=AsyncMock(),
            menu_repo=AsyncMock(),
        )
        await forecaster._cleanup_obsolete_models(active_ids)

        ml_models_repo.delete_models.assert_awaited()
        delete_calls = [
            call.args[0] if call.args else call.kwargs.get("dish_id")
            for call in ml_models_repo.delete_models.call_args_list
        ]
        assert "dish-gone" in delete_calls
        assert "dish-keep" not in delete_calls

    async def test_no_deletes_when_all_dishes_active(self):
        active_ids = {"a", "b"}
        existing_models = [
            SimpleNamespace(dish_id="a", dish_name="A"),
            SimpleNamespace(dish_id="b", dish_name="B"),
        ]
        ml_models_repo = AsyncMock()
        ml_models_repo.get_all_models = AsyncMock(return_value=existing_models)
        ml_models_repo.delete_models = AsyncMock()

        forecaster = WeeklyForecaster(
            settings=_settings(),
            sales_repo=AsyncMock(),
            ml_models_repo=ml_models_repo,
            weather_repo=AsyncMock(),
            menu_repo=AsyncMock(),
        )
        await forecaster._cleanup_obsolete_models(active_ids)
        ml_models_repo.delete_models.assert_not_called()
