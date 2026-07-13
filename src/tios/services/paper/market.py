"""Minimal public-only Binance market-data client for the synthetic paper lane."""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from tios.trading_domain import Timeframe

PUBLIC_DATA_HOST = "https://data-api.binance.vision"
ALLOWED_SYMBOLS = frozenset({"BTCUSDT", "ETHUSDT"})
_ALLOWED_PATHS = frozenset({"/api/v3/klines", "/api/v3/ticker/bookTicker"})
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class BinanceDataError(ValueError):
    """Public market data was unavailable or malformed."""


@dataclass(frozen=True, slots=True)
class BinanceKline:
    symbol: str
    interval: Timeframe
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def is_closed(self, as_of: datetime) -> bool:
        return self.close_time <= as_of


@dataclass(frozen=True, slots=True)
class BinanceBookTicker:
    symbol: str
    bid_price: Decimal
    bid_quantity: Decimal
    ask_price: Decimal
    ask_quantity: Decimal
    observed_at: datetime

    @property
    def midpoint(self) -> Decimal:
        return (self.bid_price + self.ask_price) / 2

    @property
    def spread_bps(self) -> Decimal:
        return (self.ask_price - self.bid_price) / self.midpoint * Decimal("10000")


Transport = Callable[[urllib.request.Request, float], bytes]


def _transport(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return cast(bytes, response.read(MAX_RESPONSE_BYTES + 1))


def _decimal(value: object, name: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, float):
        raise BinanceDataError(f"{name} must be an exact decimal string")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise BinanceDataError(f"{name} is not a decimal") from error
    if not parsed.is_finite() or parsed < 0 or (not allow_zero and parsed == 0):
        raise BinanceDataError(f"{name} must be finite and positive")
    return parsed


def _timestamp_ms(value: object, name: str) -> datetime:
    try:
        milliseconds = int(str(value))
    except (TypeError, ValueError) as error:
        raise BinanceDataError(f"{name} must be epoch milliseconds") from error
    if milliseconds < 0:
        raise BinanceDataError(f"{name} must be epoch milliseconds")
    try:
        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError) as error:
        raise BinanceDataError(f"{name} must be epoch milliseconds") from error


class BinancePublicClient:
    """GET two public data endpoints; there is deliberately no generic request method."""

    def __init__(
        self,
        *,
        transport: Transport = _transport,
        timeout_seconds: float = 10,
        max_attempts: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int | float)
            or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= 30
            or not isinstance(max_attempts, int)
            or isinstance(max_attempts, bool)
            or not 1 <= max_attempts <= 5
        ):
            raise BinanceDataError("timeout and retry attempts must be positive and bounded")
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._sleep = sleep
        self._clock = clock

    def fetch_klines(
        self,
        symbol: str,
        interval: Timeframe,
        *,
        limit: int = 200,
    ) -> tuple[BinanceKline, ...]:
        _symbol(symbol)
        if not isinstance(interval, Timeframe):
            raise BinanceDataError("interval must be a canonical Timeframe")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
            raise BinanceDataError("kline limit must be between 1 and 1000")
        payload = self._get_json(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval.value, "limit": str(limit)},
        )
        if not isinstance(payload, list):
            raise BinanceDataError("klines response must be a list")
        if len(payload) > limit:
            raise BinanceDataError("klines response exceeds the requested limit")
        rows: list[BinanceKline] = []
        for raw in payload:
            if not isinstance(raw, list) or len(raw) != 12:
                raise BinanceDataError("kline row is malformed")
            opening = _timestamp_ms(raw[0], "open_time")
            closing = _timestamp_ms(raw[6], "close_time")
            open_price = _decimal(raw[1], "open")
            high = _decimal(raw[2], "high")
            low = _decimal(raw[3], "low")
            close = _decimal(raw[4], "close")
            volume = _decimal(raw[5], "volume", allow_zero=True)
            if opening >= closing or low > min(open_price, close) or high < max(open_price, close):
                raise BinanceDataError("kline timestamps or OHLC values are inconsistent")
            rows.append(
                BinanceKline(
                    symbol,
                    interval,
                    opening,
                    closing,
                    open_price,
                    high,
                    low,
                    close,
                    volume,
                )
            )
        if any(a.open_time >= b.open_time for a, b in zip(rows, rows[1:], strict=False)):
            raise BinanceDataError("klines must be strictly time ordered")
        return tuple(rows)

    def fetch_book_ticker(self, symbol: str) -> BinanceBookTicker:
        _symbol(symbol)
        payload = self._get_json("/api/v3/ticker/bookTicker", {"symbol": symbol})
        if not isinstance(payload, dict) or payload.get("symbol") != symbol:
            raise BinanceDataError("book ticker does not match the requested symbol")
        bid = _decimal(payload.get("bidPrice"), "bidPrice")
        ask = _decimal(payload.get("askPrice"), "askPrice")
        if bid > ask:
            raise BinanceDataError("book ticker bid cannot exceed ask")
        observed = self._clock()
        if observed.tzinfo is None or observed.utcoffset() != UTC.utcoffset(observed):
            raise BinanceDataError("client clock must return UTC")
        return BinanceBookTicker(
            symbol,
            bid,
            _decimal(payload.get("bidQty"), "bidQty"),
            ask,
            _decimal(payload.get("askQty"), "askQty"),
            observed,
        )

    def _get_json(self, path: str, parameters: dict[str, str]) -> Any:
        if path not in _ALLOWED_PATHS:
            raise BinanceDataError("endpoint is not public-paper allowlisted")
        url = f"{PUBLIC_DATA_HOST}{path}?{urllib.parse.urlencode(parameters)}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/json", "User-Agent": "tios-paper/1"},
        )
        for attempt in range(self._max_attempts):
            try:
                raw = self._transport(request, self._timeout_seconds)
                if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
                    raise BinanceDataError("public Binance response is invalid or too large")
                return json.loads(raw)
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt + 1 == self._max_attempts:
                    raise BinanceDataError(f"public Binance HTTP {error.code}") from error
                retry_after = error.headers.get("Retry-After") if error.headers else None
                try:
                    delay = float(retry_after) if retry_after is not None else 2**attempt
                except (ValueError, OverflowError):
                    delay = 2**attempt
                self._sleep(min(60.0, max(0.0, delay)))
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise BinanceDataError("public Binance returned malformed JSON") from error
            except urllib.error.URLError as error:
                raise BinanceDataError("public Binance data request failed") from error
        raise BinanceDataError("public Binance retry budget exhausted")


def _symbol(symbol: str) -> None:
    if symbol not in ALLOWED_SYMBOLS:
        raise BinanceDataError("paper symbols are limited to BTCUSDT and ETHUSDT")
