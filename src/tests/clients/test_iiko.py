import pytest
import respx
from httpx import Response

from app.clients.iiko import IikoClient
from app.exceptions import IikoApiError, IikoAuthError


@pytest.fixture
def mock_server():
    return "https://iiko.test"


@pytest.fixture
async def client(mock_server):
    c = IikoClient(
        server_url=mock_server,
        login="admin",
        password="secret",
        max_retries=1,
    )
    await c.__aenter__()
    yield c
    await c.__aexit__(None, None, None)


@respx.mock
async def test_auth_success(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text='"test-token-123"'),
    )
    respx.get(f"{mock_server}/resto/api/products").mock(
        return_value=Response(200, json=[]),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    products = await client.get_products()
    assert products == []


@respx.mock
async def test_auth_failure(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(401, text="Invalid credentials"),
    )

    with pytest.raises(IikoAuthError, match="Authentication failed"):
        await client.get_products()


@respx.mock
async def test_get_products_parses_response(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="token-1"),
    )
    respx.get(f"{mock_server}/resto/api/products").mock(
        return_value=Response(200, json=[
            {"id": "p1", "name": "Борщ", "product_type": "dish", "price": 350},
            {"id": "p2", "name": "Хлеб", "code": "BRD", "product_type": "good"},
        ]),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    products = await client.get_products()
    assert len(products) == 2
    assert products[0].name == "Борщ"
    assert products[0].product_type == "dish"
    assert products[1].code == "BRD"


@respx.mock
async def test_session_logout_called_on_success(client, mock_server):
    auth_route = respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/corporation/stores").mock(
        return_value=Response(200, json=[]),
    )
    logout_route = respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    await client.get_stores()
    assert auth_route.called
    assert logout_route.called


@respx.mock
async def test_session_logout_called_on_error(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/corporation/stores").mock(
        return_value=Response(500, text="Internal Server Error"),
    )
    logout_route = respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    with pytest.raises(IikoApiError):
        await client.get_stores()
    assert logout_route.called


@respx.mock
async def test_get_departments(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/corporation/departments").mock(
        return_value=Response(200, json=[
            {"id": "d1", "name": "Кухня"},
        ]),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    departments = await client.get_departments()
    assert len(departments) == 1
    assert departments[0].name == "Кухня"
