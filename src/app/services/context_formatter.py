import datetime
from collections import defaultdict

from app.models.iiko import SaleRecord
from app.models.weather import DailyWeather
from app.utils.calendar import get_calendar_context


def build_sales_data(
    historical: list[SaleRecord],
    recent: list[SaleRecord],
    target_date: datetime.date,
) -> str:
    lines: list[str] = []

    # 1. Weekly totals for top dishes (last 4 weeks)
    if recent:
        dish_vol: dict[str, float] = defaultdict(float)
        for s in recent:
            dish_vol[s.dish_name] += s.quantity
        top_dishes = sorted(dish_vol, key=dish_vol.get, reverse=True)[:20]

        # Group by week
        week_data: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for s in recent:
            if s.dish_name in top_dishes:
                days_ago = (target_date - s.date).days
                week_num = min(days_ago // 7, 3)
                week_data[week_num][s.dish_name] += s.quantity

        lines.append("## Продажи по неделям (последние 4 недели, топ-20 блюд)")
        header = f"{'Блюдо':<35} {'Нед-1':>7} {'Нед-2':>7} {'Нед-3':>7} {'Нед-4':>7}"
        lines.append(header)
        lines.append("-" * len(header))
        for dish in top_dishes:
            row = f"{dish[:35]:<35}"
            for w in range(4):
                qty = week_data[w].get(dish, 0)
                row += f" {qty:>7.0f}"
            lines.append(row)

        lines.append("")

        # Weekly totals
        lines.append("## Общие продажи по неделям")
        for w in range(4):
            total = sum(week_data[w].values())
            lines.append(f"  Неделя -{w + 1}: {total:.0f} порций")

        lines.append("")

        # Revenue last week
        week_ago = target_date - datetime.timedelta(days=7)
        last_week_sales = [s for s in recent if s.date > week_ago]
        total_revenue = sum(s.total for s in last_week_sales)
        lines.append(f"## Выручка за прошлую неделю: {total_revenue:,.0f} руб.")
    else:
        lines.append("## Данные о недавних продажах отсутствуют")

    return "\n".join(lines)


def build_weather_data_weekly(
    weather_records: list[DailyWeather],
    week_start: datetime.date,
    week_end: datetime.date,
) -> str:
    week_weather = [w for w in weather_records if week_start <= w.date <= week_end]
    if not week_weather:
        return "Данные о погоде за неделю недоступны."

    temps = [w.temp_avg for w in week_weather]
    precips = [w.precipitation for w in week_weather]
    lines = [
        f"Период: {week_start.isoformat()} — {week_end.isoformat()}",
        f"Температура: {min(temps):.0f}°C — {max(temps):.0f}°C (средняя {sum(temps)/len(temps):.0f}°C)",
        f"Осадки: {sum(precips):.1f} мм за неделю",
    ]
    for w in week_weather:
        lines.append(f"  {w.date.isoformat()} ({w.weather_main}): {w.temp_avg:.0f}°C, {w.precipitation:.1f} мм")
    return "\n".join(lines)


def build_calendar_info_weekly(week_start: datetime.date, week_end: datetime.date) -> str:
    lines = [
        f"Неделя: {week_start.isoformat()} — {week_end.isoformat()}",
        f"Неделя года: {week_start.isocalendar()[1]}",
    ]
    holidays = []
    weekends = 0
    for offset in range(7):
        d = week_start + datetime.timedelta(days=offset)
        ctx = get_calendar_context(d)
        if ctx["is_holiday"]:
            holidays.append(f"{d.isoformat()} — {ctx['holiday_name']}")
        if ctx["is_day_off"]:
            weekends += 1
    lines.append(f"Выходных/праздников: {weekends}")
    if holidays:
        for h in holidays:
            lines.append(f"Праздник: {h}")
    return "\n".join(lines)
