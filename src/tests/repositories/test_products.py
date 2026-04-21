from app.models.iiko import IikoProduct, ProductIngredient, ProductType
from app.repositories.products import ProductsRepository


def _make_product(
    id: str = "p1",
    name: str = "Пицца",
    product_type: ProductType = ProductType.DISH,
    price: float = 500.0,
    ingredients: list[ProductIngredient] | None = None,
) -> IikoProduct:
    return IikoProduct(
        id=id,
        name=name,
        code=None,
        product_type=product_type,
        price=price,
        included_in_menu=True,
        ingredients=ingredients or [],
    )


async def test_sync_empty_returns_zero(session):
    repo = ProductsRepository(session)
    assert await repo.sync_products([]) == 0


async def test_sync_inserts_product_and_ingredients(session):
    repo = ProductsRepository(session)
    p = _make_product(
        "p1",
        "Пицца",
        ingredients=[
            ProductIngredient(product_id="i1", name="Тесто", amount=0.3, unit="кг"),
            ProductIngredient(product_id="i2", name="Сыр", amount=0.1, unit="кг"),
        ],
    )
    count = await repo.sync_products([p])
    assert count == 1

    names = await repo.get_product_names()
    assert names == {"p1": "Пицца"}

    ingredients = await repo.get_ingredients_for_dish("p1")
    assert len(ingredients) == 2
    assert {i.product_id for i in ingredients} == {"i1", "i2"}


async def test_sync_dedupes_by_id(session):
    repo = ProductsRepository(session)
    first = _make_product("p1", "Старое имя")
    second = _make_product("p1", "Новое имя")

    count = await repo.sync_products([first, second])
    assert count == 1

    names = await repo.get_product_names()
    assert names["p1"] == "Новое имя"


async def test_sync_replaces_ingredients_on_update(session):
    repo = ProductsRepository(session)
    await repo.sync_products([
        _make_product("p1", ingredients=[
            ProductIngredient(product_id="i1", name="X", amount=1.0, unit="кг"),
        ]),
    ])
    await repo.sync_products([
        _make_product("p1", ingredients=[
            ProductIngredient(product_id="i2", name="Y", amount=2.0, unit="л"),
        ]),
    ])

    ingredients = await repo.get_ingredients_for_dish("p1")
    assert len(ingredients) == 1
    assert ingredients[0].product_id == "i2"
    assert ingredients[0].unit == "л"


async def test_get_ingredient_units_returns_names_and_units(session):
    repo = ProductsRepository(session)
    await repo.sync_products([
        _make_product("p1", ingredients=[
            ProductIngredient(product_id="i1", name="Мука", amount=0.3, unit="кг"),
            ProductIngredient(product_id="i2", name="Молоко", amount=0.2, unit="л"),
        ]),
    ])

    names, units = await repo.get_ingredient_units()
    assert names == {"i1": "Мука", "i2": "Молоко"}
    assert units == {"i1": "кг", "i2": "л"}
