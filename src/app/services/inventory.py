import datetime
import logging
from collections import defaultdict

from app.clients.iiko import IikoClient
from app.config import Settings
from app.models.inventory import InventoryItem, InventoryResponse
from app.repositories.forecasts import ForecastsRepository
from app.repositories.products import ProductsRepository

logger = logging.getLogger(__name__)


class InventoryService:
    """Расчёт остатков и потребности в закупке на неделю."""

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

    async def get_weekly_inventory(
        self, target_date: datetime.date
    ) -> InventoryResponse:
        # 1. Вычислить границы недели
        week_start = target_date - datetime.timedelta(days=target_date.weekday())
        week_end = week_start + datetime.timedelta(days=6)

        # 2. Забрать остатки из iiko
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

        # 3. Имена продуктов и единицы ингредиентов из БД
        product_names = await self._products_repo.get_product_names()
        (
            ingredient_names,
            ingredient_units,
        ) = await self._products_repo.get_ingredient_units()

        # 4. Загрузить прогноз недели
        forecast = await self._forecasts_repo.get_forecast(week_start, method="ml")

        # 5. Рассчитать потребность по ингредиентам
        need_map: dict[str, float] = defaultdict(float)
        if forecast:
            for dish in forecast.forecasts:
                ingredients = await self._products_repo.get_ingredients_for_dish(
                    dish.dish_id
                )
                for ing in ingredients:
                    need_map[ing.product_id] += dish.predicted_quantity * ing.amount

        # 6. Объединить все product_id
        all_ids = set(stock_map.keys()) | set(need_map.keys())

        # 7. Собрать результат
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
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            items=items,
        )
