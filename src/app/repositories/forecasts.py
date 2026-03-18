import datetime
import json

from sqlalchemy import select

from app.db import ForecastRecord
from app.models.forecast import DailyForecastResult, DishForecast, PlanFactRecord
from app.repositories.base import BaseRepository


class ForecastsRepository(BaseRepository[ForecastRecord]):
    model = ForecastRecord

    async def save_forecast(self, forecast: DailyForecastResult) -> list[ForecastRecord]:
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
            )
            self._session.add(record)
            records.append(record)
        await self._session.flush()
        return records

    async def get_forecast(self, date: datetime.date) -> DailyForecastResult | None:
        stmt = select(ForecastRecord).where(ForecastRecord.date == date)
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
        )

    async def get_plan_fact(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        actual_sales: list[dict],
    ) -> list[PlanFactRecord]:
        stmt = (
            select(ForecastRecord)
            .where(ForecastRecord.date >= date_from, ForecastRecord.date <= date_to)
        )
        result = await self._session.execute(stmt)
        forecasts = list(result.scalars().all())

        sales_map: dict[tuple[datetime.date, str], float] = {}
        for sale in actual_sales:
            key = (sale["date"], sale["dish_id"])
            sales_map[key] = sales_map.get(key, 0) + sale["quantity"]

        records = []
        for f in forecasts:
            actual = sales_map.get((f.date, f.dish_id), 0.0)
            deviation = (
                ((actual - f.predicted_quantity) / f.predicted_quantity * 100)
                if f.predicted_quantity
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
