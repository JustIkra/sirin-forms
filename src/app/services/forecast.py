import asyncio
import datetime
import logging
from collections import defaultdict

from app.clients.openrouter import OpenRouterClient
from app.config import Settings
from app.exceptions import ForecastError
from app.models.forecast import DailyForecastResult
from app.models.iiko import IikoProduct
from app.models.weather import DailyWeather
from app.repositories.forecasts import ForecastsRepository
from app.repositories.sales import SalesRepository
from app.services.data_collector import DataCollector
from app.services.prompt_builder import PromptBuilder
from app.utils.calendar import get_calendar_context

logger = logging.getLogger(__name__)


class ForecastService:

    def __init__(
        self,
        data_collector: DataCollector,
        prompt_builder: PromptBuilder,
        openrouter_client: OpenRouterClient,
        forecasts_repo: ForecastsRepository,
        sales_repo: SalesRepository,
        settings: Settings,
    ) -> None:
        self._collector = data_collector
        self._prompt = prompt_builder
        self._openrouter = openrouter_client
        self._forecasts_repo = forecasts_repo
        self._sales_repo = sales_repo
        self._settings = settings

    async def generate_forecast(
        self,
        target_date: datetime.date,
        *,
        force: bool = False,
        _backfill: bool = True,
    ) -> DailyForecastResult:
        # 1. Cache check
        if not force:
            cached = await self._forecasts_repo.get_forecast(target_date)
            if cached is not None:
                logger.info("Returning cached forecast for %s", target_date)
                return cached

        # 2. Collect products (fatal if fails)
        try:
            dishes = await self._collector.collect_products()
        except Exception as exc:
            raise ForecastError(f"Failed to load products: {exc}") from exc

        # 3. Collect sales and weather sequentially (asyncpg doesn't support
        #    concurrent operations on a single session)
        historical = await self._collector.collect_historical_sales(target_date)
        recent = await self._collector.collect_recent_sales(target_date)
        weather = await self._collector.collect_weather(target_date)

        # 4. Filter dishes to only those with sales (by ID or name,
        #    because iiko may use different IDs for the same dish across departments)
        sold_ids = {s.dish_id for s in historical} | {s.dish_id for s in recent}
        sold_names = {s.dish_name.strip().lower() for s in historical} | {
            s.dish_name.strip().lower() for s in recent
        }
        active_dishes = [
            d for d in dishes
            if d.id in sold_ids or d.name.strip().lower() in sold_names
        ]

        # Only keep dishes with price and included in menu
        active_dishes = [
            d for d in active_dishes
            if d.price and d.price > 0 and d.included_in_menu
        ]

        # Exclude ingredients, modifiers, and internal items from forecast
        active_dishes = [d for d in active_dishes if not self._is_non_dish(d.name)]

        # Deduplicate by name: iiko has separate entries per department
        # for the same dish. Keep one entry per unique name (prefer ID-matched).
        seen_names: dict[str, IikoProduct] = {}
        for d in active_dishes:
            key = d.name.strip().lower()
            if key not in seen_names or d.id in sold_ids:
                seen_names[key] = d
        active_dishes = list(seen_names.values())

        # Limit to top-N most popular dishes so the LLM can predict all of them
        dish_volume: dict[str, float] = defaultdict(float)
        for s in recent:
            dish_volume[s.dish_name.strip().lower()] += s.quantity
        active_dishes.sort(
            key=lambda d: dish_volume.get(d.name.strip().lower(), 0), reverse=True,
        )
        max_dishes = 50
        active_dishes = active_dishes[:max_dishes]
        logger.info(
            "Menu filtered: %d → %d dishes (top %d by recent sales)",
            len(dishes), len(active_dishes), max_dishes,
        )

        # 5. Build prompt parts
        sales_data = self._prompt.build_sales_data(historical, recent, target_date)
        weather_data = self._prompt.build_weather_data(weather)
        calendar_info = self._prompt.build_calendar_info(target_date)
        menu_info = self._prompt.build_menu_info(active_dishes)

        logger.debug("Sales prompt (%d chars): %.500s", len(sales_data), sales_data)

        # 6. Backfill + retrospective
        retrospective = ""
        if _backfill:
            retrospective = await self._backfill_and_get_retrospective(target_date)
            if retrospective:
                logger.info("Retrospective included (%d chars)", len(retrospective))

        # 7. LLM forecast
        try:
            result = await self._openrouter.generate_daily_forecast(
                sales_data=sales_data,
                weather_data=weather_data,
                calendar_info=calendar_info,
                menu_info=menu_info,
                retrospective=retrospective,
            )
        except Exception as exc:
            raise ForecastError(f"LLM forecast failed: {exc}") from exc

        # 8. Post-processing
        result = self._post_process_forecast(result, active_dishes, weather, target_date)

        # 9. Save and return
        await self._forecasts_repo.save_forecast(result)
        logger.info("Forecast saved for %s: %d dishes", target_date, len(result.forecasts))
        return result

    async def _backfill_and_get_retrospective(self, target_date: datetime.date) -> str:
        """Backfill missing LLM forecasts for X-7..X-1, then build retrospective."""
        today = datetime.date.today()
        dates = [
            target_date - datetime.timedelta(days=i)
            for i in range(1, 8)
            if (target_date - datetime.timedelta(days=i)) <= today
        ]

        # Backfill missing forecasts (without recursion)
        for d in dates:
            existing = await self._forecasts_repo.get_forecast(d, method="llm")
            if existing is None:
                logger.info("Backfilling LLM forecast for %s", d)
                try:
                    await self.generate_forecast(d, force=False, _backfill=False)
                except Exception:
                    logger.warning("Backfill failed for %s, skipping", d, exc_info=True)

        # Collect plan-fact for all backfilled dates
        all_records = []
        for d in dates:
            forecast = await self._forecasts_repo.get_forecast(d, method="llm")
            if forecast is None:
                continue
            sales = await self._sales_repo.get_sales_by_period(d, d)
            if not sales:
                continue
            actual_sales = [
                {"date": s.date, "dish_id": s.dish_id, "dish_name": s.dish_name, "quantity": s.quantity}
                for s in sales
            ]
            records = await self._forecasts_repo.get_plan_fact(d, d, actual_sales, method="llm")
            all_records.extend(records)

        if not all_records:
            return ""

        # Calculate average MAPE
        deviations = [
            abs(r.actual_quantity - r.predicted_quantity) / max(r.actual_quantity, r.predicted_quantity)
            for r in all_records
            if r.actual_quantity > 0
        ]
        avg_mape = (sum(deviations) / len(deviations) * 100) if deviations else 0.0

        return self._prompt.build_retrospective(all_records, avg_mape)

    _NON_DISH_PREFIXES = ("+", "-", "Заказ ")
    _NON_DISH_KEYWORDS = ("комплимент", "замена чаши", "на чаше", "подарок", "персонал")

    @staticmethod
    def _is_non_dish(name: str) -> bool:
        """Return True for modifiers and internal items."""
        stripped = name.strip()
        if any(stripped.startswith(p) for p in ForecastService._NON_DISH_PREFIXES):
            return True
        if any(kw in stripped.lower() for kw in ForecastService._NON_DISH_KEYWORDS):
            return True
        return False

    _WEATHER_RU: dict[str, str] = {
        "Clear": "ясно",
        "Clouds": "облачно",
        "Rain": "дождь",
        "Drizzle": "морось",
        "Thunderstorm": "гроза",
        "Snow": "снег",
        "Mist": "дымка",
        "Fog": "туман",
        "Haze": "мгла",
        "Smoke": "смог",
        "Dust": "пыль",
        "Sand": "песчаная буря",
        "Ash": "пепел",
        "Squall": "шквал",
        "Tornado": "торнадо",
    }

    @staticmethod
    def _format_weather(weather: DailyWeather | None) -> str | None:
        if weather is None:
            return None
        raw = weather.weather_description or weather.weather_main
        desc = ForecastService._WEATHER_RU.get(raw, raw)
        parts = [
            f"{weather.temp_min:.0f}–{weather.temp_max:.0f}°C",
            desc,
        ]
        if weather.precipitation > 0:
            parts.append(f"осадки {weather.precipitation:.1f} мм")
        if weather.humidity is not None:
            parts.append(f"влажность {weather.humidity}%")
        if weather.wind_speed is not None:
            parts.append(f"ветер {weather.wind_speed:.1f} м/с")
        return ", ".join(parts)

    @staticmethod
    def _post_process_forecast(
        result: DailyForecastResult,
        active_dishes: list[IikoProduct],
        weather: DailyWeather | None,
        target_date: datetime.date,
    ) -> DailyForecastResult:
        active_ids = {d.id for d in active_dishes}
        active_names = {d.name.strip().lower() for d in active_dishes}

        # Build price lookup from catalog
        price_by_id = {d.id: d.price for d in active_dishes if d.price}
        price_by_name = {d.name.strip().lower(): d.price for d in active_dishes if d.price}

        filtered = []
        for dish in result.forecasts:
            if dish.dish_id not in active_ids and dish.dish_name.strip().lower() not in active_names:
                logger.debug("Filtering unknown dish from forecast: %s", dish.dish_name)
                continue
            dish.predicted_quantity = max(0.0, dish.predicted_quantity)
            dish.confidence = max(0.0, min(1.0, dish.confidence))
            dish.price = price_by_id.get(dish.dish_id) or price_by_name.get(dish.dish_name.strip().lower())
            filtered.append(dish)

        cal = get_calendar_context(target_date)
        weather_str = ForecastService._format_weather(weather)

        return DailyForecastResult(
            date=target_date,
            forecasts=filtered,
            weather=weather_str,
            is_holiday=cal["is_holiday"],
            notes=result.notes,
            method="llm",
        )
