"""Fetch and freeze public Coinbase source bytes for D-075.

This script performs read-only unauthenticated HTTP GETs. It does not calculate a
strategy signal, future return, or performance metric.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data/raw/coinbase_exchange/cross_venue_premium_v1.json"
API = "https://api.exchange.coinbase.com"
DOCS = (
    "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles",
    "https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-all-known-trading-pairs",
)
PRODUCTS = ("BTC-USD", "USDT-USD")
USER_AGENT = "TradingOS-offline-research/1.0"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url: str, *, retries: int = 5) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        requested_at = _utc_now()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                body = response.read()
                return {
                    "url": url,
                    "requested_at_utc": requested_at,
                    "received_at_utc": _utc_now(),
                    "attempts": attempt,
                    "status": response.status,
                    "response_date": response.headers.get("Date"),
                    "content_type": response.headers.get("Content-Type"),
                    "body_bytes": len(body),
                    "body_sha256": _sha256(body),
                    "body_base64": base64.b64encode(body).decode("ascii"),
                }
        except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError) as error:
            last_error = error
            if attempt == retries:
                break
            time.sleep(min(2**attempt, 10))
    raise RuntimeError(f"failed public GET after {retries} attempts: {url}") from last_error


def _candle_url(product: str, start: datetime, end: datetime) -> str:
    query = urllib.parse.urlencode({"granularity": "3600", "start": _iso(start), "end": _iso(end)})
    return f"{API}/products/{product}/candles?{query}"


def fetch(output: Path, *, delay_seconds: float = 0.20) -> dict[str, Any]:
    start = datetime(2021, 5, 1, tzinfo=UTC)
    end_exclusive = datetime(2026, 7, 1, tzinfo=UTC)
    chunk = timedelta(hours=240)
    retrieval_started = _utc_now()
    sources: list[dict[str, Any]] = []

    for url in DOCS:
        item = _get(url)
        item["kind"] = "OFFICIAL_DOCUMENTATION"
        sources.append(item)

    for product in PRODUCTS:
        item = _get(f"{API}/products/{product}")
        item.update({"kind": "PRODUCT_IDENTITY", "product_id": product})
        sources.append(item)

    windows: list[dict[str, Any]] = []
    total_windows = 0
    cursor = start
    while cursor < end_exclusive:
        total_windows += 1
        cursor = min(cursor + chunk, end_exclusive)
    total_requests = total_windows * len(PRODUCTS)
    completed = 0

    for product in PRODUCTS:
        cursor = start
        while cursor < end_exclusive:
            window_end = min(cursor + chunk, end_exclusive)
            item = _get(_candle_url(product, cursor, window_end))
            item.update(
                {
                    "kind": "PRODUCT_CANDLES",
                    "product_id": product,
                    "granularity_seconds": 3600,
                    "requested_start_utc": _iso(cursor),
                    "requested_end_utc": _iso(window_end),
                }
            )
            windows.append(item)
            completed += 1
            if completed % 25 == 0 or completed == total_requests:
                print(f"fetched {completed}/{total_requests} candle windows", flush=True)
            cursor = window_end
            time.sleep(delay_seconds)

    package = {
        "schema": "tios-coinbase-cross-venue-raw-bundle-v1",
        "decision": "D-075",
        "purpose": "SOURCE_AND_DATA_FREEZE_ONLY_NO_PERFORMANCE",
        "retrieval_started_utc": retrieval_started,
        "retrieval_completed_utc": _utc_now(),
        "request_user_agent": USER_AGENT,
        "query_start_utc": _iso(start),
        "query_end_exclusive_utc": _iso(end_exclusive),
        "chunk_hours": 240,
        "sources": sources,
        "candle_windows": windows,
        "safety": {
            "authenticated": False,
            "secrets_used": False,
            "performance_computed": False,
            "venue_connection": "PUBLIC_MARKET_DATA_HTTP_ONLY",
            "execution_authority": "NONE",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(package, sort_keys=True, separators=(",", ":")) + "\n")
    os.replace(temporary, output)
    print(f"wrote {output} sha256={_sha256(output.read_bytes())}", flush=True)
    return package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--delay-seconds", type=float, default=0.20)
    args = parser.parse_args()
    fetch(args.output, delay_seconds=args.delay_seconds)


if __name__ == "__main__":
    main()
