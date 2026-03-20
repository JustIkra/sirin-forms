import datetime

RUSSIAN_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Новый год",
    (1, 2): "Новогодние каникулы",
    (1, 3): "Новогодние каникулы",
    (1, 4): "Новогодние каникулы",
    (1, 5): "Новогодние каникулы",
    (1, 6): "Новогодние каникулы",
    (1, 7): "Рождество Христово",
    (1, 8): "Новогодние каникулы",
    (2, 23): "День защитника Отечества",
    (3, 8): "Международный женский день",
    (5, 1): "Праздник Весны и Труда",
    (5, 9): "День Победы",
    (6, 12): "День России",
    (11, 4): "День народного единства",
}

RUSSIAN_MONTH_NAMES: dict[int, str] = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

RUSSIAN_WEEKDAY_NAMES: dict[int, str] = {
    0: "понедельник",
    1: "вторник",
    2: "среда",
    3: "четверг",
    4: "пятница",
    5: "суббота",
    6: "воскресенье",
}


def is_russian_holiday(date: datetime.date) -> tuple[bool, str | None]:
    key = (date.month, date.day)
    name = RUSSIAN_HOLIDAYS.get(key)
    return (True, name) if name else (False, None)


def is_pre_holiday(date: datetime.date) -> bool:
    tomorrow = date + datetime.timedelta(days=1)
    return is_russian_holiday(tomorrow)[0]


def get_calendar_context(date: datetime.date) -> dict:
    weekday = date.weekday()
    holiday, holiday_name = is_russian_holiday(date)
    return {
        "weekday": RUSSIAN_WEEKDAY_NAMES[weekday],
        "weekday_num": weekday,
        "is_weekend": weekday >= 5,
        "is_holiday": holiday,
        "holiday_name": holiday_name,
        "is_pre_holiday": is_pre_holiday(date),
        "month": RUSSIAN_MONTH_NAMES[date.month],
        "week_number": date.isocalendar()[1],
    }
