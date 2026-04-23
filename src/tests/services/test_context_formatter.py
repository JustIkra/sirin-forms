"""Юнит-тесты для app.services.context_formatter — подготовка контекста для LLM."""
import datetime

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.services.context_formatter import (
    build_calendar_info_weekly,
    build_sales_data,
    build_weather_data_weekly,
)


def _make_sale(date: datetime.date, dish: str, qty: float, price: float = 350.0) -> SaleRecord:
    return SaleRecord(
        date=date,
        dish_id=dish.lower(),
        dish_name=dish,
        quantity=qty,
        price=price,
        total=qty * price,
    )


def _make_weather(date: datetime.date, temp: float, precip: float = 0.0) -> DailyWeather:
    return DailyWeather(
        date=date,
        temp_min=temp - 3,
        temp_max=temp + 3,
        temp_avg=temp,
        precipitation=precip,
        weather_main="Clear",
        humidity=60,
        wind_speed=2.0,
    )


class TestBuildSalesData:
    def test_empty_recent_returns_fallback_text(self):
        result = build_sales_data(historical=[], recent=[], target_date=datetime.date(2026, 4, 15))
        assert "отсутствуют" in result.lower()

    def test_contains_weekly_headers(self):
        target = datetime.date(2026, 4, 15)
        recent = [_make_sale(target - datetime.timedelta(days=2), "Борщ", 10)]
        result = build_sales_data([], recent, target)
        assert "Продажи по неделям" in result
        assert "Общие продажи по неделям" in result
        assert "Выручка за прошлую неделю" in result

    def test_shows_top_dishes(self):
        target = datetime.date(2026, 4, 15)
        recent = [
            _make_sale(target - datetime.timedelta(days=1), "Борщ", 20),
            _make_sale(target - datetime.timedelta(days=1), "Салат", 5),
        ]
        result = build_sales_data([], recent, target)
        assert "Борщ" in result
        assert "Салат" in result

    def test_revenue_includes_currency(self):
        target = datetime.date(2026, 4, 15)
        recent = [_make_sale(target - datetime.timedelta(days=2), "Борщ", 10, price=300)]
        result = build_sales_data([], recent, target)
        assert "руб" in result.lower()


class TestBuildWeatherDataWeekly:
    def test_no_weather_returns_unavailable(self):
        result = build_weather_data_weekly(
            [], datetime.date(2026, 4, 13), datetime.date(2026, 4, 19)
        )
        assert "недоступны" in result.lower()

    def test_filters_weather_by_week_range(self):
        """Погода вне указанной недели отфильтровывается."""
        week_start = datetime.date(2026, 4, 13)
        week_end = datetime.date(2026, 4, 19)
        records = [
            _make_weather(datetime.date(2026, 4, 10), 5.0),   # outside
            _make_weather(datetime.date(2026, 4, 14), 8.0),   # inside
            _make_weather(datetime.date(2026, 4, 25), 15.0),  # outside
        ]
        result = build_weather_data_weekly(records, week_start, week_end)
        assert "2026-04-14" in result
        assert "2026-04-10" not in result
        assert "2026-04-25" not in result

    def test_temperature_range_shown(self):
        week_start = datetime.date(2026, 4, 13)
        week_end = datetime.date(2026, 4, 19)
        records = [
            _make_weather(datetime.date(2026, 4, 13), 5.0),
            _make_weather(datetime.date(2026, 4, 14), 10.0),
            _make_weather(datetime.date(2026, 4, 15), 15.0),
        ]
        result = build_weather_data_weekly(records, week_start, week_end)
        # min/max температуры
        assert "5°C" in result
        assert "15°C" in result

    def test_precipitation_sum(self):
        week_start = datetime.date(2026, 4, 13)
        week_end = datetime.date(2026, 4, 19)
        records = [
            _make_weather(datetime.date(2026, 4, 13), 5.0, precip=1.5),
            _make_weather(datetime.date(2026, 4, 14), 6.0, precip=2.0),
        ]
        result = build_weather_data_weekly(records, week_start, week_end)
        assert "3.5 мм" in result


class TestBuildCalendarInfoWeekly:
    def test_shows_week_range(self):
        result = build_calendar_info_weekly(
            datetime.date(2026, 4, 13), datetime.date(2026, 4, 19)
        )
        assert "2026-04-13" in result
        assert "2026-04-19" in result

    def test_shows_week_number(self):
        week_start = datetime.date(2026, 4, 13)
        week_end = datetime.date(2026, 4, 19)
        result = build_calendar_info_weekly(week_start, week_end)
        assert f"Неделя года: {week_start.isocalendar()[1]}" in result

    def test_counts_weekends(self):
        # 13-19 апреля: сб 18, вс 19 → 2 выходных
        result = build_calendar_info_weekly(
            datetime.date(2026, 4, 13), datetime.date(2026, 4, 19)
        )
        assert "Выходных/праздников: 2" in result

    def test_lists_holidays_in_week(self):
        # 1-7 января 2026 — новогодние каникулы
        result = build_calendar_info_weekly(
            datetime.date(2026, 1, 1), datetime.date(2026, 1, 7)
        )
        assert "Праздник:" in result
