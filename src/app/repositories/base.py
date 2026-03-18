from typing import Generic, TypeVar

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic CRUD repository for SQLAlchemy models."""

    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, id: object) -> T | None:
        return await self._session.get(self.model, id)

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def create_many(self, entities: list[T]) -> list[T]:
        self._session.add_all(entities)
        await self._session.flush()
        return entities

    async def update(self, entity: T) -> T:
        merged = await self._session.merge(entity)
        await self._session.flush()
        return merged

    async def delete_by_id(self, id: object) -> None:
        stmt = delete(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        await self._session.execute(stmt)
        await self._session.flush()
