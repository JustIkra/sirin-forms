import datetime

import numpy as np
import pandas as pd

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.utils.calendar import get_calendar_context

FEATURE_NAMES = [
    "day_of_week",     # 0-6 (categorical)
    "month",           # 1-12 (categorical)
    "week_of_year",    # 1-53
    "is_weekend",      # 0/1 (categorical)
    "is_holiday",      # 0/1 (categorical)
    "is_pre_holiday",  # 0/1 (categorical)
    "is_day_off",      # 0/1 (categorical) — weekend OR holiday OR transfer
    "temp_avg",        # float
    "precipitation",   # float
    "humidity",        # float
    "wind_speed",      # float
    "rolling_avg_7d",  # float
    "rolling_avg_30d", # float
    "same_weekday_avg_4w",  # float
    "day_of_month",    # 1-31
    "is_payday_period",  # 0/1 (categorical) — days 25-31 and 1-5
    "trend_7d",        # float — slope of sales over last 7 days
    "days_since_last_sale",  # int — days since last non-zero sale, capped at 30
    "total_restaurant_sales_7d_avg",  # float — average total restaurant traffic over 7 days
]

# day_of_week, month, is_weekend, is_holiday, is_pre_holiday, is_day_off, is_payday_period
CATEGORICAL_FEATURES = [0, 1, 3, 4, 5, 6, 15]


def build_features_dataframe(
    dish_sales: list[SaleRecord],
    weather_by_date: dict[datetime.date, DailyWeather],
    total_daily_sales: dict[datetime.date, float] | None = None,
) -> pd.DataFrame:
    """Build feature matrix from sales history for a single dish."""
    if not dish_sales:
        return pd.DataFrame(columns=FEATURE_NAMES + ["target"])

    # Sort by date and aggregate quantities per day
    daily: dict[datetime.date, float] = {}
    for s in dish_sales:
        daily[s.date] = daily.get(s.date, 0) + s.quantity

    dates = sorted(daily.keys())
    if not dates:
        return pd.DataFrame(columns=FEATURE_NAMES + ["target"])

    # Build continuous date range
    date_range = pd.date_range(start=dates[0], end=dates[-1], freq="D")
    qty_series = pd.Series(
        [daily.get(d.date(), 0.0) for d in date_range],
        index=date_range,
    )

    rows = []
    for i, dt in enumerate(date_range):
        d = dt.date()
        cal = get_calendar_context(d)
        w = weather_by_date.get(d)

        # Lag features (no data leakage — uses only past data)
        past_7 = qty_series.iloc[max(0, i - 7):i]
        past_30 = qty_series.iloc[max(0, i - 30):i]

        # Same weekday average (last 4 weeks)
        same_wd_indices = [i - 7 * k for k in range(1, 5) if i - 7 * k >= 0]
        same_wd_vals = [qty_series.iloc[j] for j in same_wd_indices] if same_wd_indices else []

        # Trend: slope of last 7 days
        trend_7d = np.nan
        if len(past_7) >= 2:
            x = np.arange(len(past_7))
            trend_7d = float(np.polyfit(x, past_7.values, 1)[0])

        # Days since last non-zero sale
        days_since = 30  # cap
        for j in range(1, min(i + 1, 31)):
            if qty_series.iloc[i - j] > 0:
                days_since = j
                break

        # Total restaurant sales 7d average
        total_7d_avg = np.nan
        if total_daily_sales:
            total_vals = []
            for offset in range(1, 8):
                prev = d - datetime.timedelta(days=offset)
                if prev in total_daily_sales:
                    total_vals.append(total_daily_sales[prev])
            if total_vals:
                total_7d_avg = float(np.mean(total_vals))

        rows.append({
            "day_of_week": d.weekday(),
            "month": d.month,
            "week_of_year": d.isocalendar()[1],
            "is_weekend": 1 if cal["is_weekend"] else 0,
            "is_holiday": 1 if cal["is_holiday"] else 0,
            "is_pre_holiday": 1 if cal["is_pre_holiday"] else 0,
            "is_day_off": 1 if cal.get("is_day_off", cal["is_weekend"] or cal["is_holiday"]) else 0,
            "temp_avg": w.temp_avg if w else np.nan,
            "precipitation": w.precipitation if w else np.nan,
            "humidity": float(w.humidity) if w and w.humidity is not None else np.nan,
            "wind_speed": w.wind_speed if w and w.wind_speed is not None else np.nan,
            "rolling_avg_7d": past_7.mean() if len(past_7) > 0 else np.nan,
            "rolling_avg_30d": past_30.mean() if len(past_30) > 0 else np.nan,
            "same_weekday_avg_4w": np.mean(same_wd_vals) if same_wd_vals else np.nan,
            "day_of_month": d.day,
            "is_payday_period": 1 if d.day >= 25 or d.day <= 5 else 0,
            "trend_7d": trend_7d,
            "days_since_last_sale": days_since,
            "total_restaurant_sales_7d_avg": total_7d_avg,
            "target": qty_series.iloc[i],
        })

    return pd.DataFrame(rows)


