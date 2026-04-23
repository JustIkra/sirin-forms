"""Unit tests for IikoClient.get_stop_list().

The iiko stop-list endpoint is under-documented; this client parses
defensively and returns a `set[str]` of stopped dish IDs. On any failure
(HTTP != 200, malformed body, exception) it logs a warning and returns an
empty set — downstream code treats "unknown stop-list" as "no dishes
stopped".
"""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import Response

from app.clients.iiko import IikoClient


@pytest.fixture
async def client():
    """IikoClient where auth/logout/request are patched below per-test."""
    c = IikoClient(
        server_url="https://iiko.test",
        login="admin",
        password="secret",
        max_retries=1,
    )
    await c.__aenter__()
    yield c
    await c.__aexit__(None, None, None)


def _resp(status: int, body: str = "", content_type: str = "application/json") -> Response:
    return Response(status, text=body, headers={"content-type": content_type})


class TestStopListBareList:
    async def test_bare_json_list_extracts_product_ids(self, client):
        """iiko returns a raw JSON array of stop-list entries."""
        payload = (
            '[{"productId": "dish-1", "balance": 0}, '
            '{"productId": "dish-2", "balance": 0}]'
        )
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, payload)),
            ):
            result = await client.get_stop_list()
        assert result == {"dish-1", "dish-2"}


class TestStopListDictWrapped:
    async def test_dict_with_stoplist_key(self, client):
        """iiko may wrap the array under a `stopList` key."""
        payload = '{"stopList": [{"productId": "dish-3"}, {"productId": "dish-4"}]}'
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, payload)),
            ):
            result = await client.get_stop_list()
        assert result == {"dish-3", "dish-4"}

    async def test_dict_with_items_key(self, client):
        payload = '{"items": [{"productId": "dish-5"}]}'
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, payload)),
            ):
            result = await client.get_stop_list()
        assert result == {"dish-5"}

    async def test_nested_stoplists_array(self, client):
        """iiko may return per-department wrappers: stopLists[].items[]."""
        payload = (
            '{"stopLists": ['
            '{"items": [{"productId": "dish-6"}, {"productId": "dish-7"}]},'
            '{"items": [{"productId": "dish-8"}]}'
            ']}'
        )
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, payload)),
            ):
            result = await client.get_stop_list()
        assert result == {"dish-6", "dish-7", "dish-8"}

    async def test_fallback_product_and_id_keys(self, client):
        """If productId is absent, fallback to `product` or `id`."""
        payload = (
            '[{"product": "dish-a"}, {"id": "dish-b"}, {"productId": "dish-c"}]'
        )
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, payload)),
            ):
            result = await client.get_stop_list()
        assert result == {"dish-a", "dish-b", "dish-c"}


class TestStopListErrors:
    async def test_http_500_returns_empty_set(self, client):
        """On server error: log warning, return empty set (graceful degradation)."""
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(500, "Internal Server Error")),
            ):
            result = await client.get_stop_list()
        assert result == set()

    async def test_malformed_json_returns_empty_set(self, client):
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, "not json at all {{{")),
            ):
            result = await client.get_stop_list()
        assert result == set()

    async def test_unexpected_shape_returns_empty_set(self, client):
        """Valid JSON but no extractable list → empty set, no crash."""
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(return_value=_resp(200, '{"unexpected": "shape"}')),
            ):
            result = await client.get_stop_list()
        assert result == set()

    async def test_exception_in_request_returns_empty_set(self, client):
        """Transport/runtime error → empty set, no raise."""
        with patch.object(client, "_authenticate", AsyncMock(return_value="tok")), \
             patch.object(client, "_logout", AsyncMock()), \
             patch.object(
                client, "_request",
                AsyncMock(side_effect=RuntimeError("network down")),
            ):
            result = await client.get_stop_list()
        assert result == set()
