import datetime

import numpy as np
import pandas as pd

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.utils.calendar import get_calendar_context

FEATURE_NAMES = [
    "day_of_week",     # 0  (categorical)
    "month",           # 1  (categorical)
    "week_of_year",    # 2
    "is_weekend",      # 3  (categorical)
    "is_holiday",      # 4  (categorical)
    "is_pre_holiday",  # 5  (categorical)
    "is_day_off",      # 6  (categorical) — weekend OR holiday OR transfer
    "temp_avg",        # 7
    "precipitation",   # 8
    "humidity",        # 9
    "wind_speed",      # 10
    "rolling_avg_7d",  # 11
    "rolling_avg_30d", # 12
    "same_weekday_avg_4w",  # 13
    "day_of_month",    # 14
    "is_payday_period",  # 15 (categorical) — days 25-31 and 1-5
    "trend_7d",        # 16 — slope of sales over last 7 days
    "days_since_last_sale",  # 17 — capped at 30
    "total_restaurant_sales_7d_avg",  # 18
    "lag_1d",          # 19 — sales yesterday
    "lag_7d",          # 20 — sales 7 days ago
    "lag_14d",         # 21 — sales 14 days ago
    "rolling_std_7d",  # 22 — volatility over last 7 days
    "cv_30d",          # 23 — coefficient of variation over 30 days
    "sin_day_of_year", # 24 — yearly seasonality (sin)
    "cos_day_of_year", # 25 — yearly seasonality (cos)
    "sin_day_of_week", # 26 — weekly seasonality (sin)
    "cos_day_of_week", # 27 — weekly seasonality (cos)
    "weather_category",  # 28 (categorical) — 0=clear,1=clouds,2=rain,3=snow,4=other
    "temp_x_weekend",    # 29 — interaction: temp_avg * is_weekend
    "precip_x_weekend",  # 30 — interaction: precipitation * is_weekend
    "lag_21d",          # 31 — sales 21 days ago (monthly cycle)
    "lag_28d",          # 32 — sales 28 days ago (4-week cycle, same weekday)
    "rolling_avg_14d",  # 33 — 2-week baseline
    "rolling_avg_60d",  # 34 — 2-month baseline (stable long-term average)
    "density_30d",      # 35 — share of non-zero days in last 30 (regularity signal)
    "total_restaurant_sales_1d",  # 36 — yesterday's restaurant-wide sales (strong lead)
    "same_weekday_max_4w",  # 37 — max of last 4 same-weekday sales (peak reference)
]

# day_of_week, month, is_weekend, is_holiday, is_pre_holiday, is_day_off, is_payday_period, weather_category
CATEGORICAL_FEATURES = [0, 1, 3, 4, 5, 6, 15, 28]

_WEATHER_CATEGORY_MAP = {
    "Clear": 0, "Clouds": 1, "Rain": 2, "Drizzle": 2,
    "Thunderstorm": 2, "Snow": 3, "Mist": 4, "Fog": 4,
    "Haze": 4, "Smoke": 4, "Dust": 4, "Sand": 4,
    "Ash": 4, "Squall": 4, "Tornado": 4,
}