def build_prediction_features(
    target_date: datetime.date,
    dish_sales: list[SaleRecord],
    weather: DailyWeather | None,
    total_daily_sales: dict[datetime.date, float] | None = None,
) -> np.ndarray | None:
    """Build feature vector for a single prediction date."""
    cal = get_calendar_context(target_date)

    # Calculate lag features from historical sales
    daily: dict[datetime.date, float] = {}
    for s in dish_sales:
        daily[s.date] = daily.get(s.date, 0) + s.quantity

    # Rolling averages (past data only)
    recent_7 = []
    recent_30 = []
    same_wd = []
    for offset in range(1, 31):
        d = target_date - datetime.timedelta(days=offset)
        qty = daily.get(d, 0.0)
        if offset <= 7:
            recent_7.append(qty)
        recent_30.append(qty)
        if d.weekday() == target_date.weekday() and offset <= 28:
            same_wd.append(qty)

    # Trend: slope of last 7 days
    trend_7d = np.nan
    if len(recent_7) >= 2:
        x = np.arange(len(recent_7))
        trend_7d = float(np.polyfit(x, recent_7, 1)[0])

    # Days since last non-zero sale
    days_since = 30
    for offset in range(1, 31):
        d = target_date - datetime.timedelta(days=offset)
        if daily.get(d, 0.0) > 0:
            days_since = offset
            break

    # Total restaurant sales 7d average
    total_7d_avg = np.nan
    if total_daily_sales:
        total_vals = []
        for offset in range(1, 8):
            prev = target_date - datetime.timedelta(days=offset)
            if prev in total_daily_sales:
                total_vals.append(total_daily_sales[prev])
        if total_vals:
            total_7d_avg = float(np.mean(total_vals))

    features = np.array([
        target_date.weekday(),
        target_date.month,
        target_date.isocalendar()[1],
        1 if cal["is_weekend"] else 0,
        1 if cal["is_holiday"] else 0,
        1 if cal["is_pre_holiday"] else 0,
        1 if cal.get("is_day_off", cal["is_weekend"] or cal["is_holiday"]) else 0,
        weather.temp_avg if weather else np.nan,
        weather.precipitation if weather else np.nan,
        float(weather.humidity) if weather and weather.humidity is not None else np.nan,
        weather.wind_speed if weather and weather.wind_speed is not None else np.nan,
        np.mean(recent_7) if recent_7 else np.nan,
        np.mean(recent_30) if recent_30 else np.nan,
        np.mean(same_wd) if same_wd else np.nan,
        target_date.day,
        1 if target_date.day >= 25 or target_date.day <= 5 else 0,
        trend_7d,
        days_since,
        total_7d_avg,
    ], dtype=np.float64).reshape(1, -1)

    return features
