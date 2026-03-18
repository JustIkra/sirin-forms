from sqlalchemy import select, delete

from app.db import IngredientRecord, ProductRecord
from app.models.iiko import IikoProduct, ProductIngredient
from app.repositories.base import BaseRepository


class ProductsRepository(BaseRepository[ProductRecord]):
    model = ProductRecord

    async def sync_products(self, products: list[IikoProduct]) -> int:
        if not products:
            return 0

        product_ids = [p.id for p in products]

        # Delete ingredients for products being synced
        stmt = delete(IngredientRecord).where(
            IngredientRecord.product_id.in_(product_ids),
        )
        await self._session.execute(stmt)

        for product in products:
            existing = await self._session.get(ProductRecord, product.id)
            if existing:
                existing.name = product.name
                existing.code = product.code
                existing.product_type = product.product_type
                existing.price = product.price
            else:
                existing = ProductRecord(
                    id=product.id,
                    name=product.name,
                    code=product.code,
                    product_type=product.product_type,
                    price=product.price,
                )
                self._session.add(existing)

            for ing in product.ingredients:
                self._session.add(IngredientRecord(
                    product_id=product.id,
                    ingredient_id=ing.product_id,
                    name=ing.name,
                    amount=ing.amount,
                    unit=ing.unit,
                ))

        await self._session.flush()
        return len(products)

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

    @staticmethod
    def _to_model(record: ProductRecord) -> IikoProduct:
        return IikoProduct(
            id=record.id,
            name=record.name,
            code=record.code,
            product_type=record.product_type,
            price=record.price,
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
