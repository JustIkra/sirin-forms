from __future__ import annotations

import datetime
import logging
import urllib.request
from typing import Optional

import holidays

logger = logging.getLogger(__name__)

# Primary source: holidays library (knows Russian public holidays + yearly transfers)
_ru_holidays: Optional[holidays.Russia] = None


def _get_ru_holidays(year: int) -> holidays.Russia:
    global _ru_holidays
    if _ru_holidays is None or year not in _ru_holidays.years:
        _ru_holidays = holidays.Russia(years=range(2015, year + 2))
    return _ru_holidays


# Fallback B: isdayoff.ru production calendar cache
_isdayoff_cache: dict[tuple[int, int], str] = {}


def _fetch_isdayoff(year: int, month: int) -> Optional[str]:
    """Fetch production calendar from isdayoff.ru. Returns string of 0/1/2 per day."""
    key = (year, month)
    if key in _isdayoff_cache:
        return _isdayoff_cache[key]
    try:
        url = f"https://isdayoff.ru/api/getdata?year={year}&month={month}"
        req = urllib.request.Request(url, headers={"User-Agent": "GurmanAnalytics/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode()
            if data and all(c in "012" for c in data):
                _isdayoff_cache[key] = data
                return data
    except Exception:
        logger.debug("isdayoff.ru unavailable for %d-%02d", year, month, exc_info=True)
    return None


# Unofficial but restaurant-significant dates
RESTAURANT_EVENTS: dict[tuple[int, int], str] = {
    (2, 14): "День святого Валентина",
    (3, 7): "Предпраздничный (8 марта)",
    (10, 31): "Хэллоуин",
    (12, 25): "Католическое Рождество",
    (12, 31): "Новогодняя ночь",
}


RUSSIAN_MONTH_NAMES: dict[int, str] = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель",
    5: "май", 6: "июнь", 7: "июль", 8: "август",
    9: "сентябрь", 10: "октябрь", 11: "ноябрь", 12: "декабрь",
}

RUSSIAN_WEEKDAY_NAMES: dict[int, str] = {
    0: "понедельник", 1: "вторник", 2: "среда", 3: "четверг",
    4: "пятница", 5: "суббота", 6: "воскресенье",
}


def is_russian_holiday(date: datetime.date) -> tuple[bool, str | None]:
    """Check if date is a Russian public holiday.

    Strategy: holidays library first, isdayoff.ru fallback for transfers.
    """
    ru = _get_ru_holidays(date.year)

    # Primary: holidays library
    if date in ru:
        return True, ru[date]

    # Fallback: isdayoff.ru (catches transfers the library may not know yet)
    isdayoff_data = _fetch_isdayoff(date.year, date.month)
    if isdayoff_data and date.day <= len(isdayoff_data):
        code = isdayoff_data[date.day - 1]
        if code == "1" and date.weekday() < 5:
            # Weekday marked as off but not in holidays lib = transfer day
            return True, "Перенесённый выходной"

    # Restaurant events (not public holidays, but affect demand)
    event = RESTAURANT_EVENTS.get((date.month, date.day))
    if event:
        return True, event

    return False, None


def is_day_off(date: datetime.date) -> bool:
    """Check if date is a non-working day (holiday, weekend, or transferred day off)."""
    if date.weekday() >= 5:
        return True
    is_h, _ = is_russian_holiday(date)
    return is_h


def is_pre_holiday(date: datetime.date) -> bool:
    tomorrow = date + datetime.timedelta(days=1)
    is_h, _ = is_russian_holiday(tomorrow)
    if is_h:
        return True
    # Also check isdayoff for shortened days (code "2")
    isdayoff_data = _fetch_isdayoff(date.year, date.month)
    if isdayoff_data and date.day <= len(isdayoff_data):
        return isdayoff_data[date.day - 1] == "2"
    return False


def get_calendar_context(date: datetime.date) -> dict:
    weekday = date.weekday()
    holiday, holiday_name = is_russian_holiday(date)
    return {
        "weekday": RUSSIAN_WEEKDAY_NAMES[weekday],
        "weekday_num": weekday,
        "is_weekend": weekday >= 5,
        "is_holiday": holiday,
        "is_day_off": is_day_off(date),
        "holiday_name": holiday_name,
        "is_pre_holiday": is_pre_holiday(date),
        "month": RUSSIAN_MONTH_NAMES[date.month],
        "week_number": date.isocalendar()[1],
    }
