import datetime
from collections import defaultdict

from app.models.iiko import IikoProduct, SaleRecord
from app.models.weather import DailyWeather
from app.utils.calendar import get_calendar_context


class PromptBuilder:

    @staticmethod
    def build_sales_data(
        historical: list[SaleRecord],
        recent: list[SaleRecord],
        target_date: datetime.date,
    ) -> str:
        target_weekday = target_date.weekday()
        lines: list[str] = []

        # 1. Historical stats for the same weekday, grouped by dish
        same_weekday = [s for s in historical if s.date.weekday() == target_weekday]
        dish_stats: dict[str, list[float]] = defaultdict(list)
        for sale in same_weekday:
            dish_stats[sale.dish_name].append(sale.quantity)

        if dish_stats:
            lines.append("## Продажи в этот же день недели (исторические)")
            lines.append(f"{'Блюдо':<40} {'Среднее':>8} {'Мин':>6} {'Макс':>6}")
            lines.append("-" * 62)
            for dish_name, quantities in sorted(dish_stats.items()):
                avg = sum(quantities) / len(quantities)
                lines.append(
                    f"{dish_name:<40} {avg:>8.1f} {min(quantities):>6.0f} {max(quantities):>6.0f}"
                )
        else:
            lines.append("## Исторические данные за этот день недели отсутствуют")

        lines.append("")

        # 2. Trend: average daily sales per week for last 4 weeks
        if recent:
            lines.append("## Тренд продаж (последние 4 недели, среднее в день)")
            week_totals: dict[int, list[float]] = defaultdict(list)
            for sale in recent:
                days_ago = (target_date - sale.date).days
                week_num = min(days_ago // 7, 3)
                week_totals[week_num].append(sale.quantity)

            for week in range(4):
                quantities = week_totals.get(week, [])
                if quantities:
                    days_in_week = min(7, len({s.date for s in recent if (target_date - s.date).days // 7 == week})) or 1
                    total = sum(quantities)
                    lines.append(f"  Неделя -{week + 1}: {total / days_in_week:.1f} порций/день (всего {total:.0f})")
                else:
                    lines.append(f"  Неделя -{week + 1}: нет данных")

            lines.append("")

            # 3. Total revenue last 7 days
            week_ago = target_date - datetime.timedelta(days=7)
            last_week_sales = [s for s in recent if s.date > week_ago]
            total_revenue = sum(s.total for s in last_week_sales)
            lines.append(f"## Выручка за последние 7 дней: {total_revenue:,.0f} руб.")
        else:
            lines.append("## Данные о недавних продажах отсутствуют")

        return "\n".join(lines)

    @staticmethod
    def build_weather_data(weather: DailyWeather | None) -> str:
        if weather is None:
            return "Прогноз погоды недоступен."

        lines = [
            f"Температура: {weather.temp_min:.0f}°C — {weather.temp_max:.0f}°C (средняя {weather.temp_avg:.0f}°C)",
            f"Погода: {weather.weather_main}",
            f"Осадки: {weather.precipitation:.1f} мм",
        ]
        if weather.humidity is not None:
            lines.append(f"Влажность: {weather.humidity}%")
        if weather.wind_speed is not None:
            lines.append(f"Ветер: {weather.wind_speed} м/с")
        return "\n".join(lines)

    @staticmethod
    def build_calendar_info(target_date: datetime.date) -> str:
        ctx = get_calendar_context(target_date)
        lines = [
            f"Дата: {target_date.isoformat()}",
            f"День недели: {ctx['weekday']}",
            f"Месяц: {ctx['month']}",
            f"Неделя года: {ctx['week_number']}",
        ]
        if ctx["is_weekend"]:
            lines.append("Выходной день")
        if ctx["is_holiday"]:
            lines.append(f"Праздник: {ctx['holiday_name']}")
        if ctx["is_pre_holiday"]:
            lines.append("Предпраздничный день")
        return "\n".join(lines)

    @staticmethod
    def build_menu_info(dishes: list[IikoProduct]) -> str:
        if not dishes:
            return "Меню не загружено."
        lines = ["Активные блюда в меню:"]
        for dish in sorted(dishes, key=lambda d: d.name):
            price_str = f" — {dish.price:.0f} руб." if dish.price else ""
            lines.append(f"  - {dish.name} (id: {dish.id}){price_str}")
        return "\n".join(lines)
