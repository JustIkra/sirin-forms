import datetime
import logging
from collections import defaultdict

from app.clients.iiko import IikoClient
from app.config import Settings
from app.models.forecast import IngredientNeed, ProcurementList
from app.repositories.forecasts import ForecastsRepository
from app.repositories.sales import SalesRepository
from app.utils.dt import MSK

logger = logging.getLogger(__name__)


class ProcurementService:

    def __init__(
        self,
        iiko_client: IikoClient,
        forecasts_repo: ForecastsRepository,
        sales_repo: SalesRepository,
        settings: Settings,
    ) -> None:
        self._iiko = iiko_client
        self._forecasts_repo = forecasts_repo
        self._sales_repo = sales_repo
        self._buffer_pct = settings.procurement_buffer_pct

    async def generate_list(
        self,
        target_date: datetime.date,
        method: str = "ml",
    ) -> ProcurementList:
        # 1. Get forecast for target date
        forecast = await self._forecasts_repo.get_forecast(target_date, method=method)
        if not forecast:
            raise ValueError(f"No {method} forecast found for {target_date}. Generate forecast first.")

        forecast_total = sum(d.predicted_quantity for d in forecast.forecasts)

        # 2. Get actual average daily sales for last 7 days
        week_ago = target_date - datetime.timedelta(days=7)
        yesterday = target_date - datetime.timedelta(days=1)
        recent_sales = await self._sales_repo.get_daily_totals(week_ago, yesterday)
        if recent_sales:
            avg_daily_sales = sum(d.total_quantity for d in recent_sales) / len(recent_sales)
        else:
            avg_daily_sales = forecast_total  # fallback

        # 3. Scale factor: how much more/less than average do we expect
        scale = forecast_total / avg_daily_sales if avg_daily_sales > 0 else 1.0

        # 4. Get ingredient consumption for last 7 days from iiko
        departments = await self._iiko.get_departments()
        dept_id = departments[0].id if departments else None
        if not dept_id:
            raise ValueError("No departments found in iiko")

        expense_data = await self._iiko.get_product_expense(dept_id, week_ago, yesterday)

        # Aggregate: avg daily consumption per ingredient
        ingredient_daily: dict[str, dict] = defaultdict(lambda: {"total": 0.0, "days": 0, "id": ""})
        for row in expense_data:
            name = row.get("productName", "")
            pid = row.get("productId", "")
            value = abs(float(row.get("value", 0)))
            if name and value > 0:
                ingredient_daily[name]["total"] += value
                ingredient_daily[name]["id"] = pid
                ingredient_daily[name]["days"] += 1

        days_count = len(recent_sales) or 7

        # 5. Calculate stock on hand from store operations (incoming - outgoing)
        stock = await self._get_stock_on_hand(yesterday)

        # 6. Build procurement list
        items: list[IngredientNeed] = []
        for name, data in sorted(ingredient_daily.items()):
            avg_daily = data["total"] / days_count
            required = avg_daily * scale
            buffered = required * (1 + self._buffer_pct)
            on_hand = stock.get(data["id"], 0.0)
            to_purchase = max(0.0, buffered - on_hand)

            items.append(IngredientNeed(
                ingredient_id=data["id"],
                ingredient_name=name,
                unit="кг",
                required_amount=round(required, 3),
                buffered_amount=round(to_purchase, 3),
            ))

        return ProcurementList(
            date_from=target_date,
            date_to=target_date,
            items=items,
            generated_at=datetime.datetime.now(tz=MSK),
        )

    async def _get_stock_on_hand(
        self,
        as_of_date: datetime.date,
    ) -> dict[str, float]:
        """Estimate stock by summing incoming - outgoing from storeOperations (last 30 days)."""
        date_from = as_of_date - datetime.timedelta(days=30)
        try:
            operations = await self._iiko.get_store_operations(date_from, as_of_date)
        except Exception:
            logger.warning("storeOperations unavailable, skipping stock", exc_info=True)
            return {}

        stock: dict[str, float] = defaultdict(float)
        for op in operations:
            pid = op.get("product", "")
            amount = float(op.get("amount", 0))
            if pid and amount != 0:
                stock[pid] += amount  # positive = incoming, negative = outgoing

        # Only return positive balances
        return {pid: max(0.0, qty) for pid, qty in stock.items()}
