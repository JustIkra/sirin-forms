import datetime

from app.models.forecast import DailyForecastResult, DishForecast
from app.repositories.forecasts import ForecastsRepository


def _make_forecast(
    date: datetime.date,
    dishes: list[DishForecast] | None = None,
    method: str = "ml",
) -> DailyForecastResult:
    return DailyForecastResult(
        date=date,
        forecasts=dishes or [
            DishForecast(
                dish_id="d1",
                dish_name="Пицца",
                predicted_quantity=10.0,
                confidence=0.8,
                key_factors=["weekday:пятница"],
                price=500.0,
            ),
        ],
        weather="Sunny",
        is_holiday=False,
        notes="Обычный день",
        method=method,
    )


async def test_save_then_get_forecast(session):
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)
    await repo.save_forecast(_make_forecast(d))

    got = await repo.get_forecast(d)
    assert got is not None
    assert got.method == "ml"
    assert got.weather == "Sunny"
    assert got.is_holiday is False
    assert len(got.forecasts) == 1
    assert got.forecasts[0].dish_name == "Пицца"
    assert got.forecasts[0].key_factors == ["weekday:пятница"]
    assert got.forecasts[0].price == 500.0


async def test_get_forecast_missing_returns_none(session):
    repo = ForecastsRepository(session)
    got = await repo.get_forecast(datetime.date(2026, 3, 2))
    assert got is None


async def test_save_forecast_overwrites_same_date_and_method(session):
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)
    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="a", dish_name="A",
            predicted_quantity=5.0, confidence=0.7, price=100.0,
        ),
    ]))
    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="b", dish_name="B",
            predicted_quantity=8.0, confidence=0.9, price=200.0,
        ),
    ]))

    got = await repo.get_forecast(d)
    assert got is not None
    assert len(got.forecasts) == 1
    assert got.forecasts[0].dish_id == "b"


async def test_save_forecast_different_methods_coexist(session):
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)
    await repo.save_forecast(_make_forecast(d, method="ml"))
    await repo.save_forecast(_make_forecast(d, method="fallback"))

    ml = await repo.get_forecast(d, method="ml")
    fb = await repo.get_forecast(d, method="fallback")
    assert ml is not None and fb is not None
    assert ml.method == "ml"
    assert fb.method == "fallback"


async def test_get_forecast_dates_returns_range(session):
    repo = ForecastsRepository(session)
    await repo.save_forecast(_make_forecast(datetime.date(2026, 3, 1)))
    await repo.save_forecast(_make_forecast(datetime.date(2026, 3, 5), method="fallback"))
    await repo.save_forecast(_make_forecast(datetime.date(2026, 2, 20)))  # out of range

    pairs = await repo.get_forecast_dates(
        datetime.date(2026, 3, 1), datetime.date(2026, 3, 10),
    )
    assert {p[0] for p in pairs} == {
        datetime.date(2026, 3, 1),
        datetime.date(2026, 3, 5),
    }


async def test_plan_fact_matches_by_name(session):
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)
    await repo.save_forecast(_make_forecast(d, [
        DishForecast(
            dish_id="X", dish_name="Пицца",
            predicted_quantity=10.0, confidence=0.8, price=500.0,
        ),
    ]))

    actual = [{
        "date": d,
        "dish_id": "Y",  # differs — name-based match should still win
        "dish_name": "пицца",
        "quantity": 8.0,
        "total": 4000.0,
    }]
    records = await repo.get_plan_fact(d, d, actual)
    assert len(records) == 1
    rec = records[0]
    assert rec.dish_name == "Пицца"
    assert rec.actual_quantity == 8.0
    assert rec.predicted_quantity == 10.0
    # Deviation = (8 - 10) / max(8, 10) * 100 = -20%
    assert rec.deviation_pct == -20.0


async def test_plan_fact_unforecasted_sale_appended(session):
    repo = ForecastsRepository(session)
    d = datetime.date(2026, 3, 2)

    actual = [{
        "date": d,
        "dish_id": "new",
        "dish_name": "Новинка",
        "quantity": 3.0,
        "total": 900.0,
    }]
    records = await repo.get_plan_fact(d, d, actual)
    assert len(records) == 1
    rec = records[0]
    assert rec.predicted_quantity == 0.0
    assert rec.actual_quantity == 3.0
    assert rec.deviation_pct == -100.0
