import asyncio
import logging

import httpx

from app.exceptions import ApiClientError

logger = logging.getLogger(__name__)


class BaseHttpClient:
    """Async HTTP client wrapper with retry and timeout."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._headers = headers or {}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseHttpClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            headers=self._headers,
        )
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self.client.request(
                    method,
                    path,
                    params=params,
                    json=json_body,
                    headers=headers,
                )
                if response.status_code >= 500 and attempt < self._max_retries:
                    logger.warning(
                        "Server error %s on %s %s (attempt %d/%d)",
                        response.status_code, method, path, attempt, self._max_retries,
                    )
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue
                return response
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    logger.warning(
                        "Transport error on %s %s%s (attempt %d/%d): %s",
                        method, self._base_url, path, attempt, self._max_retries, exc,
                    )
                    await asyncio.sleep(2 ** (attempt - 1))
                    continue

        raise ApiClientError(f"Request failed after {self._max_retries} retries: {last_exc}")
