"""MenuSnapshotsRepository — Domain 1 active-dish filter source.

NOTE: this is a skeleton populated by the parallel agent working on Domain 1.
The class shape here is the contract consumed by forecasters and the API —
do not remove methods; only add to them or implement their bodies more
specifically.
"""
import datetime
from collections.abc import Iterable

from sqlalchemy import delete, func, select

from app.db import MenuSnapshotRecord, ProductRecord
from app.repositories.base import BaseRepository


class MenuSnapshotsRepository(BaseRepository[MenuSnapshotRecord]):
    model = MenuSnapshotRecord

    async def replace_snapshot(
        self,
        snapshot_date: datetime.date,
        rows: Iterable[tuple[str, bool, bool]],
    ) -> int:
        """Wipe `snapshot_date` and insert fresh (dish_id, included_in_menu, in_stop_list) tuples."""
        await self._session.execute(
            delete(MenuSnapshotRecord).where(
                MenuSnapshotRecord.snapshot_date == snapshot_date,
            )
        )
        count = 0
        for dish_id, in_menu, stopped in rows:
            self._session.add(MenuSnapshotRecord(
                snapshot_date=snapshot_date,
                dish_id=dish_id,
                included_in_menu=in_menu,
                in_stop_list=stopped,
            ))
            count += 1
        await self._session.flush()
        return count

    async def get_snapshot_for_date(
        self, snapshot_date: datetime.date,
    ) -> list[MenuSnapshotRecord]:
        stmt = select(MenuSnapshotRecord).where(
            MenuSnapshotRecord.snapshot_date == snapshot_date,
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_dish_ids(self, snapshot_date: datetime.date) -> set[str]:
        """Dishes that passed Domain-1 filter on a given date."""
        stmt = select(MenuSnapshotRecord.dish_id).where(
            MenuSnapshotRecord.snapshot_date == snapshot_date,
            MenuSnapshotRecord.included_in_menu.is_(True),
            MenuSnapshotRecord.in_stop_list.is_(False),
        )
        result = await self._session.execute(stmt)
        return {row[0] for row in result.all()}

    async def get_latest_snapshot_date(self) -> datetime.date | None:
        stmt = select(func.max(MenuSnapshotRecord.snapshot_date))
        result = await self._session.execute(stmt)
        return result.scalar()

    async def get_latest_active_dish_ids(self) -> set[str]:
        latest = await self.get_latest_snapshot_date()
        if latest is None:
            return set()
        return await self.get_active_dish_ids(latest)

    async def get_active_dish_names(self, snapshot_date: datetime.date) -> set[str]:
        """Normalized names of dishes that passed Domain-1 filter on a given
        date. Joins snapshot → products to get the human-readable identifier.
        Using name (not UUID) is essential because iiko re-creates the same
        dish under new UUIDs — the name is the stable cross-system key."""
        stmt = (
            select(func.lower(func.trim(ProductRecord.name)))
            .join(
                MenuSnapshotRecord,
                MenuSnapshotRecord.dish_id == ProductRecord.id,
            )
            .where(
                MenuSnapshotRecord.snapshot_date == snapshot_date,
                MenuSnapshotRecord.included_in_menu.is_(True),
                MenuSnapshotRecord.in_stop_list.is_(False),
            )
        )
        result = await self._session.execute(stmt)
        return {row[0] for row in result.all() if row[0]}

    async def get_latest_active_dish_names(self) -> set[str]:
        latest = await self.get_latest_snapshot_date()
        if latest is None:
            return set()
        return await self.get_active_dish_names(latest)
