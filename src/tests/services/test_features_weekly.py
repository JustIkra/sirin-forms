"""Юнит-тесты для app.services.features_weekly — недельные признаки ML-модели."""
import datetime

import numpy as np
import pytest

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.services.features_weekly import (
    WEEKLY_CATEGORICAL_FEATURES,
    WEEKLY_FEATURE_NAMES,
    build_weekly_features_dataframe,
    build_weekly_prediction_features,
)


def _make_sale(
    date: datetime.date, quantity: float = 10, dish_id: str = "d1",
) -> SaleRecord:
    return SaleRecord(
        date=date,
        dish_id=dish_id,
        dish_name="Борщ",
        quantity=quantity,
        price=350.0,
        total=quantity * 350.0,
    )


def _make_weather(date: datetime.date, temp: float = 5.0, precip: float = 0.0) -> DailyWeather:
    return DailyWeather(
        date=date,
        temp_min=temp - 3,
        temp_max=temp + 3,
        temp_avg=temp,
        precipitation=precip,
        weather_main="Clear",
        humidity=65,
        wind_speed=3.0,
    )


class TestWeeklyFeatureNames:
    def test_sixteen_features(self):
        assert len(WEEKLY_FEATURE_NAMES) == 16

    def test_expected_features_present(self):
        expected = {
            "week_of_year", "month", "has_holiday", "weekend_days",
            "temp_avg_week", "precip_sum_week",
            "lag_1w", "lag_2w", "lag_4w",
            "rolling_avg_4w", "rolling_std_4w", "trend_4w",
            "total_restaurant_prev_week",
            "sin_week_of_year", "cos_week_of_year", "is_payday_week",
        }
        assert set(WEEKLY_FEATURE_NAMES) == expected

    def test_categorical_indices_valid(self):
        # Все индексы должны быть в пределах массива признаков
        for idx in WEEKLY_CATEGORICAL_FEATURES:
            assert 0 <= idx < len(WEEKLY_FEATURE_NAMES)


class TestBuildWeeklyPredictionFeatures:
    def test_returns_correct_shape(self):
        monday = datetime.date(2026, 4, 13)  # понедельник
        features = build_weekly_prediction_features(monday, [], {})
        assert features.shape == (1, 16)

    def test_all_float_dtype(self):
        monday = datetime.date(2026, 4, 13)
        features = build_weekly_prediction_features(monday, [], {})
        assert features.dtype == np.float64

    def test_week_of_year_filled(self):
        monday = datetime.date(2026, 4, 13)
        features = build_weekly_prediction_features(monday, [], {})
        woy_idx = WEEKLY_FEATURE_NAMES.index("week_of_year")
        assert features[0, woy_idx] == monday.isocalendar()[1]

    def test_month_filled(self):
        monday = datetime.date(2026, 4, 13)
        features = build_weekly_prediction_features(monday, [], {})
        month_idx = WEEKLY_FEATURE_NAMES.index("month")
        assert features[0, month_idx] == 4

    def test_lag_1w_from_previous_week(self):
        """Прогноз на неделю с 13 апр — lag_1w должен быть продажи за неделю с 6 апр."""
        target_monday = datetime.date(2026, 4, 13)
        prev_monday = datetime.date(2026, 4, 6)  # -1 week
        sales = [
            _make_sale(prev_monday + datetime.timedelta(days=d), quantity=5)
            for d in range(7)
        ]  # 5*7 = 35
        features = build_weekly_prediction_features(target_monday, sales, {})
        lag_1w_idx = WEEKLY_FEATURE_NAMES.index("lag_1w")
        assert features[0, lag_1w_idx] == 35.0

    def test_lag_2w_from_two_weeks_ago(self):
        target_monday = datetime.date(2026, 4, 13)
        two_weeks_ago = datetime.date(2026, 3, 30)
        sales = [_make_sale(two_weeks_ago, quantity=50)]
        features = build_weekly_prediction_features(target_monday, sales, {})
        lag_2w_idx = WEEKLY_FEATURE_NAMES.index("lag_2w")
        assert features[0, lag_2w_idx] == 50.0

    def test_lag_4w_from_four_weeks_ago(self):
        target_monday = datetime.date(2026, 4, 13)
        four_weeks_ago = datetime.date(2026, 3, 16)
        sales = [_make_sale(four_weeks_ago, quantity=77)]
        features = build_weekly_prediction_features(target_monday, sales, {})
        lag_4w_idx = WEEKLY_FEATURE_NAMES.index("lag_4w")
        assert features[0, lag_4w_idx] == 77.0

    def test_rolling_avg_4w(self):
        target_monday = datetime.date(2026, 4, 13)
        # Продажи в 4-х предыдущих неделях: 10, 20, 30, 40
        sales = []
        for i, qty in enumerate([10, 20, 30, 40], start=1):
            sales.append(
                _make_sale(target_monday - datetime.timedelta(days=7 * i), quantity=qty)
            )
        features = build_weekly_prediction_features(target_monday, sales, {})
        avg_idx = WEEKLY_FEATURE_NAMES.index("rolling_avg_4w")
        assert features[0, avg_idx] == 25.0  # mean(10, 20, 30, 40)

    def test_total_restaurant_prev_week(self):
        target_monday = datetime.date(2026, 4, 13)
        prev_monday = datetime.date(2026, 4, 6)
        total_daily = {
            prev_monday + datetime.timedelta(days=d): 100.0 for d in range(7)
        }
        features = build_weekly_prediction_features(
            target_monday, [], {}, total_daily_sales=total_daily,
        )
        total_idx = WEEKLY_FEATURE_NAMES.index("total_restaurant_prev_week")
        assert features[0, total_idx] == 700.0

    def test_seasonality_sin_cos_range(self):
        """sin и cos должны быть в [-1, 1]."""
        target_monday = datetime.date(2026, 4, 13)
        features = build_weekly_prediction_features(target_monday, [], {})
        sin_idx = WEEKLY_FEATURE_NAMES.index("sin_week_of_year")
        cos_idx = WEEKLY_FEATURE_NAMES.index("cos_week_of_year")
        assert -1.0 <= features[0, sin_idx] <= 1.0
        assert -1.0 <= features[0, cos_idx] <= 1.0

    def test_monday_normalization(self):
        """Target-дата не в понедельник → фичи должны считаться как для понедельника этой недели."""
        wednesday = datetime.date(2026, 4, 15)  # среда
        monday = datetime.date(2026, 4, 13)
        f_wed = build_weekly_prediction_features(wednesday, [], {})
        f_mon = build_weekly_prediction_features(monday, [], {})
        # Результаты должны совпадать — функция нормализует к понедельнику
        np.testing.assert_array_equal(f_wed, f_mon)

    def test_weather_aggregation(self):
        """temp_avg_week должен усредняться по 7 дням недели."""
        monday = datetime.date(2026, 4, 13)
        weather_by_date = {
            monday + datetime.timedelta(days=d): _make_weather(monday, temp=10.0)
            for d in range(7)
        }
        features = build_weekly_prediction_features(monday, [], weather_by_date)
        temp_idx = WEEKLY_FEATURE_NAMES.index("temp_avg_week")
        assert features[0, temp_idx] == 10.0

    def test_no_weather_returns_nan(self):
        monday = datetime.date(2026, 4, 13)
        features = build_weekly_prediction_features(monday, [], {})
        temp_idx = WEEKLY_FEATURE_NAMES.index("temp_avg_week")
        assert np.isnan(features[0, temp_idx])


