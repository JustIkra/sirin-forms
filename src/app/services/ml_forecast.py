import datetime
import logging
import statistics
from collections import defaultdict

import numpy as np

from app.config import Settings
from app.models.forecast import DailyForecastResult, DishForecast, DishIngredient
from app.models.weather import DailyWeather
from app.repositories.forecasts import ForecastsRepository
from app.repositories.menu_snapshots import MenuSnapshotsRepository
from app.repositories.ml_models import MLModelsRepository
from app.repositories.products import ProductsRepository
from app.repositories.sales import SalesRepository
from app.repositories.weather import WeatherRepository
from app.services.data_collector import DataCollector
from app.services.forecasters.daily import DailyForecaster
from app.services.forecasters.weekly import WeeklyForecaster
from app.utils.calendar import get_calendar_context
from app.utils.dt import today as today_msk

logger = logging.getLogger(__name__)

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
        menu_repo: MenuSnapshotsRepository,
        products_repo: ProductsRepository | None = None,
    ) -> None:
        self._collector = data_collector
        self._forecasts_repo = forecasts_repo
        self._ml_models_repo = ml_models_repo
        self._sales_repo = sales_repo
        self._weather_repo = weather_repo
        self._settings = settings
        self._menu_repo = menu_repo
        self._products_repo = products_repo
        self._weekly = WeeklyForecaster(
            settings=settings,
            sales_repo=sales_repo,
            ml_models_repo=ml_models_repo,
            weather_repo=weather_repo,
            menu_repo=menu_repo,
        )
        self._daily = DailyForecaster(
            settings=settings,
            sales_repo=sales_repo,
            ml_models_repo=ml_models_repo,
            weather_repo=weather_repo,
            menu_repo=menu_repo,
        )

    async def _fetch_stock_map(
        self, target_date: datetime.date,
    ) -> dict[str, float]:
        """Получает карту остатков product_id → amount из iiko."""
        if not self._settings.iiko_department_id:
            return {}
        try:
            iiko = getattr(self._collector, "_iiko", None)
            if iiko is None:
                return {}
            raw_stock = await iiko.get_balance_stores(
                target_date,
                self._settings.iiko_department_id,
            )
        except Exception:
            logger.warning(
                "iiko stock fetch failed for enrichment on %s", target_date,
                exc_info=True,
            )
            return {}
        stock_map: dict[str, float] = defaultdict(float)
        for item in raw_stock:
            product_id = item.get("product") or item.get("productId") or ""
            amount = float(item.get("amount", 0))
            if product_id:
                stock_map[product_id] += amount
        return dict(stock_map)

    async def _enrich_with_ingredients(
        self,
        forecasts: list[DishForecast],
        scope: str = "week",
        stock_map: dict[str, float] | None = None,
    ) -> None:
        """Обогащает каждый DishForecast списком ингредиентов с total_amount.

        Shortage рассчитывается PER-BLUDO: сколько не хватает конкретного
        ингредиента при приготовлении именно этого блюда в ожидаемом объёме.
        """
        if self._products_repo is None or not forecasts:
            return
        dish_ids = [f.dish_id for f in forecasts]
        ingredients_map = await self._products_repo.get_ingredients_map(dish_ids)
        stocks = stock_map or {}
        for f in forecasts:
            raw = ingredients_map.get(f.dish_id, [])
            qty = max(0.0, f.predicted_quantity)
            enriched: list[DishIngredient] = []
            for ing in raw:
                total = round(ing.amount * qty, 3)
                stock_amt = stocks.get(ing.product_id)
                shortage = 0.0
                if stock_amt is not None and total > stock_amt:
                    shortage = round(total - stock_amt, 3)
                enriched.append(
                    DishIngredient(
                        product_id=ing.product_id,
                        name=ing.name,
                        amount_per_unit=ing.amount,
                        total_amount=total,
                        unit=ing.unit or None,
                        stock=stock_amt,
                        shortage=shortage,
                    )
                )
            f.ingredients = enriched

    async def train_models(self, *, force: bool = False) -> dict:
        result = await self._weekly.train_all(force=force)
        await self._cleanup_obsolete_forecasts(method="ml")
        return result

    async def train_daily_models(self, *, force: bool = False) -> dict:
        result = await self._daily.train_all(force=force)
        await self._cleanup_obsolete_forecasts(method="ml_daily")
        return result

    async def _cleanup_obsolete_forecasts(self, *, method: str) -> None:
        """Wipe cached forecasts for dishes dropped from the menu snapshot.

        Runs after each retrain. `_cleanup_obsolete_models` already removes
        the ml_models row; this clears the matching forecast rows so that
        stale cached predictions don't keep surfacing through
        `ForecastsRepository.get_forecast()`.
        """
        active_ids = await self._menu_repo.get_latest_active_dish_ids()
        if not active_ids:
            return
        deleted = await self._forecasts_repo.delete_obsolete_forecasts(
            active_ids, method=method,
        )
        if deleted:
            logger.info(
                "%s retrain cleanup: removed %d stale forecast rows",
                method, deleted,
            )

    async def _filter_active_dishes_weekly(
        self,
        dishes: list,
        recent_sales: list,
    ) -> list:
        """Pick dishes that belong on the weekly forecast.

        Primary source — Domain-1 menu snapshot. When the snapshot is empty
        (first run before the scheduler has populated it), fall back to a
        recent-sales heuristic so the endpoint is never "dead on arrival".
        """
        dish_volume: dict[str, float] = defaultdict(float)
        for s in recent_sales:
            dish_volume[s.dish_name.strip().lower()] += s.quantity

        active_ids = await self._menu_repo.get_latest_active_dish_ids()

        if active_ids:
            active = [
                d for d in dishes
                if d.id in active_ids
                and d.price and d.price > 0
                and not _is_non_dish(d.name)
            ]
        else:
            logger.warning(
                "menu snapshot unavailable, using sales-based fallback for weekly",
            )
            active = [d for d in dishes if not _is_non_dish(d.name)]
            sold_names = set(dish_volume.keys())
            active = [d for d in active if d.name.strip().lower() in sold_names]
            active = [d for d in active if d.price and d.price > 0]
            totals = [dish_volume.get(d.name.strip().lower(), 0) for d in active]
            if totals:
                median = statistics.median(totals)
                threshold = median * self._settings.weekly_min_sales_pct
                active = [
                    d for d in active
                    if dish_volume.get(d.name.strip().lower(), 0) >= threshold
                ]

        seen: dict[str, object] = {}
        for d in active:
            key = d.name.strip().lower()
            if key not in seen:
                seen[key] = d
        active = list(seen.values())
        active.sort(
            key=lambda d: dish_volume.get(d.name.strip().lower(), 0), reverse=True,
        )
        return active

    async def _filter_active_dishes_daily(self, dishes: list) -> list:
        """Pick dishes for daily forecast — Domain-1 snapshot or price>0 fallback."""
        active_ids = await self._menu_repo.get_latest_active_dish_ids()
        if active_ids:
            active = [
                d for d in dishes
                if d.id in active_ids
                and d.price and d.price > 0
                and not _is_non_dish(d.name)
            ]
        else:
            logger.warning(
                "menu snapshot unavailable, using price>0 fallback for daily",
            )
            active = [
                d for d in dishes
                if d.price and d.price > 0 and not _is_non_dish(d.name)
            ]
        seen: dict[str, object] = {}
        for d in active:
            key = d.name.strip().lower()
            if key not in seen:
                seen[key] = d
        return list(seen.values())

    async def generate_forecast(
        self,
        target_date: datetime.date,
        *,
        force: bool = False,
        _backfill: bool = True,
        _dishes: list | None = None,
        _recent_sales: list | None = None,
    ) -> DailyForecastResult:
        if not force:
            cached = await self._forecasts_repo.get_forecast(target_date, method="ml")
            if cached is not None:
                logger.info("Returning cached ML forecast for %s", target_date)
                return cached

        dishes = (
            _dishes if _dishes is not None
            else await self._collector.collect_products()
        )
        if _recent_sales is not None:
            date_from = target_date - datetime.timedelta(days=30)
            date_to = target_date - datetime.timedelta(days=1)
            recent = [s for s in _recent_sales if date_from <= s.date <= date_to]
        else:
            recent = await self._collector.collect_recent_sales(target_date)
        weather = await self._collector.collect_weather(target_date)

        active_dishes = await self._filter_active_dishes_weekly(dishes, recent)
        logger.info(
            "ML menu: %d catalog -> %d active (weekly)",
            len(dishes), len(active_dishes),
        )

        # Auto-train if no weekly models exist
        models_count = await self._ml_models_repo.count_models(granularity="weekly")
        if models_count == 0:
            logger.warning("No trained weekly ML models found, triggering training...")
            await self.train_models()

        week_start = target_date - datetime.timedelta(days=target_date.weekday())
        week_end = week_start + datetime.timedelta(days=6)

        window = self._weekly._training_window(week_start)
        totals_rows = await self._sales_repo.get_daily_totals(
            window.date_from, window.date_to,
        )
        total_daily_sales = {r.date: r.total_quantity for r in totals_rows}

        # 90-day lookback is for feature aggregation (rolling stats),
        # not the training window — keep it independent.
        weather_records = await self._weather_repo.get_weather_range(
            week_start - datetime.timedelta(days=90),
            week_end,
        )
        weather_by_date = {w.date: w for w in weather_records}

        forecasts: list[DishForecast] = []
        for dish in active_dishes:
            qty, method = await self._weekly.predict_dish(
                dish.id,
                dish.name,
                week_start,
                weather=weather_by_date,
                total_daily_sales=total_daily_sales,
            )
            forecasts.append(
                DishForecast(
                    dish_id=dish.id,
                    dish_name=dish.name,
                    predicted_quantity=max(0.0, round(qty)),
                    confidence=0.7 if method == "ml" else 0.4,
                    key_factors=[
                        "ML-модель (HistGBR)"
                        if method == "ml"
                        else "Среднее за 4 недели (fallback)"
                    ],
                    price=dish.price,
                    prediction_method=method,
                )
            )

        forecasts = [f for f in forecasts if f.predicted_quantity > 0]

        cal = get_calendar_context(target_date)
        weather_str = _format_weather(weather)

        stock_map = await self._fetch_stock_map(target_date)
        await self._enrich_with_ingredients(
            forecasts, scope="week", stock_map=stock_map,
        )

        ml_count = sum(1 for f in forecasts if f.prediction_method == "ml")
        total_revenue = round(
            sum((f.price or 0.0) * f.predicted_quantity for f in forecasts), 0,
        )
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
            total_revenue=total_revenue,
        )

        await self._forecasts_repo.save_forecast(result)
        logger.info(
            "ML forecast saved for %s: %d dishes", target_date, len(forecasts),
        )
        return result

    async def generate_daily_forecast(
        self,
        target_date: datetime.date,
        *,
        force: bool = False,
    ) -> DailyForecastResult:
        """Generate a daily forecast using only the daily ML models."""
        if not force:
            cached = await self._forecasts_repo.get_forecast(
                target_date, method="ml_daily",
            )
            if cached is not None:
                return cached

        dishes = await self._collector.collect_products()
        weather = await self._collector.collect_weather(target_date)

        active_dishes = await self._filter_active_dishes_daily(dishes)

        daily_count = await self._ml_models_repo.count_models(granularity="daily")
        if daily_count == 0:
            logger.warning("No daily ML models found, triggering training...")
            await self.train_daily_models()

        weather_records = await self._weather_repo.get_weather_range(
            target_date - datetime.timedelta(days=90), target_date,
        )
        weather_by_date = {w.date: w for w in weather_records}

        window = self._daily._training_window(target_date)
        totals_rows = await self._sales_repo.get_daily_totals(
            window.date_from, window.date_to,
        )
        total_daily_sales = {r.date: r.total_quantity for r in totals_rows}

        weather_for_target = weather_by_date.get(target_date) or weather

        forecasts: list[DishForecast] = []
        for dish in active_dishes:
            qty, method = await self._daily.predict_dish(
                dish.id,
                dish.name,
                target_date,
                weather=weather_for_target,
                total_daily_sales=total_daily_sales,
            )
            # Daily analysis shows only dishes backed by a valid daily ML model;
            # fallback predictions are intentionally dropped from the UI.
            if method != "ml":
                continue
            rounded = max(0.0, round(qty))
            if rounded == 0:
                continue
            forecasts.append(
                DishForecast(
                    dish_id=dish.id,
                    dish_name=dish.name,
                    predicted_quantity=rounded,
                    confidence=0.7,
                    key_factors=["ML-модель (дневная)"],
                    price=dish.price,
                    prediction_method="ml",
                )
            )

        cal = get_calendar_context(target_date)
        weather_str = _format_weather(weather)

        stock_map = await self._fetch_stock_map(target_date)
        await self._enrich_with_ingredients(
            forecasts, scope="day", stock_map=stock_map,
        )

        total_revenue = round(
            sum((f.price or 0.0) * f.predicted_quantity for f in forecasts), 0,
        )
        result = DailyForecastResult(
            date=target_date,
            forecasts=forecasts,
            weather=weather_str,
            is_holiday=cal["is_holiday"],
            notes="Дневной ML-прогноз",
            method="ml_daily",
            ml_count=len(forecasts),
            fallback_count=0,
            total_revenue=total_revenue,
        )

        await self._forecasts_repo.save_forecast(result)
        logger.info(
            "Daily forecast saved for %s: %d dishes", target_date, len(forecasts),
        )
        return result

    async def _backfill_and_get_bias(
        self, target_date: datetime.date, *, _dishes=None,
    ) -> dict[str, float]:
        """Backfill missing ML forecasts for X-14..X-1, compute per-dish bias
        with exponential decay."""
        today = today_msk()
        dates = [
            target_date - datetime.timedelta(days=i)
            for i in range(1, 15)
            if (target_date - datetime.timedelta(days=i)) <= today
        ]

        dates_to_backfill = []
        for d in dates:
            existing = await self._forecasts_repo.get_forecast(d, method="ml")
            if existing is None:
                dates_to_backfill.append(d)

        if dates_to_backfill:
            dishes = (
                _dishes if _dishes is not None
                else await self._collector.collect_products()
            )
            earliest = min(dates_to_backfill) - datetime.timedelta(days=30)
            all_sales = await self._collector.collect_recent_sales(
                target_date, date_from=earliest,
            )
            for d in dates_to_backfill:
                logger.info("Backfilling ML forecast for %s", d)
                try:
                    await self.generate_forecast(
                        d,
                        force=False,
                        _backfill=False,
                        _dishes=dishes,
                        _recent_sales=all_sales,
                    )
                except Exception:
                    logger.warning(
                        "ML backfill failed for %s, skipping", d, exc_info=True,
                    )

        dated_records: list[tuple[int, object]] = []
        for d in dates:
            forecast = await self._forecasts_repo.get_forecast(d, method="ml")
            if forecast is None:
                continue
            sales = await self._sales_repo.get_sales_by_period(d, d)
            if not sales:
                continue
            actual_sales = [
                {
                    "date": s.date,
                    "dish_id": s.dish_id,
                    "dish_name": s.dish_name,
                    "quantity": s.quantity,
                }
                for s in sales
            ]
            records = await self._forecasts_repo.get_plan_fact(
                d, d, actual_sales, method="ml",
            )
            days_ago = (target_date - d).days
            for r in records:
                dated_records.append((days_ago, r))

        if not dated_records:
            return {}

        half_life = 5.0
        dish_errors: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for days_ago, r in dated_records:
            denom = max(r.predicted_quantity, r.actual_quantity)
            if denom > 0:
                error = (r.predicted_quantity - r.actual_quantity) / denom
                weight = np.exp(-np.log(2) * days_ago / half_life)
                dish_errors[r.dish_name.strip().lower()].append((weight, error))

        result: dict[str, float] = {}
        for name, weighted_errors in dish_errors.items():
            if len(weighted_errors) >= 2:
                total_weight = sum(w for w, _ in weighted_errors)
                weighted_mean = sum(w * e for w, e in weighted_errors) / total_weight
                result[name] = weighted_mean
        return result
