"""Weekly forecaster — HistGradientBoostingRegressor over 16 weekly features."""
from __future__ import annotations

import datetime
from typing import Any

import numpy as np
import pandas as pd

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.services.features_weekly import (
    WEEKLY_CATEGORICAL_FEATURES,
    WEEKLY_FEATURE_NAMES,
    build_weekly_features_dataframe,
    build_weekly_prediction_features,
)
from app.services.forecasters.base import BaseForecaster


class WeeklyForecaster(BaseForecaster):
    granularity = "weekly"

    @property
    def max_history_months(self) -> int:
        return self._settings.weekly_max_history_months

    @property
    def min_samples(self) -> int:
        return self._settings.weekly_min_samples

    @property
    def min_sales_pct(self) -> float:
        return self._settings.weekly_min_sales_pct

    @property
    def min_accuracy(self) -> float:
        return self._settings.weekly_min_accuracy

    @property
    def feature_names(self) -> list[str]:
        return WEEKLY_FEATURE_NAMES

    @property
    def categorical_features(self) -> list[int]:
        return WEEKLY_CATEGORICAL_FEATURES

    def _count_nonzero_samples(self, sales: list[SaleRecord]) -> int:
        weekly: dict[datetime.date, float] = {}
        for s in sales:
            monday = s.date - datetime.timedelta(days=s.date.weekday())
            weekly[monday] = weekly.get(monday, 0.0) + s.quantity
        return sum(1 for q in weekly.values() if q > 0)

    def _build_training_frame(
        self,
        sales: list[SaleRecord],
        weather_by_date: dict[datetime.date, DailyWeather],
        totals: dict[datetime.date, float],
    ) -> pd.DataFrame:
        return build_weekly_features_dataframe(sales, weather_by_date, totals)

    def _build_prediction_features(
        self,
        target_date: datetime.date,
        sales: list[SaleRecord],
        weather: DailyWeather | dict[datetime.date, DailyWeather] | None,
        totals: dict[datetime.date, float] | None,
    ) -> Any:
        week_start = target_date - datetime.timedelta(days=target_date.weekday())
        weather_dict: dict[datetime.date, DailyWeather]
        if isinstance(weather, dict):
            weather_dict = weather
        else:
            weather_dict = {}
        return build_weekly_prediction_features(
            week_start, sales, weather_dict, totals,
        )

    def _fallback(
        self, sales: list[SaleRecord], target_date: datetime.date,
    ) -> float:
        week_start = target_date - datetime.timedelta(days=target_date.weekday())
        weekly_totals: dict[datetime.date, float] = {}
        for s in sales:
            monday = s.date - datetime.timedelta(days=s.date.weekday())
            weekly_totals[monday] = weekly_totals.get(monday, 0.0) + s.quantity
        prev_4w = [
            weekly_totals.get(week_start - datetime.timedelta(days=7 * i), 0.0)
            for i in range(1, 5)
        ]
        return float(np.mean(prev_4w)) if any(v > 0 for v in prev_4w) else 0.0

    def _model_params(self) -> dict[str, Any]:
        return {
            "loss": "poisson",
            "max_iter": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "min_samples_leaf": 3,
        }

    def _min_rows_for_cv(self) -> int:
        return 16
