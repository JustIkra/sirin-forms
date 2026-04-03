import asyncio
import datetime
import hashlib
import logging
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from app.clients.base import BaseHttpClient
from app.exceptions import IikoApiError, IikoAuthError
from app.models.iiko import (
    IikoDepartment,
    IikoOlapReport,
    IikoProduct,
    IikoStore,
    IikoSupplier,
    OlapReportType,
    OlapV2Request,
    SaleRecord,
)

logger = logging.getLogger(__name__)


class IikoClient(BaseHttpClient):
    """Client for iiko Server API.

    IMPORTANT: iiko has a limit on concurrent sessions.
    Sessions are short-lived: authenticate -> request -> logout immediately.
    """

    def __init__(
        self,
        server_url: str,
        login: str,
        password: str,
        **kwargs: object,
    ) -> None:
        super().__init__(
            base_url=f"{server_url.rstrip('/')}/resto/api",
            headers={"Accept": "application/json, */*;q=0.9"},
            **kwargs,
        )
        self._login = login
        self._password_hash = hashlib.sha1(password.encode("utf-8")).hexdigest()
        self._semaphore = asyncio.Semaphore(1)

    async def _authenticate(self) -> str:
        response = await self._request(
            "GET", "/auth",
            params={"login": self._login, "pass": self._password_hash},
        )
        if response.status_code != 200:
            raise IikoAuthError(
                f"Authentication failed: {response.text}",
                status_code=response.status_code,
            )
        token = response.text.strip().strip('"')
        if not token:
            raise IikoAuthError("Empty token received")
        return token

    async def _logout(self, token: str) -> None:
        try:
            await self._request("GET", "/logout", params={"key": token})
        except Exception:
            logger.warning("Failed to logout iiko session", exc_info=True)

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[str]:
        """Short-lived session: auth -> yield token -> immediate logout."""
        async with self._semaphore:
            token = await self._authenticate()
            try:
                yield token
            finally:
                await self._logout(token)

    def _check_response(self, response: object, context: str) -> None:
        from httpx import Response
        resp: Response = response  # type: ignore[assignment]
        if resp.status_code != 200:
            raise IikoApiError(
                f"{context}: {resp.status_code} {resp.text}",
                status_code=resp.status_code,
            )

    def _parse_json(self, response: object, context: str) -> Any:
        """Parse JSON from response, raising IikoApiError with diagnostic info on failure."""
        from httpx import Response
        resp: Response = response  # type: ignore[assignment]
        self._check_response(resp, context)
        body = resp.text
        if not body or not body.strip():
            raise IikoApiError(
                f"{context}: empty response body (Content-Type: {resp.headers.get('content-type', 'unknown')})",
                status_code=resp.status_code,
            )
        try:
            return resp.json()
        except Exception as exc:
            preview = body[:500]
            logger.error("%s: failed to parse JSON. Body preview: %s", context, preview)
            raise IikoApiError(
                f"{context}: invalid JSON response (Content-Type: {resp.headers.get('content-type', 'unknown')})",
                status_code=resp.status_code,
            ) from exc

    def _parse_xml_list(self, response: object, context: str) -> list[dict[str, str]]:
        """Parse XML list response from iiko Server API.

        iiko Server GET endpoints return empty {} in JSON due to broken
        serialization. XML works correctly.
        """
        from httpx import Response
        resp: Response = response  # type: ignore[assignment]
        self._check_response(resp, context)
        body = resp.text
        if not body or not body.strip():
            raise IikoApiError(
                f"{context}: empty response body",
                status_code=resp.status_code,
            )
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            preview = body[:500]
            logger.error("%s: failed to parse XML. Body preview: %s", context, preview)
            raise IikoApiError(
                f"{context}: invalid XML response",
                status_code=resp.status_code,
            ) from exc
        items: list[dict[str, str]] = []
        for element in root:
            item: dict[str, str] = {}
            for child in element:
                if child.text:
                    item[child.tag] = child.text
            items.append(item)
        return items

    # --- Products ---

    async def get_products(self, *, include_deleted: bool = False) -> list[IikoProduct]:
        async with self._session() as token:
            params: dict = {"key": token}
            if include_deleted:
                params["includeDeleted"] = "true"
            response = await self._request(
                "GET", "/v2/entities/products/list", params=params,
            )
            items = self._parse_json(response, "get_products")
            return [
                IikoProduct(
                    id=item["id"],
                    name=item.get("name", ""),
                    code=item.get("code"),
                    product_type=item.get("type", "DISH").lower(),
                    price=item.get("defaultSalePrice"),
                    included_in_menu=item.get("defaultIncludedInMenu", False),
                )
                for item in items
                if "id" in item and not item.get("deleted", False)
            ]

    async def search_products(
        self,
        *,
        name: str | None = None,
        code: str | None = None,
        product_type: str | None = None,
    ) -> list[IikoProduct]:
        async with self._session() as token:
            params: dict = {"key": token}
            if name:
                params["name"] = name
            if code:
                params["code"] = code
            if product_type:
                params["productType"] = product_type
            response = await self._request(
                "GET", "/products/search", params=params,
                headers={"Accept": "application/xml"},
            )
            items = self._parse_xml_list(response, "search_products")
            return [
                IikoProduct(
                    id=item["id"],
                    name=item.get("name", ""),
                    code=item.get("code"),
                    product_type=item.get("productType", "DISH").lower(),
                )
                for item in items
                if "id" in item
            ]

    # --- Corporation ---

    async def get_stores(self) -> list[IikoStore]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/corporation/stores", params={"key": token},
                headers={"Accept": "application/xml"},
            )
            items = self._parse_xml_list(response, "get_stores")
            return [
                IikoStore(
                    id=item["id"],
                    name=item.get("name", ""),
                    type=item.get("type"),
                )
                for item in items
                if "id" in item
            ]

    async def get_departments(self) -> list[IikoDepartment]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/corporation/departments", params={"key": token},
                headers={"Accept": "application/xml"},
            )
            items = self._parse_xml_list(response, "get_departments")
            return [
                IikoDepartment(
                    id=item["id"],
                    name=item.get("name", ""),
                    parent_id=item.get("parentId"),
                )
                for item in items
                if "id" in item
            ]

    async def get_suppliers(self) -> list[IikoSupplier]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/suppliers", params={"key": token},
                headers={"Accept": "application/xml"},
            )
            items = self._parse_xml_list(response, "get_suppliers")
            return [
                IikoSupplier(
                    id=item["id"],
                    name=item.get("name", ""),
                    code=item.get("code"),
                )
                for item in items
                if "id" in item
            ]

    # --- Reports ---

    async def get_sales_report(
        self,
        department: str,
        date_from: str,
        date_to: str,
    ) -> list[SaleRecord]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/reports/sales",
                params={
                    "key": token,
                    "department": department,
                    "dateFrom": date_from,
                    "dateTo": date_to,
                },
            )
            return [SaleRecord.model_validate(r) for r in self._parse_json(response, "get_sales_report")]

    async def get_olap_report(
        self,
        report_type: str,
        date_from: str,
        date_to: str,
        *,
        group_row: str | None = None,
        group_col: str | None = None,
        aggregate: str | None = None,
    ) -> IikoOlapReport:
        async with self._session() as token:
            params: dict = {
                "key": token,
                "reportType": report_type,
                "dateFrom": date_from,
                "dateTo": date_to,
            }
            if group_row:
                params["groupRow"] = group_row
            if group_col:
                params["groupCol"] = group_col
            if aggregate:
                params["agr"] = aggregate
            response = await self._request("GET", "/reports/olap", params=params)
            raw = self._parse_json(response, "get_olap_report")
            data = self._extract_olap_data(raw)
            return IikoOlapReport(
                report_type=OlapReportType(report_type),
                date_from=datetime.date.fromisoformat(date_from),
                date_to=datetime.date.fromisoformat(date_to),
                data=data,
            )

    @staticmethod
    def _extract_olap_data(raw: Any) -> list[dict]:
        """Extract data array from various iiko OLAP response formats."""
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            if "data" in raw:
                return raw["data"]
            return [raw]
        return []

    async def get_olap_report_v2(self, request: OlapV2Request) -> IikoOlapReport:
        async with self._session() as token:
            body = {
                "reportType": request.report_type,
                "groupByRowFields": request.group_by_row_fields,
                "groupByColFields": request.group_by_col_fields,
                "aggregateFields": request.aggregate_fields,
                "filters": request.filters,
            }
            response = await self._request(
                "POST", "/v2/reports/olap",
                params={
                    "key": token,
                    "dateFrom": request.date_from.isoformat(),
                    "dateTo": request.date_to.isoformat(),
                },
                json_body=body,
            )
            raw = self._parse_json(response, "get_olap_report_v2")
            data = self._extract_olap_data(raw)
            return IikoOlapReport(
                report_type=request.report_type,
                date_from=request.date_from,
                date_to=request.date_to,
                data=data,
            )

    async def get_product_expense(
        self,
        department: str,
        date_from: datetime.date,
        date_to: datetime.date,
    ) -> list[dict]:
        """Get ingredient consumption report. Returns list of {date, productName, productId, value}."""
        async with self._session() as token:
            response = await self._request(
                "GET", "/reports/productExpense",
                params={
                    "key": token,
                    "department": department,
                    "dateFrom": date_from.strftime("%d.%m.%Y"),
                    "dateTo": date_to.strftime("%d.%m.%Y"),
                },
                headers={"Accept": "application/xml"},
            )
            return self._parse_xml_list(response, "get_product_expense")

    async def get_store_operations(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
    ) -> list[dict]:
        """Get warehouse operations (invoices, write-offs, transfers)."""
        async with self._session() as token:
            response = await self._request(
                "GET", "/reports/storeOperations",
                params={
                    "key": token,
                    "dateFrom": date_from.strftime("%d.%m.%Y"),
                    "dateTo": date_to.strftime("%d.%m.%Y"),
                    "productDetalization": "true",
                },
                headers={"Accept": "application/xml"},
            )
            return self._parse_xml_list(response, "get_store_operations")

    async def get_ingredient_entry(
        self,
        department: str,
        article: str,
    ) -> list[dict]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/reports/ingredientEntry",
                params={
                    "key": token,
                    "department": department,
                    "article": article,
                },
            )
            return self._parse_json(response, "get_ingredient_entry")
