import asyncio
import datetime
import logging
import re
from collections import defaultdict

from app.clients.openrouter import OpenRouterClient
from app.config import Settings
from app.exceptions import ForecastError
from app.models.forecast import DailyForecastResult
from app.models.iiko import IikoProduct
from app.models.weather import DailyWeather
from app.repositories.forecasts import ForecastsRepository
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
        settings: Settings,
    ) -> None:
        self._collector = data_collector
        self._prompt = prompt_builder
        self._openrouter = openrouter_client
        self._forecasts_repo = forecasts_repo
        self._settings = settings

    async def generate_forecast(
        self,
        target_date: datetime.date,
        *,
        force: bool = False,
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

        # 6. LLM forecast
        try:
            result = await self._openrouter.generate_daily_forecast(
                sales_data=sales_data,
                weather_data=weather_data,
                calendar_info=calendar_info,
                menu_info=menu_info,
            )
        except Exception as exc:
            raise ForecastError(f"LLM forecast failed: {exc}") from exc

        # 7. Post-processing
        result = self._post_process_forecast(result, active_dishes, weather, target_date)

        # 8. Save and return
        await self._forecasts_repo.save_forecast(result)
        logger.info("Forecast saved for %s: %d dishes", target_date, len(result.forecasts))
        return result

    # Pattern to detect ingredients/addons: name ending with "NN гр", "NN мл", etc.
    _INGREDIENT_RE = re.compile(r"\d+\s*(?:гр\.?|мл\.?|мг)\s*$", re.IGNORECASE)
    _NON_DISH_PREFIXES = ("+", "-", "Заказ ")
    _NON_DISH_KEYWORDS = ("комплимент", "замена чаши", "на чаше", "подарок")

    @staticmethod
    def _is_non_dish(name: str) -> bool:
        """Return True for ingredients, modifiers, and internal items."""
        stripped = name.strip()
        if any(stripped.startswith(p) for p in ForecastService._NON_DISH_PREFIXES):
            return True
        if any(kw in stripped.lower() for kw in ForecastService._NON_DISH_KEYWORDS):
            return True
        if ForecastService._INGREDIENT_RE.search(stripped):
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

        filtered = []
        for dish in result.forecasts:
            if dish.dish_id not in active_ids and dish.dish_name.strip().lower() not in active_names:
                logger.debug("Filtering unknown dish from forecast: %s", dish.dish_name)
                continue
            dish.predicted_quantity = max(0.0, dish.predicted_quantity)
            dish.confidence = max(0.0, min(1.0, dish.confidence))
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
