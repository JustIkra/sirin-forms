import datetime
import hashlib
import json

import pytest
import respx
from httpx import Response

from app.clients.iiko import IikoClient
from app.exceptions import IikoApiError, IikoAuthError
from app.models.iiko import OlapReportType, OlapV2Request


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


PRODUCTS_JSON = [
    {
        "id": "p1",
        "name": "Борщ",
        "code": "001",
        "type": "DISH",
        "defaultSalePrice": 450,
        "defaultIncludedInMenu": True,
        "deleted": False,
    },
    {
        "id": "p2",
        "name": "Хлеб",
        "code": "BRD",
        "type": "GOODS",
        "defaultSalePrice": 50,
        "defaultIncludedInMenu": False,
        "deleted": False,
    },
]

DEPARTMENTS_XML = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<corporateItemDtoes>
  <corporateItemDto>
    <id>d1</id>
    <name>Кухня</name>
    <parentId>root</parentId>
    <type>DEPARTMENT</type>
  </corporateItemDto>
</corporateItemDtoes>"""


def _xml_response(xml: str) -> Response:
    return Response(200, text=xml, headers={"content-type": "application/xml"})


@respx.mock
async def test_auth_success(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text='"test-token-123"'),
    )
    respx.get(f"{mock_server}/resto/api/v2/entities/products/list").mock(
        return_value=_json_response([]),
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
    respx.get(f"{mock_server}/resto/api/v2/entities/products/list").mock(
        return_value=_json_response(PRODUCTS_JSON),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    products = await client.get_products()
    assert len(products) == 2
    assert products[0].name == "Борщ"
    assert products[0].product_type == "dish"
    assert products[0].code == "001"
    assert products[0].price == 450
    assert products[0].included_in_menu is True
    assert products[1].name == "Хлеб"
    assert products[1].code == "BRD"
    assert products[1].product_type == "goods"
    assert products[1].included_in_menu is False


@respx.mock
async def test_session_logout_called_on_success(client, mock_server):
    auth_route = respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/corporation/stores").mock(
        return_value=_xml_response(
            '<corporateItemDtoes></corporateItemDtoes>',
        ),
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
async def test_auth_sends_sha1_hash(client, mock_server):
    expected_hash = hashlib.sha1(b"secret").hexdigest()

    auth_route = respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/corporation/stores").mock(
        return_value=_xml_response(
            '<corporateItemDtoes></corporateItemDtoes>',
        ),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    await client.get_stores()

    assert auth_route.called
    request_url = str(auth_route.calls[0].request.url)
    assert f"pass={expected_hash}" in request_url
    assert "pass=secret" not in request_url


@respx.mock
async def test_get_departments(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/corporation/departments").mock(
        return_value=_xml_response(DEPARTMENTS_XML),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    departments = await client.get_departments()
    assert len(departments) == 1
    assert departments[0].name == "Кухня"
    assert departments[0].parent_id == "root"


@respx.mock
async def test_products_empty_response_raises_iiko_error(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/v2/entities/products/list").mock(
        return_value=Response(200, text=""),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    with pytest.raises(IikoApiError, match="empty response body"):
        await client.get_products()


@respx.mock
async def test_products_invalid_json_raises_iiko_error(client, mock_server):
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/v2/entities/products/list").mock(
        return_value=Response(200, text="not json at all {{{"),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    with pytest.raises(IikoApiError, match="invalid JSON response"):
        await client.get_products()


@respx.mock
async def test_products_excludes_deleted(client, mock_server):
    products_with_deleted = PRODUCTS_JSON + [
        {"id": "p3", "name": "Удалено", "type": "DISH", "deleted": True},
    ]
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.get(f"{mock_server}/resto/api/v2/entities/products/list").mock(
        return_value=_json_response(products_with_deleted),
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )

    products = await client.get_products()
    assert len(products) == 2
    assert all(p.name != "Удалено" for p in products)


# --- OLAP v2 tests ---

OLAP_V2_REQUEST = OlapV2Request(
    report_type=OlapReportType.SALES,
    date_from=datetime.date(2026, 3, 1),
    date_to=datetime.date(2026, 3, 15),
    group_by_row_fields=["DishName", "DishId", "OpenDate.Typed"],
    aggregate_fields=["DishAmountInt", "DishSumInt"],
)

OLAP_ROW = {"DishName": "Борщ", "DishId": "p1", "OpenDate.Typed": "2026-03-10", "DishAmountInt": 5, "DishSumInt": 1500}


def _json_response(data: object) -> Response:
    return Response(200, text=json.dumps(data), headers={"content-type": "application/json"})


def _mock_olap_v2_session(mock_server: str, olap_response: Response) -> None:
    respx.get(f"{mock_server}/resto/api/auth").mock(
        return_value=Response(200, text="tok"),
    )
    respx.post(f"{mock_server}/resto/api/v2/reports/olap").mock(
        return_value=olap_response,
    )
    respx.get(f"{mock_server}/resto/api/logout").mock(
        return_value=Response(200),
    )


@respx.mock
async def test_olap_v2_list_response(client, mock_server):
    """iiko returns a plain JSON array."""
    _mock_olap_v2_session(mock_server, _json_response([OLAP_ROW]))

    report = await client.get_olap_report_v2(OLAP_V2_REQUEST)
    assert report.report_type == OlapReportType.SALES
    assert report.date_from == datetime.date(2026, 3, 1)
    assert report.date_to == datetime.date(2026, 3, 15)
    assert len(report.data) == 1
    assert report.data[0]["DishName"] == "Борщ"


@respx.mock
async def test_olap_v2_dates_in_query_params(client, mock_server):
    """dateFrom/dateTo must be query params, not in the JSON body."""
    _mock_olap_v2_session(mock_server, _json_response([OLAP_ROW]))

    await client.get_olap_report_v2(OLAP_V2_REQUEST)

    olap_call = respx.calls[-2]  # last is logout
    url = str(olap_call.request.url)
    assert "dateFrom=2026-03-01" in url
    assert "dateTo=2026-03-15" in url

    body = json.loads(olap_call.request.content)
    assert "dateFrom" not in body
    assert "dateTo" not in body


@respx.mock
async def test_olap_v2_dict_with_data_key(client, mock_server):
    """iiko returns {"data": [...]}."""
    _mock_olap_v2_session(mock_server, _json_response({"data": [OLAP_ROW]}))

    report = await client.get_olap_report_v2(OLAP_V2_REQUEST)
    assert len(report.data) == 1
    assert report.data[0]["DishId"] == "p1"


@respx.mock
async def test_olap_v2_single_dict_response(client, mock_server):
    """iiko returns a single dict without 'data' key — wrap as [dict]."""
    _mock_olap_v2_session(mock_server, _json_response(OLAP_ROW))

    report = await client.get_olap_report_v2(OLAP_V2_REQUEST)
    assert len(report.data) == 1
    assert report.data[0]["DishName"] == "Борщ"


@respx.mock
async def test_olap_v2_empty_list(client, mock_server):
    """iiko returns an empty list."""
    _mock_olap_v2_session(mock_server, _json_response([]))

    report = await client.get_olap_report_v2(OLAP_V2_REQUEST)
    assert report.data == []
