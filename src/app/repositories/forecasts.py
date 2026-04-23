import datetime
import json

from rapidfuzz import fuzz
from sqlalchemy import delete, distinct, select

from app.db import ForecastRecord
from app.models.forecast import (
    DailyForecastResult,
    DishForecast,
    DishIngredient,
    PlanFactRecord,
)
from app.repositories.base import BaseRepository


class ForecastsRepository(BaseRepository[ForecastRecord]):
    model = ForecastRecord

    async def save_forecast(self, forecast: DailyForecastResult) -> list[ForecastRecord]:
        method = forecast.method
        # Delete existing forecast for this date+method (supports force-regeneration)
        await self._session.execute(
            delete(ForecastRecord).where(
                ForecastRecord.date == forecast.date,
                ForecastRecord.method == method,
            )
        )
        records = []
        for dish in forecast.forecasts:
            ingredients_json = (
                json.dumps(
                    [ing.model_dump() for ing in dish.ingredients],
                    ensure_ascii=False,
                )
                if dish.ingredients
                else None
            )
            record = ForecastRecord(
                date=forecast.date,
                dish_id=dish.dish_id,
                dish_name=dish.dish_name,
                predicted_quantity=dish.predicted_quantity,
                confidence=dish.confidence,
                price=dish.price,
                key_factors=json.dumps(dish.key_factors, ensure_ascii=False) if dish.key_factors else None,
                ingredients=ingredients_json,
                weather=forecast.weather,
                is_holiday=forecast.is_holiday,
                notes=forecast.notes,
                method=method,
            )
            self._session.add(record)
            records.append(record)
        await self._session.flush()
        return records

    async def get_forecast(
        self, date: datetime.date, method: str = "ml",
    ) -> DailyForecastResult | None:
        stmt = select(ForecastRecord).where(
            ForecastRecord.date == date,
            ForecastRecord.method == method,
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return None

        forecasts: list[DishForecast] = []
        for r in rows:
            if not (r.price and r.price > 0):
                continue
            ingredients: list[DishIngredient] = []
            if r.ingredients:
                try:
                    raw = json.loads(r.ingredients)
                    ingredients = [DishIngredient(**item) for item in raw]
                except (json.JSONDecodeError, TypeError, ValueError):
                    ingredients = []
            forecasts.append(
                DishForecast(
                    dish_id=r.dish_id,
                    dish_name=r.dish_name,
                    predicted_quantity=r.predicted_quantity,
                    confidence=r.confidence,
                    key_factors=json.loads(r.key_factors) if r.key_factors else [],
                    price=r.price,
                    prediction_method="ml" if method == "ml_daily" else "ml",
                    ingredients=ingredients,
                )
            )

        total_revenue = round(
            sum((f.price or 0.0) * f.predicted_quantity for f in forecasts), 0
        )
        # Восстанавливаем границы недели для method="ml" (weekly) — они не
        # хранятся в БД, но выводятся детерминированно: понедельник недели
        # даты forecast.date, + 6 дней.
        week_start: datetime.date | None = None
        week_end: datetime.date | None = None
        if method == "ml":
            week_start = date - datetime.timedelta(days=date.weekday())
            week_end = week_start + datetime.timedelta(days=6)
        return DailyForecastResult(
            date=date,
            forecasts=forecasts,
            weather=rows[0].weather,
            is_holiday=rows[0].is_holiday,
            notes=rows[0].notes,
            method=method,
            ml_count=len(forecasts),
            fallback_count=0,
            total_revenue=total_revenue,
            week_start=week_start,
            week_end=week_end,
        )

    async def delete_obsolete_forecasts(
        self,
        active_dish_ids: set[str],
        *,
        method: str | None = None,
        date_from: datetime.date | None = None,
    ) -> int:
        """Delete forecast rows for dishes no longer in the active menu.

        Called after a retrain to clear stale predictions left over when a
        dish has been removed from the menu (its ml_model is deleted by
        `_cleanup_obsolete_models`, but the forecast row keyed by
        (date, method) for the matching week/day would otherwise linger
        in the cache and be served via `get_forecast`).

        Pass `method` to scope the cleanup to one granularity — weekly
        retrain should not nuke daily forecasts and vice versa. Pass
        `date_from` to preserve historical plan-fact rows (not normally
        needed: plan-fact queries already filter by active_dish_ids).
        """
        if not active_dish_ids:
            return 0
        stmt = delete(ForecastRecord).where(
            ForecastRecord.dish_id.notin_(active_dish_ids),
        )
        if method is not None:
            stmt = stmt.where(ForecastRecord.method == method)
        if date_from is not None:
            stmt = stmt.where(ForecastRecord.date >= date_from)
        result = await self._session.execute(stmt)
        return result.rowcount or 0

    async def get_forecast_dates(
        self, date_from: datetime.date, date_to: datetime.date,
    ) -> list[tuple[datetime.date, str]]:
        """Return distinct (date, method) pairs that have forecasts."""
        stmt = (
            select(distinct(ForecastRecord.date), ForecastRecord.method)
            .where(ForecastRecord.date >= date_from, ForecastRecord.date <= date_to)
            .order_by(ForecastRecord.date)
        )
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_plan_fact(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        actual_sales: list[dict],
        method: str = "ml",
        active_dish_ids: set[str] | None = None,
        active_dish_names: set[str] | None = None,
    ) -> list[PlanFactRecord]:
        # Normalize name-based filter once: lower + strip. When provided, this
        # filter takes priority over `active_dish_ids` — iiko often re-creates
        # the same dish under a new UUID, so name is the stable identifier.
        name_filter = (
            {n.strip().lower() for n in active_dish_names if n and n.strip()}
            if active_dish_names is not None
            else None
        )

        stmt = (
            select(ForecastRecord)
            .where(
                ForecastRecord.date >= date_from,
                ForecastRecord.date <= date_to,
                ForecastRecord.method == method,
            )
        )
        result = await self._session.execute(stmt)
        forecasts = list(result.scalars().all())

        # Build two lookup maps: by dish_id and by normalized dish_name.
        # Name-based matching handles iiko duplicate IDs for the same dish
        # (e.g. "Капучино" sold under 3 different IDs across departments).
        sales_by_id: dict[tuple[datetime.date, str], float] = {}
        sales_by_name: dict[tuple[datetime.date, str], float] = {}
        revenue_by_id: dict[tuple[datetime.date, str], float] = {}
        revenue_by_name: dict[tuple[datetime.date, str], float] = {}
        # All unique sale names per date for fuzzy matching
        sales_names_by_date: dict[datetime.date, dict[str, float]] = {}
        revenue_names_by_date: dict[datetime.date, dict[str, float]] = {}
        for sale in actual_sales:
            id_key = (sale["date"], sale["dish_id"])
            sales_by_id[id_key] = sales_by_id.get(id_key, 0) + sale["quantity"]
            revenue_by_id[id_key] = revenue_by_id.get(id_key, 0) + sale.get("total", 0.0)
            name = (sale.get("dish_name") or "").strip().lower()
            if name:
                name_key = (sale["date"], name)
                sales_by_name[name_key] = sales_by_name.get(name_key, 0) + sale["quantity"]
                revenue_by_name[name_key] = revenue_by_name.get(name_key, 0) + sale.get("total", 0.0)
                if sale["date"] not in sales_names_by_date:
                    sales_names_by_date[sale["date"]] = {}
                    revenue_names_by_date[sale["date"]] = {}
                sales_names_by_date[sale["date"]][name] = (
                    sales_names_by_date[sale["date"]].get(name, 0) + sale["quantity"]
                )
                revenue_names_by_date[sale["date"]][name] = (
                    revenue_names_by_date[sale["date"]].get(name, 0) + sale.get("total", 0.0)
                )

        records = []
        matched_sales: set[tuple[datetime.date, str]] = set()  # (date, name_lower)

        for f in forecasts:
            # Domain 3: restrict plan-fact to active dishes (Domain 1 scope).
            # Name-based filter wins when provided (handles iiko duplicate IDs
            # for the same dish — e.g. "Лимон 30 гр" under 3 different UUIDs).
            f_name_norm = f.dish_name.strip().lower()
            if name_filter is not None:
                if f_name_norm not in name_filter:
                    continue
            elif active_dish_ids is not None and f.dish_id not in active_dish_ids:
                continue
            # Prefer name-based match (aggregates across duplicate IDs),
            # fall back to ID-based match, then fuzzy match
            name_key = (f.date, f.dish_name.strip().lower())
            actual = sales_by_name.get(name_key)
            actual_rev = revenue_by_name.get(name_key)
            matched_name = f.dish_name.strip().lower()
            if actual is None:
                actual = sales_by_id.get((f.date, f.dish_id))
                actual_rev = revenue_by_id.get((f.date, f.dish_id))
            # Fuzzy fallback: substring match or token_set_ratio >= 80
            if actual is None:
                matched_name_fuzzy = self._fuzzy_match_name(
                    f.dish_name, f.date, sales_names_by_date,
                )
                if matched_name_fuzzy:
                    matched_name = matched_name_fuzzy
                    actual = sales_names_by_date.get(f.date, {}).get(matched_name, 0.0)
                    actual_rev = revenue_names_by_date.get(f.date, {}).get(matched_name, 0.0)
            if actual is not None:
                matched_sales.add((f.date, matched_name))
            if actual is None:
                actual = 0.0
            if actual_rev is None:
                actual_rev = 0.0

            # Revenue: use catalog price, fallback to avg from actuals
            catalog_price = f.price or 0.0
            avg_price = catalog_price or ((actual_rev / actual) if actual > 0 else 0.0)
            predicted_rev = round(f.predicted_quantity * avg_price, 0)
            actual_rev = round(actual_rev, 0)
            rev_denom = max(actual_rev, predicted_rev)
            rev_deviation = (
                ((actual_rev - predicted_rev) / rev_denom * 100)
                if rev_denom > 0
                else 0.0
            )

            denom = max(actual, f.predicted_quantity)
            deviation = (
                ((actual - f.predicted_quantity) / denom * 100)
                if denom > 0
                else 0.0
            )
            records.append(PlanFactRecord(
                date=f.date,
                dish_id=f.dish_id,
                dish_name=f.dish_name,
                predicted_quantity=f.predicted_quantity,
                actual_quantity=actual,
                deviation_pct=round(deviation, 2),
                predicted_revenue=predicted_rev,
                actual_revenue=actual_rev,
                revenue_deviation_pct=round(rev_deviation, 2),
            ))

        # Add unforecasted sales (predicted=0)
        for sale in actual_sales:
            name = (sale.get("dish_name") or "").strip().lower()
            if not name:
                continue
            # Domain 3: restrict unforecasted-sales rows to active dishes too.
            # Same priority rule as above — name-filter wins over id-filter.
            if name_filter is not None:
                if name not in name_filter:
                    continue
            elif (
                active_dish_ids is not None
                and sale.get("dish_id") not in active_dish_ids
            ):
                continue
            key = (sale["date"], name)
            if key in matched_sales:
                continue
            matched_sales.add(key)
            qty = sales_by_name.get(key, sale["quantity"])
            rev = revenue_by_name.get(key, sale.get("total", 0.0))
            records.append(PlanFactRecord(
                date=sale["date"],
                dish_id=sale.get("dish_id", ""),
                dish_name=sale.get("dish_name", ""),
                predicted_quantity=0.0,
                actual_quantity=qty,
                deviation_pct=-100.0,
                predicted_revenue=0.0,
                actual_revenue=round(rev, 0),
                revenue_deviation_pct=-100.0,
            ))

        # Drop noise rows where the dish neither was forecasted nor sold
        # (predicted=0 AND actual=0 → meaningless 0/0 that poisons MAPE).
        return [
            r for r in records
            if not (r.predicted_quantity == 0 and r.actual_quantity == 0)
        ]

    @staticmethod
    def _fuzzy_match_name(
        forecast_name: str,
        date: datetime.date,
        sales_names_by_date: dict[datetime.date, dict[str, float]],
    ) -> str | None:
        """Find the best matching sale name for a forecast dish via fuzzy matching."""
        date_sales = sales_names_by_date.get(date)
        if not date_sales:
            return None
        fn = forecast_name.strip().lower()
        # 1. Substring containment
        for sale_name in date_sales:
            if fn in sale_name or sale_name in fn:
                return sale_name
        # 2. Token set ratio
        best_score = 0.0
        best_name = None
        for sale_name in date_sales:
            score = fuzz.token_set_ratio(fn, sale_name)
            if score > best_score:
                best_score = score
                best_name = sale_name
        if best_score >= 80 and best_name is not None:
            return best_name
        return None
