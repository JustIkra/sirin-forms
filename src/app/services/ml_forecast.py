import datetime
import io
import logging
from collections import defaultdict

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

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
from app.utils.calendar import get_calendar_context

logger = logging.getLogger(__name__)

MIN_SAMPLES = 30  # Minimum non-zero sales days to train a model


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
    ) -> DailyForecastResult:
        # 1. Cache check
        if not force:
            cached = await self._forecasts_repo.get_forecast(target_date, method="ml")
            if cached is not None:
                logger.info("Returning cached ML forecast for %s", target_date)
                return cached

        # 2. Get top-50 dishes (reuse DataCollector)
        dishes = await self._collector.collect_products()
        recent = await self._collector.collect_recent_sales(target_date)
        weather = await self._collector.collect_weather(target_date)

        # Filter to active dishes with recent sales
        dish_volume: dict[str, float] = defaultdict(float)
        dish_ids_by_name: dict[str, str] = {}
        for s in recent:
            key = s.dish_name.strip().lower()
            dish_volume[key] += s.quantity
            dish_ids_by_name[key] = s.dish_id

        from app.services.forecast import ForecastService
        active_dishes = [d for d in dishes if not ForecastService._is_non_dish(d.name)]
        sold_names = set(dish_volume.keys())
        active_dishes = [d for d in active_dishes if d.name.strip().lower() in sold_names]

        # Deduplicate by name
        seen: dict[str, object] = {}
        for d in active_dishes:
            key = d.name.strip().lower()
            if key not in seen:
                seen[key] = d
        active_dishes = list(seen.values())
        active_dishes.sort(key=lambda d: dish_volume.get(d.name.strip().lower(), 0), reverse=True)
        active_dishes = active_dishes[:50]

        # 3. Per-dish: load model → predict (or fallback)
        forecasts: list[DishForecast] = []
        for dish in active_dishes:
            model_record = await self._ml_models_repo.get_latest_model(dish.id)
            qty = await self._predict_dish(
                dish.id, dish.name, target_date, weather, model_record,
            )
            forecasts.append(DishForecast(
                dish_id=dish.id,
                dish_name=dish.name,
                predicted_quantity=max(0.0, round(qty)),
                confidence=0.7 if model_record else 0.4,
                key_factors=["ML-модель (HistGBR)" if model_record else "Среднее за 4 недели (fallback)"],
            ))

        cal = get_calendar_context(target_date)
        weather_str = ForecastService._format_weather(weather)

        result = DailyForecastResult(
            date=target_date,
            forecasts=forecasts,
            weather=weather_str,
            is_holiday=cal["is_holiday"],
            notes="ML-прогноз (HistGradientBoostingRegressor)",
            method="ml",
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
    ) -> float:
        date_from = target_date - datetime.timedelta(days=30)
        date_to = target_date - datetime.timedelta(days=1)

        # Sales by ID — matches what model was trained on
        by_id = await self._sales_repo.get_sales_by_dish(dish_id, date_from, date_to)
        # Sales by name — broader (aggregates across duplicate iiko IDs)
        by_name = await self._sales_repo.get_sales_by_dish_name(dish_name, date_from, date_to)

        # Fallback uses name-based sales (more complete)
        fallback = self._same_weekday_average(by_name or by_id, target_date)

        if model_record is not None:
            try:
                model = joblib.load(io.BytesIO(model_record.model_blob))
                # Model prediction uses ID-based sales (consistent with training)
                features = build_prediction_features(target_date, by_id, weather)
                prediction = float(model.predict(features)[0])
                # If model predicts ~0 but fallback shows sales, use fallback
                if prediction < 0.5 and fallback > 0:
                    return fallback
                return prediction
            except Exception:
                logger.warning(
                    "ML prediction failed for %s, using fallback", dish_name, exc_info=True,
                )

        return fallback

    @staticmethod
    def _same_weekday_average(sales: list[SaleRecord], target_date: datetime.date) -> float:
        daily: dict[datetime.date, float] = {}
        for s in sales:
            daily[s.date] = daily.get(s.date, 0) + s.quantity
        same_wd = []
        for week in range(1, 5):
            d = target_date - datetime.timedelta(weeks=week)
            if d in daily:
                same_wd.append(daily[d])
        return float(np.mean(same_wd)) if same_wd else 0.0

    async def train_models(self, *, force: bool = False) -> dict:
        """Train ML models for all active dishes."""
        # Get all sales from DB
        date_to = datetime.date.today()
        date_from = date_to - datetime.timedelta(days=self._settings.history_months * 30)
        all_sales = await self._sales_repo.get_sales_by_period(date_from, date_to)

        # Get weather data for the same period
        weather_records = await self._weather_repo.get_weather_range(date_from, date_to)
        weather_by_date: dict[datetime.date, DailyWeather] = {w.date: w for w in weather_records}

        # Group sales by dish
        sales_by_dish: dict[str, list[SaleRecord]] = defaultdict(list)
        dish_names: dict[str, str] = {}
        for s in all_sales:
            sales_by_dish[s.dish_id].append(s)
            dish_names[s.dish_id] = s.dish_name

        trained = 0
        skipped = 0
        failed = 0
        all_accuracies: list[float] = []

        for dish_id, dish_sales in sales_by_dish.items():
            # Count non-zero sales days
            daily_qty: dict[datetime.date, float] = {}
            for s in dish_sales:
                daily_qty[s.date] = daily_qty.get(s.date, 0) + s.quantity
            nonzero_days = sum(1 for q in daily_qty.values() if q > 0)

            if nonzero_days < MIN_SAMPLES:
                skipped += 1
                continue

            if not force:
                existing = await self._ml_models_repo.get_latest_model(dish_id)
                if existing and existing.samples_count >= nonzero_days:
                    skipped += 1
                    continue

            try:
                df = build_features_dataframe(dish_sales, weather_by_date)
                X = df[FEATURE_NAMES].values
                y = df["target"].values

                # Temporal split: last 30 days for validation, rest for training
                test_size = min(30, len(y) // 5)  # at least 80% train
                if test_size < 7:
                    test_size = 0  # not enough data for meaningful validation
                train_end = len(y) - test_size if test_size > 0 else len(y)

                X_train, y_train = X[:train_end], y[:train_end]
                X_test, y_test = X[train_end:], y[train_end:]

                model = HistGradientBoostingRegressor(
                    max_iter=200,
                    max_depth=6,
                    learning_rate=0.1,
                    min_samples_leaf=5,
                    categorical_features=CATEGORICAL_FEATURES,
                )
                model.fit(X_train, y_train)

                # Validation metrics on held-out temporal test set
                if test_size > 0:
                    y_pred_test = model.predict(X_test)
                    mae_test = float(np.mean(np.abs(y_test - y_pred_test)))
                    # MAPE-style accuracy: 1 - mean(|actual-pred| / max(actual,pred))
                    denom = np.maximum(y_test, y_pred_test)
                    denom = np.where(denom == 0, 1.0, denom)
                    accuracy = float((1 - np.mean(np.abs(y_test - y_pred_test) / denom)) * 100)
                else:
                    y_pred_train = model.predict(X_train)
                    mae_test = float(np.mean(np.abs(y_train - y_pred_train)))
                    accuracy = 0.0  # unknown without test set

                # Retrain on full data for production model
                model.fit(X, y)

                # Serialize model
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
                    feature_names=FEATURE_NAMES,
                    samples_count=nonzero_days,
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
