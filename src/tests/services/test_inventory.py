"""Юнит-тесты для app.services.inventory — расчёт закупки на неделю."""
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.forecast import DailyForecastResult, DishForecast
from app.models.iiko import ProductIngredient
from app.services.inventory import InventoryService


def _make_settings(department_id: str | None = "dept-1") -> MagicMock:
    s = MagicMock()
    s.iiko_department_id = department_id
    return s


def _make_forecast(
    week_start: datetime.date,
    dishes: list[DishForecast],
    method: str = "ml",
) -> DailyForecastResult:
    return DailyForecastResult(
        date=week_start,
        forecasts=dishes,
        weather="",
        is_holiday=False,
        notes="",
        method=method,
    )


def _make_service(
    stock: list[dict] | None = None,
    product_names: dict[str, str] | None = None,
    ingredient_names: dict[str, str] | None = None,
    ingredient_units: dict[str, str] | None = None,
    forecast: DailyForecastResult | None = None,
    ingredients_by_dish: dict[str, list[ProductIngredient]] | None = None,
    department_id: str | None = "dept-1",
) -> InventoryService:
    iiko = MagicMock()
    iiko.get_balance_stores = AsyncMock(return_value=stock or [])

    forecasts_repo = MagicMock()
    forecasts_repo.get_forecast = AsyncMock(return_value=forecast)

    products_repo = MagicMock()
    products_repo.get_product_names = AsyncMock(return_value=product_names or {})
    products_repo.get_ingredient_units = AsyncMock(
        return_value=(ingredient_names or {}, ingredient_units or {})
    )

    async def _get_ingredients(dish_id):
        return (ingredients_by_dish or {}).get(dish_id, [])

    products_repo.get_ingredients_for_dish = AsyncMock(side_effect=_get_ingredients)

    async def _get_ingredients_map(dish_ids):
        return {did: (ingredients_by_dish or {}).get(did, []) for did in dish_ids}

    products_repo.get_ingredients_map = AsyncMock(side_effect=_get_ingredients_map)

    return InventoryService(
        iiko_client=iiko,
        forecasts_repo=forecasts_repo,
        products_repo=products_repo,
        settings=_make_settings(department_id),
    )


class TestWeeklyInventoryBasics:
    async def test_week_bounds_start_on_monday(self):
        service = _make_service()
        # Среда 15 апреля 2026 → понедельник 13 апреля, воскресенье 19 апреля
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        assert result.week_start == "2026-04-13"
        assert result.week_end == "2026-04-19"
        assert result.date == "2026-04-15"

    async def test_monday_target_stays_monday(self):
        service = _make_service()
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 13))
        assert result.week_start == "2026-04-13"
        assert result.week_end == "2026-04-19"

    async def test_sunday_target_same_week(self):
        service = _make_service()
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 19))
        assert result.week_start == "2026-04-13"
        assert result.week_end == "2026-04-19"

    async def test_empty_state_returns_no_items(self):
        service = _make_service()
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        assert result.items == []


