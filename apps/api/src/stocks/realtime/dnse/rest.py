"""TLS-verified bounded DNSE market-data REST client."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date
from typing import Any, AsyncIterator, Mapping

import httpx

from .. import DataOutcome, DataOutcomeKind, MarketDataSource
from .auth import RestSigner
from .metrics import AdapterMetrics
from .rate_budget import EndpointFamily, RateBudget
from .validation import EventWindow, OhlcRequest, validated_board, validated_symbol


@dataclass(frozen=True, slots=True)
class RestResult:
    request_id: str
    data: Any | None = None
    outcome: DataOutcome | None = None

    def __post_init__(self) -> None:
        if (self.data is None) == (self.outcome is None):
            raise ValueError("REST result requires exactly one of data or outcome")


@dataclass(frozen=True, slots=True)
class RestPage:
    items: tuple[Mapping[str, Any], ...]
    next_page_token: str | None


class DnseRestClient:
    """Market-data-only client; account and trading paths are intentionally absent."""

    def __init__(
        self,
        signer: RestSigner,
        *,
        base_url: str = "https://openapi.dnse.com.vn",
        client: httpx.AsyncClient | None = None,
        budget: RateBudget | None = None,
        metrics: AdapterMetrics | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("DNSE REST base URL must use verified TLS")
        self._signer = signer
        self._base_url = base_url.rstrip("/")
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(
            verify=True,
            timeout=httpx.Timeout(connect=5, read=15, write=10, pool=5),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
        self._budget = budget or RateBudget()
        self.metrics = metrics or AdapterMetrics()
        self._request_sequence = 0

    async def __aenter__(self) -> "DnseRestClient":
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def instruments(self, **filters: str | int) -> RestResult:
        allowed = {"symbol", "marketId", "securityGroupId", "indexName", "limit", "page"}
        if set(filters) - allowed:
            raise ValueError("unsupported instrument filter")
        if "symbol" in filters:
            filters["symbol"] = validated_symbol(str(filters["symbol"]))
        for name in ("limit", "page"):
            if name in filters and (not isinstance(filters[name], int) or filters[name] < 1):
                raise ValueError(f"instrument {name} must be a positive integer")
        return await self._get("/market/instruments", filters, EndpointFamily.INSTRUMENTS)

    async def security_definition(self, symbol: str, board: str | None = None) -> RestResult:
        return await self._symbol_get(
            symbol, "/price/{symbol}/secdef", board, EndpointFamily.REFERENCE
        )

    async def ohlc(self, request: OhlcRequest) -> RestResult:
        query = request.query()
        return await self._get("/price/ohlc", query, EndpointFamily.OHLC)

    async def trades(self, symbol: str, window: EventWindow, board: str | None = None) -> RestResult:
        return await self._event_get(symbol, "trades", window, board)

    async def quotes(self, symbol: str, window: EventWindow, board: str | None = None) -> RestResult:
        return await self._event_get(symbol, "quotes", window, board)

    async def foreign_trading(self, symbol: str, window: EventWindow, board: str | None = None) -> RestResult:
        return await self._event_get(symbol, "foreign-trading", window, board, unpublished=True)

    async def expected_price(self, symbol: str, window: EventWindow, board: str | None = None) -> RestResult:
        return await self._event_get(symbol, "expected-price", window, board, unpublished=True)

    async def latest_trade(self, symbol: str, board: str | None = None) -> RestResult:
        return await self._symbol_get(symbol, "/price/{symbol}/trades/latest", board, EndpointFamily.EVENTS)

    async def latest_quote(self, symbol: str, board: str | None = None) -> RestResult:
        return await self._symbol_get(symbol, "/price/{symbol}/quotes/latest", board, EndpointFamily.EVENTS)

    async def close_price(self, symbol: str, board: str | None = None) -> RestResult:
        return await self._symbol_get(symbol, "/price/{symbol}/close", board, EndpointFamily.REFERENCE)

    async def trading_session(self, *, product_group: str | None = None, board: str | None = None) -> RestResult:
        query: dict[str, str] = {}
        if product_group:
            query["tscProdGrpId"] = product_group
        normalized_board = validated_board(board)
        if normalized_board:
            query["boardId"] = normalized_board
        return await self._get("/market/trading-session", query, EndpointFamily.UNPUBLISHED)

    async def working_dates(self) -> RestResult:
        return await self._get("/market/working-dates", {}, EndpointFamily.REFERENCE)

    async def pages(
        self,
        symbol: str,
        family: str,
        window: EventWindow,
        board: str | None = None,
    ) -> AsyncIterator[RestPage]:
        """Yield idempotent pages while treating continuation tokens as opaque."""
        token: str | None = None
        seen_tokens: set[str] = set()
        seen_items: set[str] = set()
        while True:
            result = await self._event_get(symbol, family, window, board, page_token=token)
            if result.outcome:
                return
            payload = result.data
            if not isinstance(payload, dict):
                raise ValueError("paginated DNSE response must be an object")
            rows = payload.get("data", payload.get("items", []))
            if not isinstance(rows, list):
                raise ValueError("paginated DNSE items must be a list")
            unique: list[Mapping[str, Any]] = []
            import json

            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("paginated DNSE item must be an object")
                identity = json.dumps(row, sort_keys=True, separators=(",", ":"))
                if identity in seen_items:
                    self.metrics.increment("duplicates")
                    continue
                seen_items.add(identity)
                unique.append(row)
            next_token = payload.get("nextPageToken")
            if next_token is not None and not isinstance(next_token, str):
                raise ValueError("DNSE nextPageToken must be opaque text")
            yield RestPage(tuple(unique), next_token)
            if not next_token:
                return
            if next_token in seen_tokens:
                self.metrics.increment("gaps")
                raise RuntimeError("DNSE pagination token replay detected")
            seen_tokens.add(next_token)
            token = next_token

    async def _event_get(
        self,
        symbol: str,
        family: str,
        window: EventWindow,
        board: str | None,
        *,
        unpublished: bool = False,
        page_token: str | None = None,
    ) -> RestResult:
        if family not in {"trades", "quotes", "foreign-trading", "expected-price"}:
            raise ValueError("unsupported DNSE event family")
        normalized_symbol = validated_symbol(symbol)
        query = window.query()
        normalized_board = validated_board(board)
        if normalized_board:
            query["boardId"] = normalized_board
        if page_token is not None:
            if not page_token or len(page_token) > 4096:
                raise ValueError("invalid opaque page token")
            query["nextPageToken"] = page_token
        endpoint = EndpointFamily.UNPUBLISHED if unpublished else EndpointFamily.EVENTS
        return await self._get(f"/price/{normalized_symbol}/{family}", query, endpoint)

    async def _symbol_get(
        self,
        symbol: str,
        path: str,
        board: str | None,
        family: EndpointFamily,
    ) -> RestResult:
        normalized_symbol = validated_symbol(symbol)
        query = {}
        normalized_board = validated_board(board)
        if normalized_board:
            query["boardId"] = normalized_board
        return await self._get(path.format(symbol=normalized_symbol), query, family)

    async def _get(
        self, path: str, query: Mapping[str, str | int], family: EndpointFamily
    ) -> RestResult:
        self._request_sequence += 1
        request_id = f"dnse-{self._request_sequence}"
        try:
            self._budget.acquire(family)
        except RuntimeError:
            self.metrics.increment("quota_refusals")
            return RestResult(
                request_id=request_id,
                outcome=DataOutcome(
                    kind=DataOutcomeKind.PROVIDER_FAILURE,
                    source=MarketDataSource.DNSE,
                    request_id=request_id,
                ),
            )
        started = time.monotonic()
        try:
            response = await self._client.get(
                f"{self._base_url}{path}",
                params=query,
                headers=self._signer.headers("GET", path),
            )
        except (httpx.TimeoutException, httpx.NetworkError):
            return self._failure(request_id)
        finally:
            self.metrics.observe_latency((time.monotonic() - started) * 1000)
            self.metrics.increment("requests")
        self._budget.update(family, response.headers)
        self.metrics.gauge("quota_remaining", self._budget.remaining(family))
        if response.status_code == 429 or response.status_code >= 500:
            return self._failure(request_id)
        if response.status_code in {400, 404, 422}:
            return RestResult(
                request_id=request_id,
                outcome=DataOutcome(
                    kind=(
                        DataOutcomeKind.UNKNOWN_SYMBOL
                        if response.status_code == 404
                        else DataOutcomeKind.INVALID_REQUEST
                    ),
                    source=MarketDataSource.DNSE,
                    request_id=request_id,
                ),
            )
        try:
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError):
            return self._failure(request_id)
        if data is None or data == [] or data == {}:
            return RestResult(
                request_id=request_id,
                outcome=DataOutcome(
                    kind=DataOutcomeKind.SILENT_EMPTY,
                    source=MarketDataSource.DNSE,
                    request_id=request_id,
                ),
            )
        return RestResult(request_id=request_id, data=data)

    @staticmethod
    def _failure(request_id: str) -> RestResult:
        return RestResult(
            request_id=request_id,
            outcome=DataOutcome(
                kind=DataOutcomeKind.PROVIDER_FAILURE,
                source=MarketDataSource.DNSE,
                request_id=request_id,
            ),
        )
