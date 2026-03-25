import datetime
import json

from rapidfuzz import fuzz
from sqlalchemy import delete, distinct, select

from app.db import ForecastRecord
from app.models.forecast import DailyForecastResult, DishForecast, PlanFactRecord
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
            record = ForecastRecord(
                date=forecast.date,
                dish_id=dish.dish_id,
                dish_name=dish.dish_name,
                predicted_quantity=dish.predicted_quantity,
                confidence=dish.confidence,
                key_factors=json.dumps(dish.key_factors, ensure_ascii=False) if dish.key_factors else None,
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
        self, date: datetime.date, method: str = "llm",
    ) -> DailyForecastResult | None:
        stmt = select(ForecastRecord).where(
            ForecastRecord.date == date,
            ForecastRecord.method == method,
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return None

        return DailyForecastResult(
            date=date,
            forecasts=[
                DishForecast(
                    dish_id=r.dish_id,
                    dish_name=r.dish_name,
                    predicted_quantity=r.predicted_quantity,
                    confidence=r.confidence,
                    key_factors=json.loads(r.key_factors) if r.key_factors else [],
                )
                for r in rows
            ],
            weather=rows[0].weather,
            is_holiday=rows[0].is_holiday,
            notes=rows[0].notes,
            method=method,
        )

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
        method: str = "llm",
    ) -> list[PlanFactRecord]:
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
        # All unique sale names per date for fuzzy matching
        sales_names_by_date: dict[datetime.date, dict[str, float]] = {}
        for sale in actual_sales:
            id_key = (sale["date"], sale["dish_id"])
            sales_by_id[id_key] = sales_by_id.get(id_key, 0) + sale["quantity"]
            name = (sale.get("dish_name") or "").strip().lower()
            if name:
                name_key = (sale["date"], name)
                sales_by_name[name_key] = sales_by_name.get(name_key, 0) + sale["quantity"]
                if sale["date"] not in sales_names_by_date:
                    sales_names_by_date[sale["date"]] = {}
                sales_names_by_date[sale["date"]][name] = (
                    sales_names_by_date[sale["date"]].get(name, 0) + sale["quantity"]
                )

        records = []
        for f in forecasts:
            # Prefer name-based match (aggregates across duplicate IDs),
            # fall back to ID-based match, then fuzzy match
            name_key = (f.date, f.dish_name.strip().lower())
            actual = sales_by_name.get(name_key)
            if actual is None:
                actual = sales_by_id.get((f.date, f.dish_id))
            # Fuzzy fallback: substring match or token_set_ratio >= 80
            if actual is None:
                actual = self._fuzzy_match_sales(
                    f.dish_name, f.date, sales_names_by_date,
                )
            if actual is None:
                actual = 0.0
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
            ))
        return records

    @staticmethod
    def _fuzzy_match_sales(
        forecast_name: str,
        date: datetime.date,
        sales_names_by_date: dict[datetime.date, dict[str, float]],
    ) -> float | None:
        """Try to match forecast dish name to actual sales via fuzzy matching."""
        date_sales = sales_names_by_date.get(date)
        if not date_sales:
            return None
        fn = forecast_name.strip().lower()
        # 1. Substring containment: "Хугарден" in "Хугарден бут. 0,44 л"
        for sale_name, qty in date_sales.items():
            if fn in sale_name or sale_name in fn:
                return qty
        # 2. Token set ratio (handles word reordering, partial overlap)
        best_score = 0.0
        best_qty = None
        for sale_name, qty in date_sales.items():
            score = fuzz.token_set_ratio(fn, sale_name)
            if score > best_score:
                best_score = score
                best_qty = qty
        if best_score >= 80:
            return best_qty
        return None