class TestStockAggregation:
    async def test_stock_only_appears_when_named(self):
        """Остаток без названия продукта пропускается."""
        stock = [
            {"product": "p1", "amount": 10},
            {"product": "p2", "amount": 5},
        ]
        service = _make_service(
            stock=stock,
            product_names={"p1": "Мука"},  # p2 без имени
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        ids = {i.product_id for i in result.items}
        assert "p1" in ids
        assert "p2" not in ids

    async def test_stock_uses_ingredient_names_fallback(self):
        """Если имени нет в products — ищем в ingredient_names."""
        stock = [{"product": "ing1", "amount": 3}]
        service = _make_service(
            stock=stock,
            product_names={},
            ingredient_names={"ing1": "Соль"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        assert len(result.items) == 1
        assert result.items[0].product_name == "Соль"

    async def test_stock_aggregates_duplicate_entries(self):
        """Несколько записей остатков на один product_id суммируются."""
        stock = [
            {"product": "p1", "amount": 3},
            {"product": "p1", "amount": 5},
            {"product": "p1", "amount": 2},
        ]
        service = _make_service(
            stock=stock,
            product_names={"p1": "Мука"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        assert result.items[0].stock == 10.0

    async def test_productId_field_is_also_accepted(self):
        """iiko может отдавать поле productId вместо product."""
        stock = [{"productId": "p1", "amount": 7}]
        service = _make_service(
            stock=stock,
            product_names={"p1": "Мука"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        assert result.items[0].stock == 7.0

    async def test_missing_department_skips_stock(self):
        """Если department_id не задан — остатки не запрашиваются."""
        service = _make_service(department_id=None)
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        # Остатков нет и iiko не дёргался
        assert service._iiko.get_balance_stores.call_count == 0
        assert result.items == []


class TestNeedCalculation:
    async def test_dish_forecast_produces_ingredient_need(self):
        week_start = datetime.date(2026, 4, 13)
        forecast = _make_forecast(
            week_start,
            [
                DishForecast(
                    dish_id="dish1", dish_name="Борщ",
                    predicted_quantity=100.0, confidence=0.9, price=350.0,
                ),
            ],
        )
        service = _make_service(
            forecast=forecast,
            ingredients_by_dish={
                "dish1": [
                    ProductIngredient(product_id="ing1", name="Свёкла", amount=0.15, unit="кг"),
                    ProductIngredient(product_id="ing2", name="Капуста", amount=0.1, unit="кг"),
                ],
            },
            ingredient_names={"ing1": "Свёкла", "ing2": "Капуста"},
            ingredient_units={"ing1": "кг", "ing2": "кг"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        needs = {i.product_id: i.need for i in result.items}
        assert needs["ing1"] == 15.0  # 100 * 0.15
        assert needs["ing2"] == 10.0  # 100 * 0.1

    async def test_multiple_dishes_sum_same_ingredient(self):
        """Два блюда с одним ингредиентом — потребности суммируются."""
        week_start = datetime.date(2026, 4, 13)
        forecast = _make_forecast(
            week_start,
            [
                DishForecast(
                    dish_id="dish1", dish_name="Борщ",
                    predicted_quantity=50.0, confidence=0.9, price=350.0,
                ),
                DishForecast(
                    dish_id="dish2", dish_name="Щи",
                    predicted_quantity=30.0, confidence=0.8, price=300.0,
                ),
            ],
        )
        service = _make_service(
            forecast=forecast,
            ingredients_by_dish={
                "dish1": [ProductIngredient(product_id="cabbage", name="Капуста", amount=0.1, unit="кг")],
                "dish2": [ProductIngredient(product_id="cabbage", name="Капуста", amount=0.2, unit="кг")],
            },
            ingredient_names={"cabbage": "Капуста"},
            ingredient_units={"cabbage": "кг"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        cabbage = next(i for i in result.items if i.product_id == "cabbage")
        # 50 * 0.1 + 30 * 0.2 = 11
        assert cabbage.need == 11.0

    async def test_no_forecast_zero_need(self):
        service = _make_service(forecast=None)
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        assert result.items == []


class TestToBuyCalculation:
    async def test_to_buy_is_need_minus_stock(self):
        week_start = datetime.date(2026, 4, 13)
        forecast = _make_forecast(
            week_start,
            [DishForecast(
                dish_id="d1", dish_name="Борщ",
                predicted_quantity=100.0, confidence=0.9, price=350.0,
            )],
        )
        service = _make_service(
            stock=[{"product": "ing1", "amount": 3}],  # stock = 3
            product_names={"ing1": "Свёкла"},
            forecast=forecast,
            ingredients_by_dish={
                "d1": [ProductIngredient(product_id="ing1", name="Свёкла", amount=0.15, unit="кг")],
            },
            ingredient_units={"ing1": "кг"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        item = result.items[0]
        assert item.stock == 3.0
        assert item.need == 15.0  # 100 * 0.15
        assert item.to_buy == 12.0  # 15 - 3

    async def test_to_buy_clamped_to_zero_when_stock_exceeds_need(self):
        """Если остатков больше, чем нужно — to_buy = 0, не отрицательное."""
        week_start = datetime.date(2026, 4, 13)
        forecast = _make_forecast(
            week_start,
            [DishForecast(
                dish_id="d1", dish_name="Суп",
                predicted_quantity=10.0, confidence=0.8, price=200.0,
            )],
        )
        service = _make_service(
            stock=[{"product": "ing1", "amount": 100}],  # завалено
            product_names={"ing1": "Соль"},
            forecast=forecast,
            ingredients_by_dish={
                "d1": [ProductIngredient(product_id="ing1", name="Соль", amount=0.01, unit="кг")],
            },
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        item = result.items[0]
        assert item.need == 0.1  # 10 * 0.01
        assert item.to_buy == 0.0  # не отрицательное

    async def test_no_stock_full_need_to_buy(self):
        """Если остатков нет — нужно докупать всё."""
        week_start = datetime.date(2026, 4, 13)
        forecast = _make_forecast(
            week_start,
            [DishForecast(
                dish_id="d1", dish_name="Борщ",
                predicted_quantity=50.0, confidence=0.8, price=350.0,
            )],
        )
        service = _make_service(
            product_names={"ing1": "Свёкла"},
            forecast=forecast,
            ingredients_by_dish={
                "d1": [ProductIngredient(product_id="ing1", name="Свёкла", amount=0.2, unit="кг")],
            },
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        item = result.items[0]
        assert item.stock == 0.0
        assert item.to_buy == 10.0  # весь need


class TestSorting:
    async def test_items_sorted_by_name(self):
        stock = [
            {"product": "a", "amount": 1},
            {"product": "b", "amount": 1},
            {"product": "c", "amount": 1},
        ]
        service = _make_service(
            stock=stock,
            product_names={"a": "Яблоко", "b": "Авокадо", "c": "Банан"},
        )
        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        names = [i.product_name for i in result.items]
        # Сортировка алфавитная (Авокадо < Банан < Яблоко)
        assert names == sorted(names)


class TestResilience:
    async def test_iiko_error_does_not_crash(self):
        """При ошибке iiko сервис должен отдать результат с нулевыми остатками."""
        forecast = _make_forecast(
            datetime.date(2026, 4, 13),
            [DishForecast(
                dish_id="d1", dish_name="Борщ",
                predicted_quantity=10.0, confidence=0.8, price=350.0,
            )],
        )
        service = _make_service(
            forecast=forecast,
            ingredients_by_dish={
                "d1": [ProductIngredient(product_id="ing1", name="Свёкла", amount=0.15, unit="кг")],
            },
            product_names={"ing1": "Свёкла"},
        )
        # Симулируем ошибку
        service._iiko.get_balance_stores = AsyncMock(side_effect=Exception("iiko timeout"))

        result = await service.get_weekly_inventory(datetime.date(2026, 4, 15))
        # Сервис не упал, need посчитан, stock = 0
        assert len(result.items) == 1
        assert result.items[0].stock == 0.0
        assert result.items[0].need == 1.5  # 10 * 0.15
