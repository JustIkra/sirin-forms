from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import (
    get_forecasts_repo,
    get_iiko_client,
    get_products_repo,
    get_settings,
)
from app.api.forecast import router
from app.exceptions import ApiClientError
from app.models.inventory import InventoryItem, InventoryResponse


@pytest.fixture
def app() -> FastAPI:
    fastapi_app = FastAPI()
    fastapi_app.include_router(router)
    fastapi_app.dependency_overrides[get_iiko_client] = lambda: MagicMock()
    fastapi_app.dependency_overrides[get_forecasts_repo] = lambda: MagicMock()
    fastapi_app.dependency_overrides[get_products_repo] = lambda: MagicMock()
    fastapi_app.dependency_overrides[get_settings] = lambda: MagicMock()
    return fastapi_app


async def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_inventory_returns_response(app: FastAPI) -> None:
    mock_response = InventoryResponse(
        date="2026-03-17",
        week_start="2026-03-16",
        week_end="2026-03-22",
        items=[
            InventoryItem(
                product_id="i1",
                product_name="Мука",
                stock=5.0,
                need=10.0,
                to_buy=5.0,
                unit="кг",
            ),
        ],
    )
    service = MagicMock()
    service.get_weekly_inventory = AsyncMock(return_value=mock_response)

    with patch("app.api.forecast.InventoryService", return_value=service):
        async with await _client(app) as client:
            resp = await client.get("/api/inventory?date=2026-03-17")

    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2026-03-17"
    assert data["week_start"] == "2026-03-16"
    assert len(data["items"]) == 1
    assert data["items"][0]["product_name"] == "Мука"
    assert data["items"][0]["to_buy"] == 5.0


async def test_inventory_handles_iiko_error(app: FastAPI) -> None:
    service = MagicMock()
    service.get_weekly_inventory = AsyncMock(side_effect=ApiClientError("iiko down"))

    with patch("app.api.forecast.InventoryService", return_value=service):
        async with await _client(app) as client:
            resp = await client.get("/api/inventory?date=2026-03-17")

    assert resp.status_code == 502
    assert "iiko down" in resp.json()["detail"]


async def test_inventory_requires_date(app: FastAPI) -> None:
    async with await _client(app) as client:
        resp = await client.get("/api/inventory")

    assert resp.status_code == 422
