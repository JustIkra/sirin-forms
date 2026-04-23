import datetime
import logging
from collections import defaultdict
from typing import Literal

from app.clients.iiko import IikoClient
from app.config import Settings
from app.models.inventory import InventoryItem, InventoryResponse
from app.repositories.forecasts import ForecastsRepository
from app.repositories.products import ProductsRepository

logger = logging.getLogger(__name__)


Scope = Literal["day", "week"]


class InventoryService:
    """Расчёт остатков и потребности в закупке на день или неделю."""

    def __init__(
        self,
        iiko_client: IikoClient,
        forecasts_repo: ForecastsRepository,
        products_repo: ProductsRepository,
        settings: Settings,
    ) -> None:
        self._iiko = iiko_client
        self._forecasts_repo = forecasts_repo
        self._products_repo = products_repo
        self._settings = settings

    async def get_inventory(
        self,
        target_date: datetime.date,
        scope: Scope = "week",
    ) -> InventoryResponse:
        """Возвращает остатки + потребность на период.

        scope="week": потребность по недельному прогнозу (понедельник–воскресенье).
        scope="day": потребность по дневному прогнозу (ml_daily).
        """
        # 1. Границы периода
        if scope == "week":
            period_start = target_date - datetime.timedelta(days=target_date.weekday())
            period_end = period_start + datetime.timedelta(days=6)
        else:  # day
            period_start = target_date
            period_end = target_date

        # 2. Остатки из iiko
        stock_map: dict[str, float] = defaultdict(float)
        if self._settings.iiko_department_id:
            try:
                raw_stock = await self._iiko.get_balance_stores(
                    target_date,
                    self._settings.iiko_department_id,
                )
                for item in raw_stock:
                    product_id = item.get("product") or item.get("productId") or ""
                    amount = float(item.get("amount", 0))
                    if product_id:
                        stock_map[product_id] += amount
            except Exception:
                logger.warning("Не удалось получить остатки из iiko", exc_info=True)

        # 3. Имена и единицы
        product_names = await self._products_repo.get_product_names()
        (
            ingredient_names,
            ingredient_units,
        ) = await self._products_repo.get_ingredient_units()

        # 4. Прогноз по scope
        if scope == "week":
            forecast = await self._forecasts_repo.get_forecast(period_start, method="ml")
        else:
            forecast = await self._forecasts_repo.get_forecast(target_date, method="ml_daily")
            # Fallback: если дневного прогноза нет — делим недельный на 7 как грубую оценку
            if forecast is None:
                weekly_start = target_date - datetime.timedelta(days=target_date.weekday())
                weekly = await self._forecasts_repo.get_forecast(weekly_start, method="ml")
                if weekly is not None:
                    forecast = weekly
                    # Делим предсказанное кол-во на 7, чтобы получить дневную норму
                    for dish in forecast.forecasts:
                        dish.predicted_quantity = round(dish.predicted_quantity / 7.0, 3)

        # 5. Потребность по ингредиентам (bulk-запрос)
        need_map: dict[str, float] = defaultdict(float)
        if forecast and forecast.forecasts:
            dish_ids = [d.dish_id for d in forecast.forecasts]
            ingredients_map = await self._products_repo.get_ingredients_map(dish_ids)
            for dish in forecast.forecasts:
                for ing in ingredients_map.get(dish.dish_id, []):
                    need_map[ing.product_id] += dish.predicted_quantity * ing.amount

        # 6. Объединить все product_id
        all_ids = set(stock_map.keys()) | set(need_map.keys())

        items: list[InventoryItem] = []
        for pid in all_ids:
            name = product_names.get(pid) or ingredient_names.get(pid)
            if not name:
                continue
            stock = stock_map.get(pid, 0.0)
            need = need_map.get(pid, 0.0)
            unit = ingredient_units.get(pid)
            items.append(
                InventoryItem(
                    product_id=pid,
                    product_name=name,
                    stock=round(stock, 3),
                    need=round(need, 3),
                    to_buy=round(max(0, need - stock), 3),
                    unit=unit,
                )
            )

        items.sort(key=lambda x: x.product_name)

        return InventoryResponse(
            date=target_date.isoformat(),
            scope=scope,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            week_start=period_start.isoformat(),
            week_end=period_end.isoformat(),
            items=items,
        )

    # Сохраняем старую сигнатуру для совместимости с тестами
    async def get_weekly_inventory(
        self, target_date: datetime.date,
    ) -> InventoryResponse:
        return await self.get_inventory(target_date, scope="week")
