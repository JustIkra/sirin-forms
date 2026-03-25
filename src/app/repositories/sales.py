import datetime

from sqlalchemy import select, func, delete

from app.db import SaleRecordDb
from app.models.iiko import DailySalesTotal, SaleRecord
from app.repositories.base import BaseRepository


class SalesRepository(BaseRepository[SaleRecordDb]):
    model = SaleRecordDb

    async def bulk_upsert_sales(self, records: list[SaleRecord]) -> int:
        if not records:
            return 0
        dates = {r.date for r in records}
        stmt = delete(SaleRecordDb).where(SaleRecordDb.date.in_(dates))
        await self._session.execute(stmt)

        entities = [
            SaleRecordDb(
                date=r.date,
                dish_id=r.dish_id,
                dish_name=r.dish_name,
                quantity=r.quantity,
                price=r.price,
                total=r.total,
            )
            for r in records
        ]
        self._session.add_all(entities)
        await self._session.flush()
        return len(entities)

    async def get_sales_by_period(
        self, date_from: datetime.date, date_to: datetime.date,
    ) -> list[SaleRecord]:
        stmt = (
            select(SaleRecordDb)
            .where(SaleRecordDb.date >= date_from, SaleRecordDb.date <= date_to)
            .order_by(SaleRecordDb.date)
        )
        result = await self._session.execute(stmt)
        return [self._to_model(r) for r in result.scalars().all()]

    async def get_sales_by_dish(
        self, dish_id: str, date_from: datetime.date, date_to: datetime.date,
    ) -> list[SaleRecord]:
        stmt = (
            select(SaleRecordDb)
            .where(
                SaleRecordDb.dish_id == dish_id,
                SaleRecordDb.date >= date_from,
                SaleRecordDb.date <= date_to,
            )
            .order_by(SaleRecordDb.date)
        )
        result = await self._session.execute(stmt)
        return [self._to_model(r) for r in result.scalars().all()]

    async def get_sales_by_dish_name(
        self, dish_name: str, date_from: datetime.date, date_to: datetime.date,
    ) -> list[SaleRecord]:
        stmt = (
            select(SaleRecordDb)
            .where(
                func.lower(SaleRecordDb.dish_name) == dish_name.strip().lower(),
                SaleRecordDb.date >= date_from,
                SaleRecordDb.date <= date_to,
            )
            .order_by(SaleRecordDb.date)
        )
        result = await self._session.execute(stmt)
        return [self._to_model(r) for r in result.scalars().all()]

    async def get_daily_totals(
        self, date_from: datetime.date, date_to: datetime.date,
    ) -> list[DailySalesTotal]:
        stmt = (
            select(
                SaleRecordDb.date,
                func.sum(SaleRecordDb.quantity).label("total_quantity"),
                func.sum(SaleRecordDb.total).label("total_revenue"),
                func.count(func.distinct(SaleRecordDb.dish_id)).label("dish_count"),
            )
            .where(SaleRecordDb.date >= date_from, SaleRecordDb.date <= date_to)
            .group_by(SaleRecordDb.date)
            .order_by(SaleRecordDb.date)
        )
        result = await self._session.execute(stmt)
        return [
            DailySalesTotal(
                date=row.date,
                total_quantity=row.total_quantity,
                total_revenue=row.total_revenue,
                dish_count=row.dish_count,
            )
            for row in result.all()
        ]

    @staticmethod
    def _to_model(record: SaleRecordDb) -> SaleRecord:
        return SaleRecord(
            date=record.date,
            dish_id=record.dish_id,
            dish_name=record.dish_name,
            quantity=record.quantity,
            price=record.price,
            total=record.total,
        )
