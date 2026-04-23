import datetime

from sqlalchemy import select, delete

from app.db import IngredientRecord, ProductRecord
from app.models.iiko import AssemblyChart, IikoProduct, ProductIngredient
from app.repositories.base import BaseRepository
from app.utils.dt import today


class ProductsRepository(BaseRepository[ProductRecord]):
    model = ProductRecord

    async def sync_products(self, products: list[IikoProduct]) -> int:
        if not products:
            return 0

        seen: dict[str, IikoProduct] = {}
        for p in products:
            seen[p.id] = p
        products = list(seen.values())

        for product in products:
            record = ProductRecord(
                id=product.id,
                name=product.name,
                code=product.code,
                product_type=product.product_type,
                price=product.price,
                included_in_menu=product.included_in_menu,
            )
            await self._session.merge(record)

        await self._session.flush()
        return len(products)

    async def sync_assembly_charts(
        self,
        charts: list[AssemblyChart],
        units_by_product: dict[str, str] | None = None,
    ) -> int:
        """Upsert assembly charts (tech cards) into `product_ingredients`.

        For each dish выбирается единственная актуальная карта: `date_to` пуст
        или >= сегодня; если несколько — берём с самым свежим `date_from`.
        `amountMiddle` нормализуется на `assembled_amount` (выход рецепта).
        Пропускаются тех.карты и ингредиенты, product_id которых отсутствует
        в таблице `products` (соблюдение FK).
        `units_by_product` — опциональная карта product_id → имя единицы
        (кг / л / шт / порц). Если не передано, `unit` пишется пустым.
        """
        if not charts:
            return 0

        today_ = today()
        active: dict[str, AssemblyChart] = {}
        for c in charts:
            if c.date_to is not None and c.date_to < today_:
                continue
            existing = active.get(c.assembled_product_id)
            if existing is None:
                active[c.assembled_product_id] = c
                continue
            existing_from = existing.date_from or datetime.date.min
            new_from = c.date_from or datetime.date.min
            if new_from > existing_from:
                active[c.assembled_product_id] = c

        if not active:
            return 0

        stmt = select(ProductRecord.id, ProductRecord.name)
        rows = (await self._session.execute(stmt)).all()
        known_ids = {r[0] for r in rows}
        names = {r[0]: r[1] for r in rows}

        synced = 0
        for dish_id, chart in active.items():
            if dish_id not in known_ids:
                continue
            yield_amt = chart.assembled_amount or 1.0
            if yield_amt <= 0:
                yield_amt = 1.0

            await self._session.execute(
                delete(IngredientRecord).where(
                    IngredientRecord.product_id == dish_id,
                )
            )
            for item in chart.items:
                if item.product_id not in known_ids:
                    continue
                unit = (
                    (units_by_product or {}).get(item.product_id) or ""
                )
                self._session.add(
                    IngredientRecord(
                        product_id=dish_id,
                        ingredient_id=item.product_id,
                        name=names.get(item.product_id, ""),
                        amount=item.amount / yield_amt,
                        unit=unit,
                    )
                )
            synced += 1

        await self._session.flush()
        return synced

    async def get_product_names(self) -> dict[str, str]:
        """Return mapping product_id → name for all products."""
        stmt = select(ProductRecord.id, ProductRecord.name)
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_ingredient_units(self) -> tuple[dict[str, str], dict[str, str]]:
        """Return (names, units) mappings from all ingredient records."""
        stmt = select(
            IngredientRecord.ingredient_id, IngredientRecord.name, IngredientRecord.unit
        )
        result = await self._session.execute(stmt)
        # Последняя запись побеждает при дубликатах
        names: dict[str, str] = {}
        units: dict[str, str] = {}
        for row in result.all():
            names[row[0]] = row[1]
            units[row[0]] = row[2]
        return names, units

    async def get_active_dishes(self) -> list[IikoProduct]:
        stmt = select(ProductRecord).where(ProductRecord.product_type == "dish")
        result = await self._session.execute(stmt)
        return [self._to_model(r) for r in result.scalars().all()]

    async def get_ingredients_for_dish(self, dish_id: str) -> list[ProductIngredient]:
        stmt = select(IngredientRecord).where(IngredientRecord.product_id == dish_id)
        result = await self._session.execute(stmt)
        return [
            ProductIngredient(
                product_id=r.ingredient_id,
                name=r.name,
                amount=r.amount,
                unit=r.unit,
            )
            for r in result.scalars().all()
        ]

    async def get_ingredients_map(
        self, dish_ids: list[str],
    ) -> dict[str, list[ProductIngredient]]:
        """Bulk-fetch ingredients for many dishes. Returns {dish_id: [ingredient, ...]}."""
        if not dish_ids:
            return {}
        stmt = select(IngredientRecord).where(
            IngredientRecord.product_id.in_(dish_ids),
        )
        result = await self._session.execute(stmt)
        out: dict[str, list[ProductIngredient]] = {did: [] for did in dish_ids}
        for r in result.scalars().all():
            out.setdefault(r.product_id, []).append(
                ProductIngredient(
                    product_id=r.ingredient_id,
                    name=r.name,
                    amount=r.amount,
                    unit=r.unit,
                )
            )
        return out

    @staticmethod
    def _to_model(record: ProductRecord) -> IikoProduct:
        return IikoProduct(
            id=record.id,
            name=record.name,
            code=record.code,
            product_type=record.product_type,
            price=record.price,
            included_in_menu=record.included_in_menu,
            ingredients=[
                ProductIngredient(
                    product_id=i.ingredient_id,
                    name=i.name,
                    amount=i.amount,
                    unit=i.unit,
                )
                for i in record.ingredients
            ],
        )
