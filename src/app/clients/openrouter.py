import logging
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config.prompt_loader import load_prompt
from app.exceptions import OpenRouterApiError
from app.models.common import ChatMessage
from app.models.forecast import DiscrepancyAnalysisResponse

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
        response_format: dict | None = None,
    ) -> str:
        try:
            kwargs: dict = {
                "model": self._model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format
            response = await self._client.chat.completions.create(**kwargs)
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
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": schema,
            },
        }

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            raw = await self.complete(
                messages, temperature=temperature, max_tokens=max_tokens,
                response_format=response_format,
            )
            raw = self._strip_markdown_fences(raw)
            try:
                return response_model.model_validate_json(raw)
            except ValidationError as exc:
                last_exc = exc
                logger.warning(
                    "Structured output validation failed (attempt %d/%d): %s",
                    attempt, max_retries, exc,
                )

        raise OpenRouterApiError(
            f"Structured output failed after {max_retries} retries: {last_exc}"
        )

    @staticmethod
    def _strip_markdown_fences(text: str) -> str:
        """Remove ```json ... ``` wrappers that LLMs often add."""
        stripped = text.strip()
        if stripped.startswith("```"):
            # Remove opening fence (```json or ```)
            first_newline = stripped.index("\n")
            stripped = stripped[first_newline + 1:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
        return stripped.strip()

    async def generate_discrepancy_analysis(
        self,
        plan_fact_details: str,
        mape: float,
        accuracy: float,
        quality_rating: str,
        total_predicted: float,
        total_actual: float,
        forecast_key_factors: str,
        forecast_notes: str,
        sales_data: str,
        weather_data: str,
        calendar_info: str,
    ) -> DiscrepancyAnalysisResponse:
        cfg = load_prompt("discrepancy_analysis")
        messages = [
            ChatMessage(role="system", content=cfg.system_prompt),
            ChatMessage(
                role="user",
                content=cfg.user_template.format(
                    plan_fact_details=plan_fact_details,
                    mape=mape,
                    accuracy=accuracy,
                    quality_rating=quality_rating,
                    total_predicted=total_predicted,
                    total_actual=total_actual,
                    forecast_key_factors=forecast_key_factors,
                    forecast_notes=forecast_notes,
                    sales_data=sales_data,
                    weather_data=weather_data,
                    calendar_info=calendar_info,
                ),
            ),
        ]
        return await self.complete_structured(
            messages, DiscrepancyAnalysisResponse,
            temperature=cfg.temperature, max_tokens=cfg.max_tokens,
        )
