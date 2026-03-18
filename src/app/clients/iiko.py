import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.clients.base import BaseHttpClient
from app.exceptions import IikoApiError, IikoAuthError
from app.models.iiko import (
    IikoDepartment,
    IikoOlapReport,
    IikoProduct,
    IikoStore,
    IikoSupplier,
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
        super().__init__(base_url=f"{server_url.rstrip('/')}/resto/api", **kwargs)
        self._login = login
        self._password = password
        self._semaphore = asyncio.Semaphore(1)

    async def _authenticate(self) -> str:
        response = await self._request(
            "GET", "/auth",
            params={"login": self._login, "pass": self._password},
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

    # --- Products ---

    async def get_products(self, *, include_deleted: bool = False) -> list[IikoProduct]:
        async with self._session() as token:
            params: dict = {"key": token}
            if include_deleted:
                params["includeDeleted"] = "true"
            response = await self._request("GET", "/products", params=params)
            self._check_response(response, "get_products")
            return [IikoProduct.model_validate(p) for p in response.json()]

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
            response = await self._request("GET", "/products/search", params=params)
            self._check_response(response, "search_products")
            return [IikoProduct.model_validate(p) for p in response.json()]

    # --- Corporation ---

    async def get_stores(self) -> list[IikoStore]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/corporation/stores", params={"key": token},
            )
            self._check_response(response, "get_stores")
            return [IikoStore.model_validate(s) for s in response.json()]

    async def get_departments(self) -> list[IikoDepartment]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/corporation/departments", params={"key": token},
            )
            self._check_response(response, "get_departments")
            return [IikoDepartment.model_validate(d) for d in response.json()]

    async def get_suppliers(self) -> list[IikoSupplier]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/suppliers", params={"key": token},
            )
            self._check_response(response, "get_suppliers")
            return [IikoSupplier.model_validate(s) for s in response.json()]

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
            self._check_response(response, "get_sales_report")
            return [SaleRecord.model_validate(r) for r in response.json()]

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
            self._check_response(response, "get_olap_report")
            return IikoOlapReport.model_validate(response.json())

    async def get_olap_report_v2(self, request: OlapV2Request) -> IikoOlapReport:
        async with self._session() as token:
            body = {
                "reportType": request.report_type,
                "dateFrom": request.date_from.isoformat(),
                "dateTo": request.date_to.isoformat(),
                "groupByRowFields": request.group_by_row_fields,
                "groupByColFields": request.group_by_col_fields,
                "aggregateFields": request.aggregate_fields,
                "filters": request.filters,
            }
            response = await self._request(
                "POST", "/v2/reports/olap",
                params={"key": token},
                json_body=body,
            )
            self._check_response(response, "get_olap_report_v2")
            return IikoOlapReport.model_validate(response.json())

    async def get_product_expense(
        self,
        department: str,
        date_from: str,
        date_to: str,
    ) -> list[dict]:
        async with self._session() as token:
            response = await self._request(
                "GET", "/reports/productExpense",
                params={
                    "key": token,
                    "department": department,
                    "dateFrom": date_from,
                    "dateTo": date_to,
                },
            )
            self._check_response(response, "get_product_expense")
            return response.json()

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
            self._check_response(response, "get_ingredient_entry")
            return response.json()
