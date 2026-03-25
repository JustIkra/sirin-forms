import datetime

from sqlalchemy import delete, select

from app.db import MLModelRecord
from app.repositories.base import BaseRepository


class MLModelsRepository(BaseRepository[MLModelRecord]):
    model = MLModelRecord

    async def get_latest_model(self, dish_id: str) -> MLModelRecord | None:
        stmt = (
            select(MLModelRecord)
            .where(MLModelRecord.dish_id == dish_id)
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
    ) -> MLModelRecord:
        # Delete old models for this dish
        await self._session.execute(
            delete(MLModelRecord).where(MLModelRecord.dish_id == dish_id)
        )
        record = MLModelRecord(
            dish_id=dish_id,
            dish_name=dish_name,
            model_blob=model_blob,
            metrics=metrics,
            feature_names=feature_names,
            samples_count=samples_count,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_all_models(self) -> list[MLModelRecord]:
        stmt = select(MLModelRecord).order_by(MLModelRecord.dish_name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_models(self, dish_id: str) -> None:
        await self._session.execute(
            delete(MLModelRecord).where(MLModelRecord.dish_id == dish_id)
        )
        await self._session.flush()
