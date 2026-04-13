import datetime
import io
import logging
import statistics
from collections import defaultdict

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit

from app.config import Settings
from app.models.forecast import DailyForecastResult, DishForecast
from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.repositories.forecasts import ForecastsRepository
from app.repositories.ml_models import MLModelsRepository
from app.repositories.sales import SalesRepository
from app.repositories.weather import WeatherRepository
from app.services.data_collector import DataCollector
from app.services.features import (
    CATEGORICAL_FEATURES,
    FEATURE_NAMES,
    build_features_dataframe,
    build_prediction_features,
)
from app.services.features_weekly import (
    WEEKLY_CATEGORICAL_FEATURES,
    WEEKLY_FEATURE_NAMES,
    build_weekly_features_dataframe,
    build_weekly_prediction_features,
)
from app.utils.calendar import get_calendar_context

logger = logging.getLogger(__name__)

MIN_SAMPLES = 4  # Minimum non-zero weeks to train a weekly model

_NON_DISH_PREFIXES = ("+", "-", "Заказ ")
_NON_DISH_KEYWORDS = ("комплимент", "замена чаши", "на чаше", "подарок", "персонал")


def _is_non_dish(name: str) -> bool:
    """Return True for modifiers and internal items."""
    stripped = name.strip()
    if any(stripped.startswith(p) for p in _NON_DISH_PREFIXES):
        return True
    if any(kw in stripped.lower() for kw in _NON_DISH_KEYWORDS):
        return True
    return False


_WEATHER_RU: dict[str, str] = {
    "Clear": "ясно",
    "Clouds": "облачно",
    "Rain": "дождь",
    "Drizzle": "морось",
    "Thunderstorm": "гроза",
    "Snow": "снег",
    "Mist": "дымка",
    "Fog": "туман",
    "Haze": "мгла",
    "Smoke": "смог",
    "Dust": "пыль",
    "Sand": "песчаная буря",
    "Ash": "пепел",
    "Squall": "шквал",
    "Tornado": "торнадо",
}


def _format_weather(weather: DailyWeather | None) -> str | None:
    if weather is None:
        return None
    raw = weather.weather_description or weather.weather_main
    desc = _WEATHER_RU.get(raw, raw)
    parts = [
        f"{weather.temp_min:.0f}–{weather.temp_max:.0f}°C",
        desc,
    ]
    if weather.precipitation > 0:
        parts.append(f"осадки {weather.precipitation:.1f} мм")
    if weather.humidity is not None:
        parts.append(f"влажность {weather.humidity}%")
    if weather.wind_speed is not None:
        parts.append(f"ветер {weather.wind_speed:.1f} м/с")
    return ", ".join(parts)


