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

        # 2. Daily breakdown for top-20 dishes (last 7 days)
        if recent:
            week_ago = target_date - datetime.timedelta(days=7)
            last_7d = [s for s in recent if s.date > week_ago]
            if last_7d:
                # Find top-20 dishes by volume in last 7 days
                dish_vol: dict[str, float] = defaultdict(float)
                for s in last_7d:
                    dish_vol[s.dish_name] += s.quantity
                top_dishes = sorted(dish_vol, key=dish_vol.get, reverse=True)[:20]

                # Collect unique dates
                dates_7d = sorted({s.date for s in last_7d})

                # Build per-dish per-date grid
                grid: dict[str, dict[datetime.date, float]] = defaultdict(lambda: defaultdict(float))
                for s in last_7d:
                    if s.dish_name in top_dishes:
                        grid[s.dish_name][s.date] += s.quantity

                lines.append("")
                lines.append("## Продажи по дням (последние 7 дней)")
                # Header
                header = f"{'Дата':<12}"
                for dish in top_dishes:
                    short = dish[:12]
                    header += f" | {short:>12}"
                lines.append(header)
                lines.append("-" * len(header))
                # Rows
                for d in dates_7d:
                    row = f"{d.isoformat():<12}"
                    for dish in top_dishes:
                        qty = grid[dish].get(d, 0)
                        row += f" | {qty:>12.0f}"
                    lines.append(row)

            lines.append("")

        # 3. Trend: average daily sales per week for last 4 weeks
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
    def build_retrospective(
        plan_fact_records: list["PlanFactRecord"],
        mape: float,
    ) -> str:
        from app.models.forecast import PlanFactRecord  # noqa: F811

        if not plan_fact_records:
            return "Ретроспектива недоступна — нет данных план-факт за прошлую неделю."

        lines = [
            f"## Ретроспектива: точность прогнозов за последние дни (MAPE {mape:.1f}%)",
            "",
            "Ниже — блюда с наибольшими отклонениями. Учти эти ошибки и скорректируй прогноз.",
            "",
            f"{'Блюдо':<35} {'Прогноз':>8} {'Факт':>8} {'Откл%':>8} {'Смещение':>10}",
            "-" * 73,
        ]

        # Sort by absolute deviation descending, take top 15
        sorted_records = sorted(
            plan_fact_records, key=lambda r: abs(r.deviation_pct), reverse=True,
        )[:15]

        for r in sorted_records:
            bias = "завышал" if r.predicted_quantity > r.actual_quantity else "занижал"
            lines.append(
                f"{r.dish_name:<35} {r.predicted_quantity:>8.0f} {r.actual_quantity:>8.0f} "
                f"{r.deviation_pct:>+7.1f}% {bias:>10}"
            )

        # Summary bias
        total_pred = sum(r.predicted_quantity for r in plan_fact_records)
        total_act = sum(r.actual_quantity for r in plan_fact_records)
        if total_act > 0:
            overall_bias = (total_pred - total_act) / total_act * 100
            direction = "завышение" if overall_bias > 0 else "занижение"
            lines.append("")
            lines.append(
                f"Общее смещение: {overall_bias:+.1f}% ({direction}). "
                f"Прогноз: {total_pred:.0f}, Факт: {total_act:.0f}."
            )

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