def _weather_cat(w) -> float:
    if w is None:
        return np.nan
    key = w.weather_main or w.weather_description or ""
    return float(_WEATHER_CATEGORY_MAP.get(key, 4))


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

        # Lag features (strictly past)
        lag_1d = qty_series.iloc[i - 1] if i >= 1 else np.nan
        lag_7d = qty_series.iloc[i - 7] if i >= 7 else np.nan
        lag_14d = qty_series.iloc[i - 14] if i >= 14 else np.nan
        lag_21d = qty_series.iloc[i - 21] if i >= 21 else np.nan
        lag_28d = qty_series.iloc[i - 28] if i >= 28 else np.nan

        # Additional rolling windows
        past_14 = qty_series.iloc[max(0, i - 14):i]
        past_60 = qty_series.iloc[max(0, i - 60):i]

        # Density: share of non-zero days in last 30d (regularity signal)
        density_30d = (
            float((past_30 > 0).mean()) if len(past_30) > 0 else np.nan
        )

        # Same-weekday maximum (peak reference — catches recent uptrends)
        same_wd_max = float(np.max(same_wd_vals)) if same_wd_vals else np.nan

        # Volatility
        rolling_std = float(past_7.std()) if len(past_7) >= 2 else np.nan
        mean_30 = past_30.mean() if len(past_30) > 0 else np.nan
        std_30 = float(past_30.std()) if len(past_30) >= 2 else np.nan
        cv_30d = (std_30 / mean_30) if mean_30 and mean_30 > 0 and not np.isnan(std_30) else np.nan

        # Yesterday's restaurant-wide total (strong same-phase demand signal)
        total_1d = np.nan
        if total_daily_sales:
            prev = d - datetime.timedelta(days=1)
            if prev in total_daily_sales:
                total_1d = float(total_daily_sales[prev])

        # Cyclic seasonality
        doy = d.timetuple().tm_yday
        sin_doy = np.sin(2 * np.pi * doy / 365.25)
        cos_doy = np.cos(2 * np.pi * doy / 365.25)
        sin_dow = np.sin(2 * np.pi * d.weekday() / 7)
        cos_dow = np.cos(2 * np.pi * d.weekday() / 7)

        # Weather category & interactions
        w_cat = _weather_cat(w)
        is_we = 1 if cal["is_weekend"] else 0
        temp = w.temp_avg if w else np.nan
        precip = w.precipitation if w else np.nan

        rows.append({
            "day_of_week": d.weekday(),
            "month": d.month,
            "week_of_year": d.isocalendar()[1],
            "is_weekend": is_we,
            "is_holiday": 1 if cal["is_holiday"] else 0,
            "is_pre_holiday": 1 if cal["is_pre_holiday"] else 0,
            "is_day_off": 1 if cal.get("is_day_off", cal["is_weekend"] or cal["is_holiday"]) else 0,
            "temp_avg": temp,
            "precipitation": precip,
            "humidity": float(w.humidity) if w and w.humidity is not None else np.nan,
            "wind_speed": w.wind_speed if w and w.wind_speed is not None else np.nan,
            "rolling_avg_7d": past_7.mean() if len(past_7) > 0 else np.nan,
            "rolling_avg_30d": mean_30 if mean_30 is not None else np.nan,
            "same_weekday_avg_4w": np.mean(same_wd_vals) if same_wd_vals else np.nan,
            "day_of_month": d.day,
            "is_payday_period": 1 if d.day >= 25 or d.day <= 5 else 0,
            "trend_7d": trend_7d,
            "days_since_last_sale": days_since,
            "total_restaurant_sales_7d_avg": total_7d_avg,
            "lag_1d": lag_1d,
            "lag_7d": lag_7d,
            "lag_14d": lag_14d,
            "rolling_std_7d": rolling_std,
            "cv_30d": cv_30d,
            "sin_day_of_year": sin_doy,
            "cos_day_of_year": cos_doy,
            "sin_day_of_week": sin_dow,
            "cos_day_of_week": cos_dow,
            "weather_category": w_cat,
            "temp_x_weekend": (temp * is_we) if not np.isnan(temp) else np.nan,
            "precip_x_weekend": (precip * is_we) if not np.isnan(precip) else np.nan,
            "lag_21d": lag_21d,
            "lag_28d": lag_28d,
            "rolling_avg_14d": past_14.mean() if len(past_14) > 0 else np.nan,
            "rolling_avg_60d": past_60.mean() if len(past_60) > 0 else np.nan,
            "density_30d": density_30d,
            "total_restaurant_sales_1d": total_1d,
            "same_weekday_max_4w": same_wd_max,
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
    recent_14 = []
    recent_30 = []
    recent_60 = []
    same_wd = []
    for offset in range(1, 61):
        d = target_date - datetime.timedelta(days=offset)
        qty = daily.get(d, 0.0)
        if offset <= 7:
            recent_7.append(qty)
        if offset <= 14:
            recent_14.append(qty)
        if offset <= 30:
            recent_30.append(qty)
        recent_60.append(qty)
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

    # Total restaurant sales 7d average + yesterday's total
    total_7d_avg = np.nan
    total_1d = np.nan
    if total_daily_sales:
        total_vals = []
        for offset in range(1, 8):
            prev = target_date - datetime.timedelta(days=offset)
            if prev in total_daily_sales:
                total_vals.append(total_daily_sales[prev])
                if offset == 1:
                    total_1d = float(total_daily_sales[prev])
        if total_vals:
            total_7d_avg = float(np.mean(total_vals))

    # Lag features
    lag_1d = daily.get(target_date - datetime.timedelta(days=1), np.nan)
    lag_7d = daily.get(target_date - datetime.timedelta(days=7), np.nan)
    lag_14d = daily.get(target_date - datetime.timedelta(days=14), np.nan)
    lag_21d = daily.get(target_date - datetime.timedelta(days=21), np.nan)
    lag_28d = daily.get(target_date - datetime.timedelta(days=28), np.nan)

    # Density of non-zero days in last 30
    nonzero_30 = sum(1 for q in recent_30 if q > 0)
    density_30d = (nonzero_30 / len(recent_30)) if recent_30 else np.nan

    # Same-weekday maximum (last 4 weeks)
    same_wd_max = float(np.max(same_wd)) if same_wd else np.nan

    # Volatility
    rolling_std = float(np.std(recent_7)) if len(recent_7) >= 2 else np.nan
    mean_30 = float(np.mean(recent_30)) if recent_30 else np.nan
    std_30 = float(np.std(recent_30)) if len(recent_30) >= 2 else np.nan
    cv_30d = (std_30 / mean_30) if mean_30 and mean_30 > 0 and not np.isnan(std_30) else np.nan

    # Cyclic seasonality
    doy = target_date.timetuple().tm_yday
    sin_doy = np.sin(2 * np.pi * doy / 365.25)
    cos_doy = np.cos(2 * np.pi * doy / 365.25)
    sin_dow = np.sin(2 * np.pi * target_date.weekday() / 7)
    cos_dow = np.cos(2 * np.pi * target_date.weekday() / 7)

    # Weather category & interactions
    w_cat = _weather_cat(weather)
    is_we = 1 if cal["is_weekend"] else 0
    temp = weather.temp_avg if weather else np.nan
    precip = weather.precipitation if weather else np.nan

    features = np.array([
        target_date.weekday(),
        target_date.month,
        target_date.isocalendar()[1],
        is_we,
        1 if cal["is_holiday"] else 0,
        1 if cal["is_pre_holiday"] else 0,
        1 if cal.get("is_day_off", cal["is_weekend"] or cal["is_holiday"]) else 0,
        temp,
        precip,
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
        lag_1d,
        lag_7d,
        lag_14d,
        rolling_std,
        cv_30d,
        sin_doy,
        cos_doy,
        sin_dow,
        cos_dow,
        w_cat,
        (temp * is_we) if not np.isnan(temp) else np.nan,
        (precip * is_we) if not np.isnan(precip) else np.nan,
        lag_21d,
        lag_28d,
        float(np.mean(recent_14)) if recent_14 else np.nan,
        float(np.mean(recent_60)) if recent_60 else np.nan,
        density_30d,
        total_1d,
        same_wd_max,
    ], dtype=np.float64).reshape(1, -1)

    return features
