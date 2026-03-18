from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.clients.openrouter import OpenRouterClient
from app.exceptions import OpenRouterApiError
from app.models.common import ChatMessage
from app.models.forecast import DailyForecastResult


@pytest.fixture
def client():
    return OpenRouterClient(api_key="test-key", model="test/model")


def _mock_completion(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    response = MagicMock()
    response.choices = [choice]
    return response


async def test_complete_returns_text(client):
    with patch.object(
        client._client.chat.completions, "create",
        new_callable=AsyncMock,
        return_value=_mock_completion("Hello world"),
    ):
        result = await client.complete([
            ChatMessage(role="user", content="Hi"),
        ])
    assert result == "Hello world"


async def test_complete_empty_response_raises(client):
    with patch.object(
        client._client.chat.completions, "create",
        new_callable=AsyncMock,
        return_value=_mock_completion(None),
    ):
        with pytest.raises(OpenRouterApiError, match="Empty response"):
            await client.complete([
                ChatMessage(role="user", content="Hi"),
            ])


async def test_complete_structured_parses_json(client):
    import datetime
    json_response = (
        '{"date": "2026-03-18", "forecasts": ['
        '{"dish_id": "1", "dish_name": "Борщ", '
        '"predicted_quantity": 25.0, "confidence": 0.85}]}'
    )
    with patch.object(
        client._client.chat.completions, "create",
        new_callable=AsyncMock,
        return_value=_mock_completion(json_response),
    ):
        result = await client.complete_structured(
            [ChatMessage(role="user", content="forecast")],
            DailyForecastResult,
        )
    assert result.date == datetime.date(2026, 3, 18)
    assert len(result.forecasts) == 1
    assert result.forecasts[0].dish_name == "Борщ"


async def test_complete_structured_retries_on_invalid_json(client):
    bad_json = '{"invalid": true}'
    good_json = (
        '{"date": "2026-03-18", "forecasts": ['
        '{"dish_id": "1", "dish_name": "X", '
        '"predicted_quantity": 10.0, "confidence": 0.5}]}'
    )
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_completion(bad_json)
        return _mock_completion(good_json)

    with patch.object(
        client._client.chat.completions, "create",
        side_effect=mock_create,
    ):
        result = await client.complete_structured(
            [ChatMessage(role="user", content="forecast")],
            DailyForecastResult,
        )
    assert result.date.isoformat() == "2026-03-18"
    assert call_count == 2
