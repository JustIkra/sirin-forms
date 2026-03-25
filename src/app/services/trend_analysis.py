import datetime
import logging
from collections import defaultdict

import numpy as np

from app.models.forecast import DishTrend
from app.models.iiko import SaleRecord
from app.repositories.sales import SalesRepository

logger = logging.getLogger(__name__)


class TrendAnalyzer:

    def __init__(self, sales_repo: SalesRepository) -> None:
        self._sales_repo = sales_repo

    async def get_dish_trends(
        self,
        weeks: int = 12,
        top_n: int = 20,
    ) -> list[DishTrend]:
        today = datetime.date.today()
        date_from = today - datetime.timedelta(weeks=weeks)
        date_to = today - datetime.timedelta(days=1)

        sales = await self._sales_repo.get_sales_by_period(date_from, date_to)
        if not sales:
            return []

        # Aggregate by (dish_name, week_number) -> total qty
        dish_weekly: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for s in sales:
            week_idx = (s.date - date_from).days // 7
            dish_weekly[s.dish_name][week_idx] += s.quantity

        # Compute trends
        trends: list[DishTrend] = []
        half = weeks // 2

        for dish_name, weekly in dish_weekly.items():
            week_data = [weekly.get(i, 0.0) for i in range(weeks)]
            first_half = week_data[:half]
            second_half = week_data[half:]

            prev_avg = sum(first_half) / len(first_half) if first_half else 0
            curr_avg = sum(second_half) / len(second_half) if second_half else 0

            if prev_avg > 0:
                change_pct = ((curr_avg - prev_avg) / prev_avg) * 100
            elif curr_avg > 0:
                change_pct = 100.0
            else:
                continue  # skip dishes with no sales

            if change_pct > 10:
                direction = "growing"
            elif change_pct < -10:
                direction = "declining"
            else:
                direction = "stable"

            # Seasonality: compare current month vs same month last year
            seasonality = await self._seasonality_factor(dish_name, today)

            trends.append(DishTrend(
                dish_name=dish_name,
                current_weekly_avg=round(curr_avg, 1),
                prev_weekly_avg=round(prev_avg, 1),
                change_pct=round(change_pct, 1),
                trend_direction=direction,
                seasonality_factor=seasonality,
                weekly_data=[round(v, 1) for v in week_data],
            ))

        # Sort: growing first (by change_pct desc), then declining (by change_pct asc)
        growing = sorted(
            [t for t in trends if t.trend_direction == "growing"],
            key=lambda t: t.change_pct, reverse=True,
        )[:top_n]
        declining = sorted(
            [t for t in trends if t.trend_direction == "declining"],
            key=lambda t: t.change_pct,
        )[:top_n]

        return growing + declining

    async def _seasonality_factor(
        self, dish_name: str, today: datetime.date,
    ) -> float | None:
        """Compare current month sales vs same month last year."""
        this_month_start = today.replace(day=1)
        this_month_end = today - datetime.timedelta(days=1)
        try:
            last_year_start = this_month_start.replace(year=today.year - 1)
            last_year_end = last_year_start.replace(
                day=min(today.day - 1, 28),
            )
        except ValueError:
            return None

        current = await self._sales_repo.get_sales_by_dish_name(
            dish_name, this_month_start, this_month_end,
        )
        previous = await self._sales_repo.get_sales_by_dish_name(
            dish_name, last_year_start, last_year_end,
        )

        curr_total = sum(s.quantity for s in current)
        prev_total = sum(s.quantity for s in previous)

        if prev_total > 0:
            return round(curr_total / prev_total, 2)
        return None
