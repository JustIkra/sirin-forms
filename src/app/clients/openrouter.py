import json
import logging
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.exceptions import OpenRouterApiError
from app.models.common import ChatMessage
from app.models.forecast import BusinessRecommendation, DailyForecastResult

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterClient:
    """LLM client using OpenAI SDK with OpenRouter backend."""

    def __init__(self, api_key: str, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
        )

    async def close(self) -> None:
        await self._client.close()

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                raise OpenRouterApiError("Empty response from LLM")
            return content
        except OpenRouterApiError:
            raise
        except Exception as exc:
            raise OpenRouterApiError(f"LLM request failed: {exc}") from exc

    async def complete_structured(
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        max_retries: int = 2,
    ) -> T:
        schema = response_model.model_json_schema()
        system_msg = ChatMessage(
            role="system",
            content=(
                f"Respond ONLY with valid JSON matching this schema:\n"
                f"{json.dumps(schema, ensure_ascii=False)}"
            ),
        )
        all_messages = [system_msg, *messages]

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            raw = await self.complete(
                all_messages, temperature=temperature, max_tokens=max_tokens,
            )
            try:
                return response_model.model_validate_json(raw)
            except ValidationError as exc:
                last_exc = exc
                logger.warning(
                    "Structured output validation failed (attempt %d/%d): %s",
                    attempt, max_retries, exc,
                )
                all_messages.append(ChatMessage(
                    role="assistant", content=raw,
                ))
                all_messages.append(ChatMessage(
                    role="user",
                    content=f"Invalid JSON. Fix these errors: {exc.errors()}",
                ))

        raise OpenRouterApiError(
            f"Structured output failed after {max_retries} retries: {last_exc}"
        )

    async def generate_daily_forecast(
        self,
        sales_data: str,
        weather_data: str,
        calendar_info: str,
        menu_info: str,
    ) -> DailyForecastResult:
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "Ты — аналитик ресторана. На основе исторических продаж, погоды, "
                    "календарных факторов и меню сформируй прогноз продаж на день. "
                    "Отвечай строго в JSON."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    f"Исторические продажи:\n{sales_data}\n\n"
                    f"Погода:\n{weather_data}\n\n"
                    f"Календарь:\n{calendar_info}\n\n"
                    f"Меню:\n{menu_info}\n\n"
                    f"Сформируй прогноз."
                ),
            ),
        ]
        return await self.complete_structured(messages, DailyForecastResult)

    async def generate_recommendations(
        self,
        trends: str,
        plan_fact: str,
    ) -> list[BusinessRecommendation]:
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "Ты — бизнес-консультант ресторана. На основе трендов и план-факт "
                    "анализа сформируй список рекомендаций. Отвечай JSON-массивом."
                ),
            ),
            ChatMessage(
                role="user",
                content=(
                    f"Тренды:\n{trends}\n\n"
                    f"План-факт:\n{plan_fact}\n\n"
                    f"Сформируй рекомендации."
                ),
            ),
        ]
        raw = await self.complete(messages, temperature=0.5)
        import json as _json
        items = _json.loads(raw)
        return [BusinessRecommendation.model_validate(item) for item in items]