class MLForecastService:

    def __init__(
        self,
        data_collector: DataCollector,
        forecasts_repo: ForecastsRepository,
        ml_models_repo: MLModelsRepository,
        sales_repo: SalesRepository,
        weather_repo: WeatherRepository,
        settings: Settings,
    ) -> None:
        self._collector = data_collector
        self._forecasts_repo = forecasts_repo
        self._ml_models_repo = ml_models_repo
        self._sales_repo = sales_repo
        self._weather_repo = weather_repo
        self._settings = settings

    async def generate_forecast(
        self,
        target_date: datetime.date,
        *,
        force: bool = False,
        _backfill: bool = True,
        _dishes: list | None = None,
        _recent_sales: list | None = None,
    ) -> DailyForecastResult:
        # 1. Cache check
        if not force:
            cached = await self._forecasts_repo.get_forecast(target_date, method="ml")
            if cached is not None:
                logger.info("Returning cached ML forecast for %s", target_date)
                return cached

        # 2. Get top-50 dishes (reuse pre-fetched data or call iiko)
        dishes = _dishes if _dishes is not None else await self._collector.collect_products()
        if _recent_sales is not None:
            date_from = target_date - datetime.timedelta(days=30)
            date_to = target_date - datetime.timedelta(days=1)
            recent = [s for s in _recent_sales if date_from <= s.date <= date_to]
        else:
            recent = await self._collector.collect_recent_sales(target_date)
        weather = await self._collector.collect_weather(target_date)

        # Filter to active dishes with recent sales
        dish_volume: dict[str, float] = defaultdict(float)
        dish_days: dict[str, set] = defaultdict(set)
        dish_ids_by_name: dict[str, str] = {}
        for s in recent:
            key = s.dish_name.strip().lower()
            dish_volume[key] += s.quantity
            dish_days[key].add(s.date)
            dish_ids_by_name[key] = s.dish_id

        active_dishes = [d for d in dishes if not _is_non_dish(d.name)]
        sold_names = set(dish_volume.keys())
        active_dishes = [d for d in active_dishes if d.name.strip().lower() in sold_names]

        # Deduplicate by name
        seen: dict[str, object] = {}
        for d in active_dishes:
            key = d.name.strip().lower()
            if key not in seen:
                seen[key] = d
        active_dishes = list(seen.values())
        active_dishes = [d for d in active_dishes if d.price and d.price > 0]

        # Dynamic threshold: exclude items below min_sales_pct of median monthly sales
        all_totals = [dish_volume.get(d.name.strip().lower(), 0) for d in active_dishes]
        if all_totals:
            median_sales = statistics.median(all_totals)
            sales_threshold = median_sales * self._settings.min_sales_pct
            active_dishes = [
                d for d in active_dishes
                if dish_volume.get(d.name.strip().lower(), 0) >= sales_threshold
            ]

        active_dishes.sort(key=lambda d: dish_volume.get(d.name.strip().lower(), 0), reverse=True)
        logger.info("ML menu: %d catalog → %d active (with sales, price, threshold)", len(dishes), len(active_dishes))

        # Auto-train if no models exist
        models_count = await self._ml_models_repo.count_models()
        if models_count == 0:
            logger.warning("No trained ML models found, triggering training...")
            await self.train_models()

        # Weekly: compute week boundaries
        week_start = target_date - datetime.timedelta(days=target_date.weekday())  # Monday
        week_end = week_start + datetime.timedelta(days=6)  # Sunday

        # Fetch sales history for weekly features
        _hist_from = week_start - datetime.timedelta(days=365)
        _hist_to = week_start - datetime.timedelta(days=1)
        _totals_rows = await self._sales_repo.get_daily_totals(_hist_from, _hist_to)
        total_daily_sales = {r.date: r.total_quantity for r in _totals_rows}

        # Fetch weather for the target week
        weather_records = await self._weather_repo.get_weather_range(
            week_start - datetime.timedelta(days=90), week_end,
        )
        weather_by_date = {w.date: w for w in weather_records}

        # 3. Per-dish: load model → predict weekly (or fallback)
        forecasts: list[DishForecast] = []
        for dish in active_dishes:
            model_record = await self._ml_models_repo.get_latest_model(dish.id, dish.name)
            qty, method = await self._predict_dish_weekly(
                dish.id, dish.name, week_start, weather_by_date, model_record, total_daily_sales,
            )
            forecasts.append(DishForecast(
                dish_id=dish.id,
                dish_name=dish.name,
                predicted_quantity=max(0.0, round(qty)),
                confidence=0.7 if method == "ml" else 0.4,
                key_factors=["ML-модель (HistGBR)" if method == "ml" else "Среднее за 4 недели (fallback)"],
                price=dish.price,
                prediction_method=method,
            ))

        # Remove zero-quantity predictions
        forecasts = [f for f in forecasts if f.predicted_quantity > 0]

        cal = get_calendar_context(target_date)
        weather_str = _format_weather(weather)

        ml_count = sum(1 for f in forecasts if f.prediction_method == "ml")
        result = DailyForecastResult(
            date=target_date,
            forecasts=forecasts,
            weather=weather_str,
            is_holiday=cal["is_holiday"],
            notes="Недельный ML-прогноз (HistGBR)",
            method="ml",
            ml_count=ml_count,
            fallback_count=len(forecasts) - ml_count,
            week_start=week_start,
            week_end=week_end,
        )

        # 4. Save
        await self._forecasts_repo.save_forecast(result)
        logger.info("ML forecast saved for %s: %d dishes", target_date, len(forecasts))
        return result

    async def _predict_dish(
        self,
        dish_id: str,
        dish_name: str,
        target_date: datetime.date,
        weather: DailyWeather | None,
        model_record,
        total_daily_sales: dict[datetime.date, float] | None = None,
    ) -> tuple[float, str]:
        """Return (predicted_quantity, prediction_method)."""
        date_from = target_date - datetime.timedelta(days=90)
        date_to = target_date - datetime.timedelta(days=1)

        # Sales by ID — matches what model was trained on
        by_id = await self._sales_repo.get_sales_by_dish(dish_id, date_from, date_to)
        # Sales by name — broader (aggregates across duplicate iiko IDs)
        by_name = await self._sales_repo.get_sales_by_dish_name(dish_name, date_from, date_to)

        # Fallback uses name-based sales (more complete)
        fallback = self._cascading_fallback(by_name or by_id, target_date)

        # Skip models with stale feature sets
        if model_record is not None and model_record.feature_names != FEATURE_NAMES:
            logger.info("Model for %s has stale features, skipping", dish_name)
            model_record = None

        if model_record is not None:
            try:
                model = joblib.load(io.BytesIO(model_record.model_blob))
                features = build_prediction_features(target_date, by_id, weather, total_daily_sales)
                prediction = float(model.predict(features)[0])
                # If model predicts ~0 but fallback shows sales, use fallback
                if prediction < 0.5 and fallback > 0:
                    return fallback, "fallback"
                return prediction, "ml"
            except Exception:
                logger.warning(
                    "ML prediction failed for %s, using fallback", dish_name, exc_info=True,
                )

        return fallback, "fallback"

    async def _predict_dish_weekly(
        self,
        dish_id: str,
        dish_name: str,
        week_start: datetime.date,
        weather_by_date: dict[datetime.date, DailyWeather],
        model_record,
        total_daily_sales: dict[datetime.date, float] | None = None,
    ) -> tuple[float, str]:
        """Predict weekly quantity for a dish. Returns (qty, method)."""
        hist_from = week_start - datetime.timedelta(days=365)
        hist_to = week_start - datetime.timedelta(days=1)

        by_id = await self._sales_repo.get_sales_by_dish(dish_id, hist_from, hist_to)
        by_name = await self._sales_repo.get_sales_by_dish_name(dish_name, hist_from, hist_to)

        # Weekly fallback: average of last 4 weeks
        sales = by_name or by_id
        weekly_totals: dict[datetime.date, float] = {}
        for s in sales:
            monday = s.date - datetime.timedelta(days=s.date.weekday())
            weekly_totals[monday] = weekly_totals.get(monday, 0) + s.quantity
        prev_4w = [
            weekly_totals.get(week_start - datetime.timedelta(days=7 * i), 0.0)
            for i in range(1, 5)
        ]
        fallback = float(np.mean(prev_4w)) if any(v > 0 for v in prev_4w) else 0.0

        if model_record is not None and model_record.feature_names != WEEKLY_FEATURE_NAMES:
            model_record = None

        if model_record is not None:
            try:
                model = joblib.load(io.BytesIO(model_record.model_blob))
                features = build_weekly_prediction_features(
                    week_start, by_id, weather_by_date, total_daily_sales,
                )
                prediction = float(model.predict(features)[0])
                return max(0.0, prediction), "ml"
            except Exception:
                logger.warning(
                    "Weekly ML prediction failed for %s, using fallback",
                    dish_name, exc_info=True,
                )

        return fallback, "fallback"

    async def _backfill_and_get_bias(self, target_date: datetime.date, *, _dishes=None) -> dict[str, float]:
        """Backfill missing ML forecasts for X-14..X-1, compute per-dish bias with exponential decay."""
        today = datetime.date.today()
        dates = [
            target_date - datetime.timedelta(days=i)
            for i in range(1, 15)
            if (target_date - datetime.timedelta(days=i)) <= today
        ]

        # Find dates that need backfill
        dates_to_backfill = []
        for d in dates:
            existing = await self._forecasts_repo.get_forecast(d, method="ml")
            if existing is None:
                dates_to_backfill.append(d)

        # Pre-fetch data once for all backfill dates (2 iiko sessions instead of 2*N)
        if dates_to_backfill:
            dishes = _dishes if _dishes is not None else await self._collector.collect_products()
            widest_lookback = (target_date - min(dates_to_backfill)).days + 30
            all_sales = await self._collector.collect_recent_sales(target_date, days_back=widest_lookback)
            for d in dates_to_backfill:
                logger.info("Backfilling ML forecast for %s", d)
                try:
                    await self.generate_forecast(
                        d, force=False, _backfill=False,
                        _dishes=dishes, _recent_sales=all_sales,
                    )
                except Exception:
                    logger.warning("ML backfill failed for %s, skipping", d, exc_info=True)

        # Collect plan-fact for all backfilled dates with day offsets
        dated_records: list[tuple[int, object]] = []  # (days_ago, record)
        for d in dates:
            forecast = await self._forecasts_repo.get_forecast(d, method="ml")
            if forecast is None:
                continue
            sales = await self._sales_repo.get_sales_by_period(d, d)
            if not sales:
                continue
            actual_sales = [
                {"date": s.date, "dish_id": s.dish_id, "dish_name": s.dish_name, "quantity": s.quantity}
                for s in sales
            ]
            records = await self._forecasts_repo.get_plan_fact(d, d, actual_sales, method="ml")
            days_ago = (target_date - d).days
            for r in records:
                dated_records.append((days_ago, r))

        if not dated_records:
            return {}

        # Compute per-dish weighted signed error with exponential decay (half-life = 5 days)
        half_life = 5.0
        dish_errors: dict[str, list[tuple[float, float]]] = defaultdict(list)  # name -> [(weight, error)]
        for days_ago, r in dated_records:
            denom = max(r.predicted_quantity, r.actual_quantity)
            if denom > 0:
                error = (r.predicted_quantity - r.actual_quantity) / denom
                weight = np.exp(-np.log(2) * days_ago / half_life)
                dish_errors[r.dish_name.strip().lower()].append((weight, error))

        result = {}
        for name, weighted_errors in dish_errors.items():
            if len(weighted_errors) >= 2:
                total_weight = sum(w for w, _ in weighted_errors)
                weighted_mean = sum(w * e for w, e in weighted_errors) / total_weight
                result[name] = weighted_mean
        return result

    @staticmethod
    def _cascading_fallback(sales: list[SaleRecord], target_date: datetime.date) -> float:
        daily: dict[datetime.date, float] = {}
        for s in sales:
            daily[s.date] = daily.get(s.date, 0) + s.quantity

        # Level 1: same weekday average (last 4 weeks)
        same_wd = []
        for week in range(1, 5):
            d = target_date - datetime.timedelta(weeks=week)
            if d in daily:
                same_wd.append(daily[d])
        if same_wd:
            return float(np.mean(same_wd))

        # Level 2: median of all days with sales in last 30 days
        cutoff = target_date - datetime.timedelta(days=30)
        recent = {d: q for d, q in daily.items() if d >= cutoff}
        if recent:
            return float(np.median(list(recent.values())))

        return 0.0

    async def train_models(self, *, force: bool = False) -> dict:
        """Train ML models for active menu dishes (sold in last 90 days)."""
        date_to = datetime.date.today()
        # Train on last 365 days — longer history dilutes signal with zeros
        date_from = date_to - datetime.timedelta(days=365)
        all_sales = await self._sales_repo.get_sales_by_period(date_from, date_to)

        # Active menu = dishes with at least one sale in last 90 days
        cutoff_90d = date_to - datetime.timedelta(days=90)
        active_dish_ids: set[str] = {
            s.dish_id for s in all_sales
            if s.date >= cutoff_90d and not _is_non_dish(s.dish_name)
        }
        logger.info("Active menu (sold in last 90d): %d dishes", len(active_dish_ids))

        # Get weather data for the same period
        weather_records = await self._weather_repo.get_weather_range(date_from, date_to)
        weather_by_date: dict[datetime.date, DailyWeather] = {w.date: w for w in weather_records}

        # Get total daily sales for restaurant traffic feature
        daily_totals_rows = await self._sales_repo.get_daily_totals(date_from, date_to)
        total_daily_sales = {r.date: r.total_quantity for r in daily_totals_rows}

        # Group ALL history for active dishes (full history for training)
        sales_by_dish: dict[str, list[SaleRecord]] = defaultdict(list)
        dish_names: dict[str, str] = {}
        for s in all_sales:
            if s.dish_id in active_dish_ids:
                sales_by_dish[s.dish_id].append(s)
                dish_names[s.dish_id] = s.dish_name

        trained = 0
        skipped = 0
        failed = 0
        all_accuracies: list[float] = []

        for dish_id, dish_sales in sales_by_dish.items():
            # Count non-zero weeks (not days)
            weekly_qty: dict[datetime.date, float] = {}
            for s in dish_sales:
                monday = s.date - datetime.timedelta(days=s.date.weekday())
                weekly_qty[monday] = weekly_qty.get(monday, 0) + s.quantity
            nonzero_weeks = sum(1 for q in weekly_qty.values() if q > 0)

            if nonzero_weeks < MIN_SAMPLES:
                skipped += 1
                continue

            if not force:
                existing = await self._ml_models_repo.get_latest_model(dish_id)
                if (
                    existing
                    and existing.samples_count >= nonzero_weeks
                    and existing.feature_names == WEEKLY_FEATURE_NAMES
                ):
                    skipped += 1
                    continue

            try:
                df = build_weekly_features_dataframe(dish_sales, weather_by_date, total_daily_sales)
                X = df[WEEKLY_FEATURE_NAMES].values
                y = df["target"].values

                model = HistGradientBoostingRegressor(
                    loss="poisson",
                    max_iter=200,
                    max_depth=4,
                    learning_rate=0.05,
                    min_samples_leaf=3,
                    categorical_features=WEEKLY_CATEGORICAL_FEATURES,
                )

                # TimeSeriesSplit cross-validation
                n_splits = min(5, max(2, len(y) // 8))
                test_size = 0
                if len(y) >= 16:
                    tscv = TimeSeriesSplit(n_splits=n_splits)
                    mae_scores = []
                    acc_scores = []
                    for train_idx, test_idx in tscv.split(X):
                        model.fit(X[train_idx], y[train_idx])
                        y_pred_fold = model.predict(X[test_idx])
                        mae_scores.append(float(np.mean(np.abs(y[test_idx] - y_pred_fold))))
                        denom = np.maximum(y[test_idx], y_pred_fold)
                        denom = np.where(denom == 0, 1.0, denom)
                        acc_scores.append(float((1 - np.mean(np.abs(y[test_idx] - y_pred_fold) / denom)) * 100))
                    mae_test = float(np.mean(mae_scores))
                    accuracy = float(np.mean(acc_scores))
                    test_size = len(y) // (n_splits + 1)
                else:
                    test_size = max(2, len(y) // 5)
                    train_end = len(y) - test_size
                    model.fit(X[:train_end], y[:train_end])
                    y_pred_test = model.predict(X[train_end:])
                    mae_test = float(np.mean(np.abs(y[train_end:] - y_pred_test)))
                    denom = np.maximum(y[train_end:], y_pred_test)
                    denom = np.where(denom == 0, 1.0, denom)
                    accuracy = float((1 - np.mean(np.abs(y[train_end:] - y_pred_test) / denom)) * 100)

                # Retrain on full data
                model.fit(X, y)

                buf = io.BytesIO()
                joblib.dump(model, buf)
                model_blob = buf.getvalue()

                await self._ml_models_repo.save_model(
                    dish_id=dish_id,
                    dish_name=dish_names[dish_id],
                    model_blob=model_blob,
                    metrics={
                        "mae_test": round(mae_test, 2),
                        "accuracy_pct": round(accuracy, 1),
                        "samples": len(y),
                        "test_size": test_size,
                    },
                    feature_names=WEEKLY_FEATURE_NAMES,
                    samples_count=nonzero_weeks,
                )
                trained += 1
                all_accuracies.append(accuracy)
                logger.info(
                    "Trained model for %s: MAE=%.2f, accuracy=%.1f%%, samples=%d",
                    dish_names[dish_id], mae_test, accuracy, len(y),
                )
            except Exception:
                logger.error("Failed to train model for %s", dish_names.get(dish_id, dish_id), exc_info=True)
                failed += 1

        avg_accuracy = round(np.mean(all_accuracies), 1) if all_accuracies else 0.0
        return {
            "trained": trained,
            "skipped": skipped,
            "failed": failed,
            "avg_accuracy_pct": avg_accuracy,
        }
