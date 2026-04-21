import datetime

from app.models.iiko import SaleRecord
from app.repositories.sales import SalesRepository


def _make_sale(
    date: datetime.date,
    dish_id: str = "d1",
    dish_name: str = "Пицца",
    quantity: float = 2.0,
    price: float = 500.0,
) -> SaleRecord:
    return SaleRecord(
        date=date,
        dish_id=dish_id,
        dish_name=dish_name,
        quantity=quantity,
        price=price,
        total=quantity * price,
    )


async def test_bulk_upsert_empty_returns_zero(session):
    repo = SalesRepository(session)
    count = await repo.bulk_upsert_sales([])
    assert count == 0


async def test_bulk_upsert_inserts_rows(session):
    repo = SalesRepository(session)
    sales = [
        _make_sale(datetime.date(2026, 3, 1), "d1", "Пицца", 2.0),
        _make_sale(datetime.date(2026, 3, 1), "d2", "Суп", 3.0),
    ]
    count = await repo.bulk_upsert_sales(sales)
    assert count == 2

    stored = await repo.get_sales_by_period(
        datetime.date(2026, 3, 1), datetime.date(2026, 3, 1),
    )
    assert len(stored) == 2
    ids = {s.dish_id for s in stored}
    assert ids == {"d1", "d2"}


async def test_bulk_upsert_replaces_existing_date(session):
    repo = SalesRepository(session)
    d = datetime.date(2026, 3, 1)

    await repo.bulk_upsert_sales([_make_sale(d, "d1", "Старое", 2.0)])
    await repo.bulk_upsert_sales([_make_sale(d, "d2", "Новое", 5.0)])

    stored = await repo.get_sales_by_period(d, d)
    assert len(stored) == 1
    assert stored[0].dish_id == "d2"
    assert stored[0].dish_name == "Новое"


async def test_get_sales_by_dish_filters_by_id(session):
    repo = SalesRepository(session)
    dates = [datetime.date(2026, 3, d) for d in (1, 2, 3)]
    sales = [_make_sale(d, "d1", "Пицца", 2.0) for d in dates]
    sales.append(_make_sale(datetime.date(2026, 3, 2), "d2", "Другое", 1.0))
    await repo.bulk_upsert_sales(sales)

    result = await repo.get_sales_by_dish(
        "d1", datetime.date(2026, 3, 1), datetime.date(2026, 3, 3),
    )
    assert len(result) == 3
    assert {r.dish_id for r in result} == {"d1"}


async def test_get_sales_by_dish_name_case_insensitive(session):
    repo = SalesRepository(session)
    d = datetime.date(2026, 3, 1)
    await repo.bulk_upsert_sales(
        [_make_sale(d, "d1", "Капучино", 2.0)],
    )

    result = await repo.get_sales_by_dish_name("  КАПУЧИНО ", d, d)
    assert len(result) == 1
    assert result[0].dish_id == "d1"


async def test_get_daily_totals_aggregates(session):
    repo = SalesRepository(session)
    d1 = datetime.date(2026, 3, 1)
    d2 = datetime.date(2026, 3, 2)
    await repo.bulk_upsert_sales([
        _make_sale(d1, "a", "A", 2.0, 100.0),
        _make_sale(d1, "b", "B", 3.0, 50.0),
        _make_sale(d2, "a", "A", 1.0, 100.0),
    ])

    totals = await repo.get_daily_totals(d1, d2)
    assert len(totals) == 2

    d1_total = next(t for t in totals if t.date == d1)
    assert d1_total.total_quantity == 5.0
    assert d1_total.total_revenue == 350.0
    assert d1_total.dish_count == 2

    d2_total = next(t for t in totals if t.date == d2)
    assert d2_total.total_quantity == 1.0
    assert d2_total.dish_count == 1
