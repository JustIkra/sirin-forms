import datetime

from sqlalchemy import delete, func, select

from app.db import MLModelRecord
from app.repositories.base import BaseRepository


class MLModelsRepository(BaseRepository[MLModelRecord]):
    model = MLModelRecord

    async def get_latest_model(
        self, dish_id: str, dish_name: str | None = None, granularity: str = "weekly",
    ) -> MLModelRecord | None:
        # Try by ID first
        stmt = (
            select(MLModelRecord)
            .where(MLModelRecord.dish_id == dish_id, MLModelRecord.granularity == granularity)
            .order_by(MLModelRecord.trained_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        record = result.scalars().first()
        if record or not dish_name:
            return record
        # Fallback: match by name (handles iiko duplicate IDs)
        stmt = (
            select(MLModelRecord)
            .where(
                func.lower(func.trim(MLModelRecord.dish_name)) == dish_name.strip().lower(),
                MLModelRecord.granularity == granularity,
            )
            .order_by(MLModelRecord.trained_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def save_model(
        self,
        dish_id: str,
        dish_name: str,
        model_blob: bytes,
        metrics: dict | None = None,
        feature_names: list[str] | None = None,
        samples_count: int = 0,
        granularity: str = "weekly",
    ) -> MLModelRecord:
        # Delete old models for this dish + granularity
        await self._session.execute(
            delete(MLModelRecord).where(
                MLModelRecord.dish_id == dish_id,
                MLModelRecord.granularity == granularity,
            )
        )
        record = MLModelRecord(
            dish_id=dish_id,
            dish_name=dish_name,
            model_blob=model_blob,
            metrics=metrics,
            feature_names=feature_names,
            samples_count=samples_count,
            granularity=granularity,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_all_models(self, granularity: str | None = None) -> list[MLModelRecord]:
        stmt = select(MLModelRecord)
        if granularity:
            stmt = stmt.where(MLModelRecord.granularity == granularity)
        stmt = stmt.order_by(MLModelRecord.dish_name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_models(self, granularity: str | None = None) -> int:
        stmt = select(func.count()).select_from(MLModelRecord)
        if granularity:
            stmt = stmt.where(MLModelRecord.granularity == granularity)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_models(self, dish_id: str, granularity: str | None = None) -> None:
        stmt = delete(MLModelRecord).where(MLModelRecord.dish_id == dish_id)
        if granularity:
            stmt = stmt.where(MLModelRecord.granularity == granularity)
        await self._session.execute(stmt)
        await self._session.flush()
