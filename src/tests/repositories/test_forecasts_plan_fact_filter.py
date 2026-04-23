"""Plan-fact Domain 3 filter tests.

Ensures `ForecastsRepository.get_plan_fact` supports an `active_dish_ids`
filter (Domain 1 scope) and drops meaningless zero/zero rows.
"""
import datetime

import pytest

from app.models.forecast import DailyForecastResult, DishForecast
from app.repositories.forecasts import ForecastsRepository


def _make_forecast(
    date: datetime.date,
    dishes: list[DishForecast],
    method: str = "ml",
) -> DailyForecastResult:
    return DailyForecastResult(
        date=date,
        forecasts=dishes,
        weather="Sunny",
        is_holiday=False,
        notes=None,
        method=method,
    )


@pytest.mark.asyncio
async def test_plan_fact_filters_by_active_dish_ids(session):
    """Only dishes in active_dish_ids are kept — both forecasted and
    unforecasted-but-sold dishes outside the set are dropped."""
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)

    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="d1", dish_name="Пицца",
            predicted_quantity=10.0, confidence=0.8, price=500.0,
        ),
        DishForecast(
            dish_id="d2", dish_name="Бургер",
            predicted_quantity=5.0, confidence=0.7, price=400.0,
        ),
    ]))

    actual = [
        {"date": d, "dish_id": "d1", "dish_name": "Пицца",
         "quantity": 8.0, "total": 4000.0},
        {"date": d, "dish_id": "d2", "dish_name": "Бургер",
         "quantity": 4.0, "total": 1600.0},
        {"date": d, "dish_id": "d3", "dish_name": "Суп",
         "quantity": 2.0, "total": 600.0},  # unforecasted and outside scope
    ]

    records = await repo.get_plan_fact(
        d, d, actual, active_dish_ids={"d1"},
    )
    # Only d1 survives: d2 forecasted but outside scope, d3 unforecasted and outside scope
    assert len(records) == 1
    assert records[0].dish_id == "d1"
    assert records[0].predicted_quantity == 10.0
    assert records[0].actual_quantity == 8.0


@pytest.mark.asyncio
async def test_plan_fact_drops_zero_zero_dishes(session):
    """Dish with predicted=0 AND actual=0 is noise — must be dropped."""
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)

    # Forecast: one dish predicted=5, one dish predicted=0 (not in menu / low conf)
    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="d1", dish_name="Пицца",
            predicted_quantity=5.0, confidence=0.8, price=500.0,
        ),
        DishForecast(
            dish_id="d2", dish_name="Редкое",
            predicted_quantity=0.0, confidence=0.3, price=300.0,
        ),
    ]))

    actual = [
        {"date": d, "dish_id": "d1", "dish_name": "Пицца",
         "quantity": 5.0, "total": 2500.0},
        # no sales for d2 -> predicted=0, actual=0 -> must be filtered
    ]

    records = await repo.get_plan_fact(d, d, actual)
    # d2 should be dropped (0/0 noise); d1 kept
    ids = {r.dish_id for r in records}
    assert "d1" in ids
    assert "d2" not in ids


@pytest.mark.asyncio
async def test_plan_fact_keeps_miss_predicted_zero_actual_positive(session):
    """Dish that WAS sold but NOT forecasted and IS in active_dish_ids must
    be kept — it's a legitimate model miss that should impact MAPE."""
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)

    # No saved forecast for d1; d1 IS in active_dish_ids and has actual sales
    actual = [
        {"date": d, "dish_id": "d1", "dish_name": "Пицца",
         "quantity": 7.0, "total": 3500.0},
    ]

    records = await repo.get_plan_fact(
        d, d, actual, active_dish_ids={"d1"},
    )
    assert len(records) == 1
    rec = records[0]
    assert rec.dish_id == "d1"
    assert rec.predicted_quantity == 0.0
    assert rec.actual_quantity == 7.0
    assert rec.deviation_pct == -100.0


@pytest.mark.asyncio
async def test_plan_fact_matches_forecast_and_sale_across_duplicate_dish_ids(session):
    """Real-world scenario: iiko has two dish_id for the same dish name.
    The model trained on the OLD id (stale), current sales come under the
    NEW id. Active-dish filter must recognize the dish by normalized name
    (not UUID) so prediction (old id) and actual (new id) merge into a
    single row with predicted=actual and deviation≈0."""
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 4, 13)

    # Forecast was saved under the OLD UUID
    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="old-uuid-lemon", dish_name="Лимон 30 гр",
            predicted_quantity=23.0, confidence=0.8, price=30.0,
        ),
    ]))

    # Sales came in under the NEW UUID (iiko re-created the dish)
    actual = [
        {"date": d, "dish_id": "new-uuid-lemon", "dish_name": "Лимон 30 гр",
         "quantity": 23.0, "total": 690.0},
    ]

    # Snapshot knows only the NEW UUID as active — the OLD one is inactive
    records = await repo.get_plan_fact(
        d, d, actual,
        active_dish_names={"лимон 30 гр"},
    )

    assert len(records) == 1, f"expected single merged row, got {records}"
    rec = records[0]
    assert rec.predicted_quantity == 23.0
    assert rec.actual_quantity == 23.0
    assert abs(rec.deviation_pct) < 0.01, (
        f"deviation should be ~0% for matching forecast/actual, got {rec.deviation_pct}"
    )


@pytest.mark.asyncio
async def test_plan_fact_active_dish_names_filters_inactive_dish(session):
    """Dishes whose normalized name is NOT in active_dish_names are dropped
    from both forecasted and unforecasted rows (parity with active_dish_ids)."""
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 4, 13)

    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="d-active", dish_name="Пицца",
            predicted_quantity=10.0, confidence=0.8, price=500.0,
        ),
        DishForecast(
            dish_id="d-inactive", dish_name="Старое блюдо",
            predicted_quantity=5.0, confidence=0.7, price=400.0,
        ),
    ]))
    actual = [
        {"date": d, "dish_id": "d-active", "dish_name": "Пицца",
         "quantity": 8.0, "total": 4000.0},
        {"date": d, "dish_id": "d-inactive", "dish_name": "Старое блюдо",
         "quantity": 2.0, "total": 800.0},
    ]

    records = await repo.get_plan_fact(
        d, d, actual, active_dish_names={"пицца"},
    )
    assert len(records) == 1
    assert records[0].dish_name == "Пицца"
