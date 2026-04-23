"""Юнит-тесты для app.utils.calendar — российские праздники и календарный контекст."""
import datetime
from unittest.mock import patch

from app.utils.calendar import (
    RESTAURANT_EVENTS,
    RUSSIAN_MONTH_NAMES,
    RUSSIAN_WEEKDAY_NAMES,
    get_calendar_context,
    is_day_off,
    is_pre_holiday,
    is_russian_holiday,
)


def _no_network():
    """Disable isdayoff.ru fetches in tests — return None to force library fallback."""
    return patch("app.utils.calendar._fetch_isdayoff", return_value=None)


class TestRussianNames:
    def test_all_months_have_names(self):
        assert len(RUSSIAN_MONTH_NAMES) == 12
        assert RUSSIAN_MONTH_NAMES[1] == "январь"
        assert RUSSIAN_MONTH_NAMES[12] == "декабрь"

    def test_all_weekdays_have_names(self):
        assert len(RUSSIAN_WEEKDAY_NAMES) == 7
        assert RUSSIAN_WEEKDAY_NAMES[0] == "понедельник"
        assert RUSSIAN_WEEKDAY_NAMES[6] == "воскресенье"


class TestIsRussianHoliday:
    def test_new_year(self):
        with _no_network():
            is_h, name = is_russian_holiday(datetime.date(2026, 1, 1))
        assert is_h is True
        assert name is not None

    def test_victory_day(self):
        with _no_network():
            is_h, name = is_russian_holiday(datetime.date(2026, 5, 9))
        assert is_h is True

    def test_ordinary_weekday(self):
        # Wednesday 15 April 2026 — не праздник
        with _no_network():
            is_h, _ = is_russian_holiday(datetime.date(2026, 4, 15))
        assert is_h is False

    def test_restaurant_event_valentines_day(self):
        with _no_network():
            is_h, name = is_russian_holiday(datetime.date(2026, 2, 14))
        assert is_h is True
        assert name == RESTAURANT_EVENTS[(2, 14)]

    def test_restaurant_event_halloween(self):
        with _no_network():
            is_h, name = is_russian_holiday(datetime.date(2026, 10, 31))
        assert is_h is True
        assert name == "Хэллоуин"

    def test_new_years_eve_is_restaurant_event(self):
        with _no_network():
            is_h, name = is_russian_holiday(datetime.date(2026, 12, 31))
        assert is_h is True
        assert name == "Новогодняя ночь"


class TestIsDayOff:
    def test_saturday_is_day_off(self):
        # 18 April 2026 — суббота
        with _no_network():
            assert is_day_off(datetime.date(2026, 4, 18)) is True

    def test_sunday_is_day_off(self):
        # 19 April 2026 — воскресенье
        with _no_network():
            assert is_day_off(datetime.date(2026, 4, 19)) is True

    def test_weekday_non_holiday(self):
        # 15 April 2026 — среда
        with _no_network():
            assert is_day_off(datetime.date(2026, 4, 15)) is False

    def test_new_year_is_day_off(self):
        with _no_network():
            assert is_day_off(datetime.date(2026, 1, 1)) is True


class TestIsPreHoliday:
    def test_day_before_new_year(self):
        # 31 дек — день перед 1 января (которое праздник), но 31 дек сам в RESTAURANT_EVENTS
        with _no_network():
            # 30 дек — предпраздничный перед 31 дек (ресторанный event) и 1 янв
            assert is_pre_holiday(datetime.date(2025, 12, 30)) is True

    def test_ordinary_day_not_pre_holiday(self):
        with _no_network():
            # 14 апр 2026 (вт) — завтра обычная среда
            assert is_pre_holiday(datetime.date(2026, 4, 14)) is False


class TestGetCalendarContext:
    def test_returns_all_keys(self):
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 4, 15))
        expected_keys = {
            "weekday", "weekday_num", "is_weekend", "is_holiday",
            "is_day_off", "holiday_name", "is_pre_holiday", "month", "week_number",
        }
        assert set(ctx.keys()) == expected_keys

    def test_wednesday_context(self):
        # 15 April 2026 = Wednesday
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 4, 15))
        assert ctx["weekday"] == "среда"
        assert ctx["weekday_num"] == 2
        assert ctx["is_weekend"] is False
        assert ctx["month"] == "апрель"

    def test_saturday_is_weekend(self):
        # 18 April 2026 = Saturday
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 4, 18))
        assert ctx["is_weekend"] is True
        assert ctx["weekday"] == "суббота"
        assert ctx["weekday_num"] == 5
        assert ctx["is_day_off"] is True

    def test_sunday_is_weekend(self):
        # 19 April 2026 = Sunday
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 4, 19))
        assert ctx["is_weekend"] is True
        assert ctx["weekday_num"] == 6

    def test_week_number(self):
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 1, 5))  # ISO week 2 of 2026
        assert ctx["week_number"] == datetime.date(2026, 1, 5).isocalendar()[1]

    def test_new_year_holiday_context(self):
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 1, 1))
        assert ctx["is_holiday"] is True
        assert ctx["holiday_name"] is not None
        assert ctx["month"] == "январь"

    def test_restaurant_event_marked_as_holiday(self):
        with _no_network():
            ctx = get_calendar_context(datetime.date(2026, 2, 14))
        assert ctx["is_holiday"] is True
        assert ctx["holiday_name"] == "День святого Валентина"
