"""Weekly feature engineering for ML forecast models."""
import datetime

import numpy as np
import pandas as pd

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.utils.calendar import get_calendar_context

WEEKLY_FEATURE_NAMES = [
    "week_of_year",                # 0  (categorical)
    "month",                       # 1  (categorical)
    "has_holiday",                 # 2  (categorical)
    "weekend_days",                # 3
    "temp_avg_week",               # 4
    "precip_sum_week",             # 5
    "lag_1w",                      # 6
    "lag_2w",                      # 7
    "lag_4w",                      # 8
    "rolling_avg_4w",              # 9
    "rolling_std_4w",              # 10
    "trend_4w",                    # 11
    "total_restaurant_prev_week",  # 12
    "sin_week_of_year",            # 13
    "cos_week_of_year",            # 14
    "is_payday_week",              # 15 (categorical)
]

WEEKLY_CATEGORICAL_FEATURES = [0, 1, 2, 15]


def _monday(d: datetime.date) -> datetime.date:
    """Return Monday of the week containing date d."""
    return d - datetime.timedelta(days=d.weekday())


def _week_key(d: datetime.date) -> datetime.date:
    """Use Monday as the canonical key for a week."""
    return _monday(d)


def _week_weather(
    monday: datetime.date,
    weather_by_date: dict[datetime.date, DailyWeather],
) -> tuple[float, float]:
    """Return (avg_temp, total_precip) for the week starting at monday."""
    temps, precips = [], []
    for offset in range(7):
        d = monday + datetime.timedelta(days=offset)
        w = weather_by_date.get(d)
        if w:
            temps.append(w.temp_avg)
            precips.append(w.precipitation)
    avg_temp = float(np.mean(temps)) if temps else np.nan
    total_precip = float(np.sum(precips)) if precips else np.nan
    return avg_temp, total_precip


def _week_calendar(monday: datetime.date) -> tuple[int, int]:
    """Return (has_holiday, weekend_days) for the week."""
    has_holiday = 0
    weekend_days = 0
    for offset in range(7):
        d = monday + datetime.timedelta(days=offset)
        cal = get_calendar_context(d)
        if cal["is_holiday"]:
            has_holiday = 1
        if cal["is_day_off"]:
            weekend_days += 1
    return has_holiday, weekend_days


def _is_payday_week(monday: datetime.date) -> int:
    """Week contains payday days (25-31 or 1-5)."""
    for offset in range(7):
        day = (monday + datetime.timedelta(days=offset)).day
        if day >= 25 or day <= 5:
            return 1
    return 0


def build_weekly_features_dataframe(
    dish_sales: list[SaleRecord],
    weather_by_date: dict[datetime.date, DailyWeather],
    total_daily_sales: dict[datetime.date, float] | None = None,
) -> pd.DataFrame:
    """Build weekly feature matrix for a single dish."""
    if not dish_sales:
        return pd.DataFrame(columns=WEEKLY_FEATURE_NAMES + ["target"])

    # Aggregate daily sales into weekly totals
    weekly: dict[datetime.date, float] = {}
    for s in dish_sales:
        wk = _week_key(s.date)
        weekly[wk] = weekly.get(wk, 0) + s.quantity

    if not weekly:
        return pd.DataFrame(columns=WEEKLY_FEATURE_NAMES + ["target"])

    # Build continuous week range
    all_mondays = sorted(weekly.keys())
    first_monday = all_mondays[0]
    last_monday = all_mondays[-1]

    weeks: list[datetime.date] = []
    current = first_monday
    while current <= last_monday:
        weeks.append(current)
        current += datetime.timedelta(days=7)

    # Weekly quantity series (fill missing weeks with 0)
    qty_series = [weekly.get(m, 0.0) for m in weeks]

    # Weekly restaurant totals
    total_weekly: dict[datetime.date, float] = {}
    if total_daily_sales:
        for d, qty in total_daily_sales.items():
            wk = _week_key(d)
            total_weekly[wk] = total_weekly.get(wk, 0) + qty

    rows = []
    for i, monday in enumerate(weeks):
        iso = monday.isocalendar()
        has_holiday, weekend_days = _week_calendar(monday)
        temp_avg, precip_sum = _week_weather(monday, weather_by_date)

        # Lag features
        lag_1w = qty_series[i - 1] if i >= 1 else np.nan
        lag_2w = qty_series[i - 2] if i >= 2 else np.nan
        lag_4w = qty_series[i - 4] if i >= 4 else np.nan

        # Rolling stats (4 weeks)
        past_4 = qty_series[max(0, i - 4):i]
        rolling_avg = float(np.mean(past_4)) if past_4 else np.nan
        rolling_std = float(np.std(past_4)) if len(past_4) >= 2 else np.nan

        # Trend (slope over last 4 weeks)
        trend = np.nan
        if len(past_4) >= 2:
            x = np.arange(len(past_4))
            trend = float(np.polyfit(x, past_4, 1)[0])

        # Restaurant total prev week
        prev_monday = monday - datetime.timedelta(days=7)
        total_prev = total_weekly.get(prev_monday, np.nan)

        # Seasonality
        woy = iso[1]
        sin_woy = np.sin(2 * np.pi * woy / 52)
        cos_woy = np.cos(2 * np.pi * woy / 52)

        rows.append({
            "week_of_year": woy,
            "month": monday.month,
            "has_holiday": has_holiday,
            "weekend_days": weekend_days,
            "temp_avg_week": temp_avg,
            "precip_sum_week": precip_sum,
            "lag_1w": lag_1w,
            "lag_2w": lag_2w,
            "lag_4w": lag_4w,
            "rolling_avg_4w": rolling_avg,
            "rolling_std_4w": rolling_std,
            "trend_4w": trend,
            "total_restaurant_prev_week": total_prev,
            "sin_week_of_year": sin_woy,
            "cos_week_of_year": cos_woy,
            "is_payday_week": _is_payday_week(monday),
            "target": qty_series[i],
        })

    return pd.DataFrame(rows)


