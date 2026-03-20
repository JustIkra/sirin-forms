import asyncio
import datetime
import logging

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

        # 3. Gather sales and weather in parallel
        historical_task = asyncio.create_task(
            self._collector.collect_historical_sales(target_date),
        )
        recent_task = asyncio.create_task(
            self._collector.collect_recent_sales(target_date),
        )
        weather_task = asyncio.create_task(
            self._collector.collect_weather(target_date),
        )

        historical, recent, weather = await asyncio.gather(
            historical_task, recent_task, weather_task,
        )

        # 4. Filter dishes to only those with sales
        sold_ids = {s.dish_id for s in historical} | {s.dish_id for s in recent}
        active_dishes = [d for d in dishes if d.id in sold_ids]
        logger.info("Menu filtered: %d → %d dishes with sales", len(dishes), len(active_dishes))

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

        filtered = []
        for dish in result.forecasts:
            if dish.dish_id not in active_ids:
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
        )