class TestIsPaydayWeek:
    def test_week_with_day_25(self):
        # Неделя с 20-26 апр содержит 25-е → payday
        monday = datetime.date(2026, 4, 20)
        features = build_weekly_prediction_features(monday, [], {})
        idx = WEEKLY_FEATURE_NAMES.index("is_payday_week")
        assert features[0, idx] == 1

    def test_ordinary_week(self):
        # Неделя с 6-12 апр не содержит 25+ или 1-5 → not payday
        monday = datetime.date(2026, 4, 6)
        features = build_weekly_prediction_features(monday, [], {})
        idx = WEEKLY_FEATURE_NAMES.index("is_payday_week")
        assert features[0, idx] == 0

    def test_week_with_day_1_to_5(self):
        # Неделя с 30 мар — 5 апр содержит 1-5 апр → payday
        monday = datetime.date(2026, 3, 30)
        features = build_weekly_prediction_features(monday, [], {})
        idx = WEEKLY_FEATURE_NAMES.index("is_payday_week")
        assert features[0, idx] == 1


class TestBuildWeeklyFeaturesDataframe:
    def test_empty_sales_returns_empty_dataframe(self):
        df = build_weekly_features_dataframe([], {}, None)
        assert df.empty
        for col in WEEKLY_FEATURE_NAMES:
            assert col in df.columns
        assert "target" in df.columns

    def test_one_week_of_sales(self):
        monday = datetime.date(2026, 4, 13)
        sales = [_make_sale(monday, quantity=100)]
        df = build_weekly_features_dataframe(sales, {}, None)
        assert len(df) == 1
        assert df.iloc[0]["target"] == 100.0

    def test_aggregates_daily_sales_into_weekly(self):
        """Продажи в разные дни одной недели должны суммироваться."""
        monday = datetime.date(2026, 4, 13)
        sales = [
            _make_sale(monday, quantity=10),
            _make_sale(monday + datetime.timedelta(days=1), quantity=15),
            _make_sale(monday + datetime.timedelta(days=2), quantity=25),
        ]
        df = build_weekly_features_dataframe(sales, {}, None)
        assert len(df) == 1  # одна неделя
        assert df.iloc[0]["target"] == 50.0  # 10+15+25

    def test_multiple_weeks_produce_multiple_rows(self):
        monday1 = datetime.date(2026, 4, 6)
        monday2 = datetime.date(2026, 4, 13)
        sales = [
            _make_sale(monday1, quantity=10),
            _make_sale(monday2, quantity=20),
        ]
        df = build_weekly_features_dataframe(sales, {}, None)
        assert len(df) == 2

    def test_target_column_matches_weekly_qty(self):
        monday = datetime.date(2026, 4, 13)
        sales = [_make_sale(monday + datetime.timedelta(days=i), quantity=7) for i in range(7)]
        df = build_weekly_features_dataframe(sales, {}, None)
        assert df.iloc[0]["target"] == 49.0  # 7 * 7

    def test_lag_features_for_first_week_are_nan(self):
        """Для первой недели в истории не должно быть лагов."""
        monday = datetime.date(2026, 4, 13)
        sales = [_make_sale(monday, quantity=10)]
        df = build_weekly_features_dataframe(sales, {}, None)
        assert np.isnan(df.iloc[0]["lag_1w"])