def build_weekly_prediction_features(
    target_week_start: datetime.date,
    dish_sales: list[SaleRecord],
    weather_by_date: dict[datetime.date, DailyWeather],
    total_daily_sales: dict[datetime.date, float] | None = None,
) -> np.ndarray | None:
    """Build feature vector for predicting a single week."""
    monday = _monday(target_week_start)
    iso = monday.isocalendar()

    # Historical weekly aggregation
    weekly: dict[datetime.date, float] = {}
    for s in dish_sales:
        wk = _week_key(s.date)
        weekly[wk] = weekly.get(wk, 0) + s.quantity

    # Calendar
    has_holiday, weekend_days = _week_calendar(monday)

    # Weather
    temp_avg, precip_sum = _week_weather(monday, weather_by_date)

    # Lags
    prev_weeks = []
    for offset in range(1, 5):
        prev = monday - datetime.timedelta(days=7 * offset)
        prev_weeks.append(weekly.get(prev, 0.0))

    lag_1w = prev_weeks[0] if len(prev_weeks) >= 1 else np.nan
    lag_2w = prev_weeks[1] if len(prev_weeks) >= 2 else np.nan
    lag_4w = prev_weeks[3] if len(prev_weeks) >= 4 else np.nan

    rolling_avg = float(np.mean(prev_weeks)) if prev_weeks else np.nan
    rolling_std = float(np.std(prev_weeks)) if len(prev_weeks) >= 2 else np.nan

    trend = np.nan
    if len(prev_weeks) >= 2:
        x = np.arange(len(prev_weeks))
        trend = float(np.polyfit(x, list(reversed(prev_weeks)), 1)[0])

    # Restaurant total prev week
    total_prev = np.nan
    if total_daily_sales:
        prev_monday = monday - datetime.timedelta(days=7)
        total_prev = sum(
            total_daily_sales.get(prev_monday + datetime.timedelta(days=d), 0)
            for d in range(7)
        )
        if total_prev == 0:
            total_prev = np.nan

    # Seasonality
    woy = iso[1]
    sin_woy = np.sin(2 * np.pi * woy / 52)
    cos_woy = np.cos(2 * np.pi * woy / 52)

    features = np.array([
        woy,
        monday.month,
        has_holiday,
        weekend_days,
        temp_avg,
        precip_sum,
        lag_1w,
        lag_2w,
        lag_4w,
        rolling_avg,
        rolling_std,
        trend,
        total_prev,
        sin_woy,
        cos_woy,
        _is_payday_week(monday),
    ], dtype=np.float64).reshape(1, -1)

    return features
