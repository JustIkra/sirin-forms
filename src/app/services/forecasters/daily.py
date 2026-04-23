"""Daily forecaster — HistGradientBoostingRegressor over 31 daily features."""
from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.services.features import (
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    build_features_dataframe,
    build_prediction_features,
)
from app.services.forecasters.base import BaseForecaster


class DailyForecaster(BaseForecaster):
    granularity = "daily"

    @property
    def max_history_months(self) -> int:
        return self._settings.daily_max_history_months

    @property
    def min_samples(self) -> int:
        return self._settings.daily_min_samples

    @property
    def min_sales_pct(self) -> float:
        return self._settings.daily_min_sales_pct

    @property
    def min_accuracy(self) -> float:
        return self._settings.daily_min_accuracy

    @property
    def feature_names(self) -> list[str]:
        return FEATURE_NAMES

    @property
    def categorical_features(self) -> list[int]:
        return CATEGORICAL_FEATURES

    def _count_nonzero_samples(self, sales: list[SaleRecord]) -> int:
        daily: dict[datetime.date, float] = {}
        for s in sales:
            daily[s.date] = daily.get(s.date, 0.0) + s.quantity
        return sum(1 for q in daily.values() if q > 0)

    def _build_training_frame(
        self,
        sales: list[SaleRecord],
        weather_by_date: dict[datetime.date, DailyWeather],
        totals: dict[datetime.date, float],
    ) -> pd.DataFrame:
        return build_features_dataframe(sales, weather_by_date, totals)

    def _build_prediction_features(
        self,
        target_date: datetime.date,
        sales: list[SaleRecord],
        weather: DailyWeather | dict[datetime.date, DailyWeather] | None,
        totals: dict[datetime.date, float] | None,
    ) -> Any:
        weather_for_day: DailyWeather | None
        if isinstance(weather, dict):
            weather_for_day = weather.get(target_date)
        else:
            weather_for_day = weather
        return build_prediction_features(
            target_date, sales, weather_for_day, totals,
        )

    def _fallback(
        self, sales: list[SaleRecord], target_date: datetime.date,
    ) -> float:
        daily: dict[datetime.date, float] = {}
        for s in sales:
            daily[s.date] = daily.get(s.date, 0.0) + s.quantity

        same_wd: list[float] = []
        for week in range(1, 5):
            d = target_date - datetime.timedelta(weeks=week)
            if d in daily:
                same_wd.append(daily[d])
        if same_wd:
            return float(np.mean(same_wd))

        cutoff = target_date - datetime.timedelta(days=30)
        recent = {d: q for d, q in daily.items() if d >= cutoff}
        if recent:
            return float(np.median(list(recent.values())))

        return 0.0

    def _model_params(self) -> dict[str, Any]:
        return {
            "loss": "poisson",
            "max_iter": 800,
            "max_depth": 6,
            "learning_rate": 0.03,
            "min_samples_leaf": 10,
            "l2_regularization": 0.5,
            "early_stopping": True,
            "n_iter_no_change": 30,
            "validation_fraction": 0.15,
            "tol": 1e-4,
            "random_state": 42,
        }

    def _min_rows_for_cv(self) -> int:
        return 30
