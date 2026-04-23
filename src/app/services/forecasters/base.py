"""Abstract base class for granularity-specific ML forecasters."""
from __future__ import annotations

import datetime
import io
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather

if TYPE_CHECKING:
    from app.config import Settings
    from app.repositories.menu_snapshots import MenuSnapshotsRepository
    from app.repositories.ml_models import MLModelsRepository
    from app.repositories.sales import SalesRepository
    from app.repositories.weather import WeatherRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TrainingWindow:
    date_from: datetime.date
    date_to: datetime.date


class BaseForecaster(ABC):
    granularity: str = ""

    def __init__(
        self,
        *,
        settings: Settings,
        sales_repo: SalesRepository,
        ml_models_repo: MLModelsRepository,
        weather_repo: WeatherRepository,
        menu_repo: MenuSnapshotsRepository,
    ) -> None:
        self._settings = settings
        self._sales_repo = sales_repo
        self._ml_models_repo = ml_models_repo
        self._weather_repo = weather_repo
        self._menu_repo = menu_repo

    # --- granularity-specific configuration ---

    @property
    @abstractmethod
    def max_history_months(self) -> int: ...

    @property
    @abstractmethod
    def min_samples(self) -> int: ...

    @property
    @abstractmethod
    def min_sales_pct(self) -> float: ...

    @property
    @abstractmethod
    def min_accuracy(self) -> float: ...

    @property
    @abstractmethod
    def feature_names(self) -> list[str]: ...

    @property
    @abstractmethod
    def categorical_features(self) -> list[int]: ...

    # --- granularity-specific behavior ---

    @abstractmethod
    def _count_nonzero_samples(self, sales: list[SaleRecord]) -> int: ...

    @abstractmethod
    def _build_training_frame(
        self,
        sales: list[SaleRecord],
        weather_by_date: dict[datetime.date, DailyWeather],
        totals: dict[datetime.date, float],
    ) -> Any: ...

    @abstractmethod
    def _build_prediction_features(
        self,
        target_date: datetime.date,
        sales: list[SaleRecord],
        weather: DailyWeather | dict[datetime.date, DailyWeather] | None,
        totals: dict[datetime.date, float] | None,
    ) -> Any: ...

    @abstractmethod
    def _fallback(
        self, sales: list[SaleRecord], target_date: datetime.date,
    ) -> float: ...

    @abstractmethod
    def _model_params(self) -> dict[str, Any]: ...

    @abstractmethod
    def _min_rows_for_cv(self) -> int: ...

    # --- common behavior ---

    async def _get_active_dish_ids(self) -> set[str]:
        return await self._menu_repo.get_latest_active_dish_ids()

    def _training_window(self, today: datetime.date) -> TrainingWindow:
        # Window is inclusive of both endpoints. date_to = yesterday to avoid
        # partial/in-flight data for today.
        date_to = today - datetime.timedelta(days=1)
        date_from = date_to - datetime.timedelta(days=self.max_history_months * 30)
        return TrainingWindow(date_from=date_from, date_to=date_to)

    async def train_all(self, *, force: bool = False) -> dict[str, Any]:
        from app.utils.dt import today as today_msk

        today = today_msk()
        window = self._training_window(today)

        active_ids = await self._get_active_dish_ids()
        if not active_ids:
            logger.warning(
                "%s forecaster: active menu is empty, skipping training",
                self.granularity,
            )
            return {
                "trained": 0,
                "skipped": 0,
                "failed": 0,
                "filtered_low_accuracy": 0,
                "avg_accuracy_pct": 0.0,
            }

        all_sales = await self._sales_repo.get_sales_by_period(
            window.date_from, window.date_to,
        )

        sales_by_dish: dict[str, list[SaleRecord]] = defaultdict(list)
        dish_names: dict[str, str] = {}
        for s in all_sales:
            if s.dish_id not in active_ids:
                continue
            sales_by_dish[s.dish_id].append(s)
            dish_names[s.dish_id] = s.dish_name

        trained = 0
        skipped = 0
        failed = 0
        filtered_low_acc = 0
        successfully_trained_ids: set[str] = set()
        all_accuracies: list[float] = []

        for dish_id, dish_sales in sales_by_dish.items():
            nonzero = self._count_nonzero_samples(dish_sales)
            if nonzero < self.min_samples:
                skipped += 1
                continue

            if not force:
                existing = await self._ml_models_repo.get_latest_model(
                    dish_id, granularity=self.granularity,
                )
                if (
                    existing
                    and existing.samples_count >= nonzero
                    and existing.feature_names == self.feature_names
                ):
                    skipped += 1
                    # An up-to-date model for an active dish counts as healthy state;
                    # keep in successful set so cleanup doesn't wipe it.
                    successfully_trained_ids.add(dish_id)
                    continue

            try:
                accuracy = await self._fit_and_save(
                    dish_id, dish_sales, dish_names[dish_id], nonzero,
                )
            except Exception:
                logger.error(
                    "%s training failed for %s",
                    self.granularity, dish_names.get(dish_id, dish_id),
                    exc_info=True,
                )
                failed += 1
                continue

            if accuracy < self.min_accuracy:
                filtered_low_acc += 1
                await self._ml_models_repo.delete_models(
                    dish_id, granularity=self.granularity,
                )
                logger.info(
                    "%s model for %s filtered: accuracy=%.1f%% < %.1f%%",
                    self.granularity, dish_names[dish_id],
                    accuracy, self.min_accuracy,
                )
                continue

            trained += 1
            successfully_trained_ids.add(dish_id)
            all_accuracies.append(accuracy)

        await self._cleanup_obsolete_models(active_ids)

        avg_accuracy = (
            round(float(np.mean(all_accuracies)), 1) if all_accuracies else 0.0
        )
        return {
            "trained": trained,
            "skipped": skipped,
            "failed": failed,
            "filtered_low_accuracy": filtered_low_acc,
            "avg_accuracy_pct": avg_accuracy,
        }

    async def _fit_and_save(
        self,
        dish_id: str,
        dish_sales: list[SaleRecord],
        dish_name: str,
        nonzero: int,
    ) -> float:
        window_from = min(s.date for s in dish_sales)
        window_to = max(s.date for s in dish_sales)
        weather_records = await self._weather_repo.get_weather_range(
            window_from, window_to,
        )
        weather_by_date = {w.date: w for w in weather_records}
        totals_rows = await self._sales_repo.get_daily_totals(window_from, window_to)
        totals = {r.date: r.total_quantity for r in totals_rows}

        df = self._build_training_frame(dish_sales, weather_by_date, totals)
        X = df[self.feature_names].values
        y = df["target"].values

        model = HistGradientBoostingRegressor(
            categorical_features=self.categorical_features,
            **self._model_params(),
        )

        min_cv_rows = self._min_rows_for_cv()
        if len(y) >= min_cv_rows:
            n_splits = min(5, max(2, len(y) // (min_cv_rows // 2 or 1)))
            tscv = TimeSeriesSplit(n_splits=n_splits)
            mae_scores: list[float] = []
            acc_scores: list[float] = []
            for train_idx, test_idx in tscv.split(X):
                model.fit(X[train_idx], y[train_idx])
                y_pred = model.predict(X[test_idx])
                mae_scores.append(float(np.mean(np.abs(y[test_idx] - y_pred))))
                denom = np.maximum(y[test_idx], y_pred)
                denom = np.where(denom == 0, 1.0, denom)
                acc_scores.append(
                    float(
                        (1 - np.mean(np.abs(y[test_idx] - y_pred) / denom)) * 100
                    )
                )
            mae_test = float(np.mean(mae_scores))
            accuracy = float(np.mean(acc_scores))
            test_size = len(y) // (n_splits + 1)
        else:
            test_size = max(2, len(y) // 5)
            train_end = len(y) - test_size
            model.fit(X[:train_end], y[:train_end])
            y_pred = model.predict(X[train_end:])
            mae_test = float(np.mean(np.abs(y[train_end:] - y_pred)))
            denom = np.maximum(y[train_end:], y_pred)
            denom = np.where(denom == 0, 1.0, denom)
            accuracy = float(
                (1 - np.mean(np.abs(y[train_end:] - y_pred) / denom)) * 100
            )

        model.fit(X, y)
        buf = io.BytesIO()
        joblib.dump(model, buf)
        model_blob = buf.getvalue()

        await self._ml_models_repo.save_model(
            dish_id=dish_id,
            dish_name=dish_name,
            model_blob=model_blob,
            metrics={
                "mae_test": round(mae_test, 2),
                "accuracy_pct": round(accuracy, 1),
                "samples": len(y),
                "test_size": test_size,
            },
            feature_names=self.feature_names,
            samples_count=nonzero,
            granularity=self.granularity,
        )
        logger.info(
            "%s model trained for %s: MAE=%.2f, acc=%.1f%%, samples=%d",
            self.granularity, dish_name, mae_test, accuracy, len(y),
        )
        return accuracy

    async def _cleanup_obsolete_models(self, active_ids: set[str]) -> None:
        existing_models = await self._ml_models_repo.get_all_models(
            granularity=self.granularity,
        )
        for model in existing_models:
            if model.dish_id not in active_ids:
                await self._ml_models_repo.delete_models(
                    model.dish_id, granularity=self.granularity,
                )
                logger.info(
                    "%s cleanup: removed model for obsolete dish %s (%s)",
                    self.granularity, model.dish_name, model.dish_id,
                )

    async def predict_dish(
        self,
        dish_id: str,
        dish_name: str,
        target_date: datetime.date,
        *,
        weather: DailyWeather | dict[datetime.date, DailyWeather] | None,
        total_daily_sales: dict[datetime.date, float] | None = None,
    ) -> tuple[float, str]:
        window = self._training_window(target_date)
        by_id = await self._sales_repo.get_sales_by_dish(
            dish_id, window.date_from, window.date_to,
        )
        by_name = await self._sales_repo.get_sales_by_dish_name(
            dish_name, window.date_from, window.date_to,
        )
        sales = by_name or by_id

        fallback = self._fallback(sales, target_date)

        model_record = await self._ml_models_repo.get_latest_model(
            dish_id, dish_name, granularity=self.granularity,
        )
        if (
            model_record is not None
            and model_record.feature_names != self.feature_names
        ):
            logger.info(
                "%s: skipping stale model for %s (feature drift)",
                self.granularity, dish_name,
            )
            model_record = None

        if model_record is not None:
            try:
                model = joblib.load(io.BytesIO(model_record.model_blob))
                features = self._build_prediction_features(
                    target_date, by_id, weather, total_daily_sales,
                )
                prediction = float(model.predict(features)[0])
                return max(0.0, prediction), "ml"
            except Exception:
                logger.warning(
                    "%s ML prediction failed for %s, using fallback",
                    self.granularity, dish_name, exc_info=True,
                )

        return fallback, "fallback"
