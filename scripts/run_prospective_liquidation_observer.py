#!/usr/bin/env python3
"""Capture one bounded public BTC liquidation-snapshot observation session."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from websockets.asyncio.client import connect

from tios.strategy.liquidation_stress import (
    LiquidationStressError,
    parse_force_order_message,
    window_start,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_STRESS_SIGNAL_V1.yaml"
DEFAULT_OUTPUT = ROOT / "artifacts/prospective/BTC-LIQUIDATION-STRESS-V1"
EXCHANGE_INFO_URL = "https://dapi.binance.com/dapi/v1/exchangeInfo"
WEBSOCKET_URL = "wss://dstream.binance.com/ws/btcusd_perp@forceOrder"
EXPECTED_SYMBOL = "BTCUSD_PERP"
EXPECTED_PAIR = "BTCUSD"


def utc_now() -> datetime:
    return datetime.now(UTC)


def canonical_bytes(payload: object) -> bytes:
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_exchange_info() -> tuple[bytes, Decimal]:
    request = urllib.request.Request(
        EXCHANGE_INFO_URL,
        headers={"Accept": "application/json", "User-Agent": "TradingOS-Prospective-Observer/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS URL
        body = response.read()
    payload = json.loads(body)
    matches = [item for item in payload["symbols"] if item.get("symbol") == EXPECTED_SYMBOL]
    if len(matches) != 1:
        raise LiquidationStressError("exchange info must contain exactly one BTCUSD_PERP")
    symbol = matches[0]
    if (
        symbol.get("pair") != EXPECTED_PAIR
        or symbol.get("contractType") != "PERPETUAL"
        or symbol.get("contractStatus") != "TRADING"
    ):
        raise LiquidationStressError("BTCUSD_PERP exchange identity is not active and exact")
    contract_size = Decimal(str(symbol["contractSize"]))
    if contract_size <= 0 or not contract_size.is_finite():
        raise LiquidationStressError("BTCUSD_PERP contract size is invalid")
    return body, contract_size


async def capture(
    duration_seconds: int, contract_size: Decimal
) -> tuple[list[dict[str, str]], str]:
    events: list[dict[str, str]] = []
    status = "COMPLETE"
    deadline = time.monotonic() + duration_seconds
    try:
        async with connect(
            WEBSOCKET_URL,
            open_timeout=15,
            close_timeout=5,
            ping_interval=20,
            max_size=1_000_000,
        ) as websocket:
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    async with asyncio.timeout(remaining):
                        message = await websocket.recv()
                except TimeoutError:
                    break
                if not isinstance(message, str):
                    raise LiquidationStressError("binary websocket message is not accepted")
                received_at = utc_now()
                parse_force_order_message(
                    message,
                    received_at=received_at,
                    expected_symbol=EXPECTED_SYMBOL,
                    expected_pair=EXPECTED_PAIR,
                    contract_size_usd=contract_size,
                )
                events.append({"raw_message": message, "received_at": received_at.isoformat()})
    except Exception as error:
        status = f"FAILED_{type(error).__name__}"
    return events, status


def write_content_addressed(directory: Path, prefix: str, payload: object) -> Path:
    data = canonical_bytes(payload)
    digest = sha256(data)
    destination = directory / f"{prefix}_{digest}.json"
    directory.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != data:
            raise LiquidationStressError("content-addressed artifact collision")
        return destination
    fd, temporary = tempfile.mkstemp(prefix=f".{prefix}-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def write_raw_content_addressed(directory: Path, prefix: str, data: bytes) -> Path:
    digest = sha256(data)
    destination = directory / f"{prefix}_{digest}.json"
    directory.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.read_bytes() != data:
            raise LiquidationStressError("raw content-addressed artifact collision")
        return destination
    fd, temporary = tempfile.mkstemp(prefix=f".{prefix}-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def build_session(
    *,
    started_at: datetime,
    ended_at: datetime,
    duration_seconds: int,
    source_status: str,
    events: list[dict[str, str]],
    exchange_info_hash: str,
    contract_size: Decimal,
    run_commit: str,
) -> dict[str, Any]:
    spec_hash = sha256(SPEC.read_bytes())
    signal_digest = sha256(
        f"{spec_hash}|{started_at.isoformat()}|SOURCE_WINDOW_INCOMPLETE".encode()
    )[:24]
    return {
        "schema_version": 1,
        "signal_spec_id": "PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1",
        "signal_spec_sha256": spec_hash,
        "run_commit": run_commit,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "requested_duration_seconds": duration_seconds,
        "source": {
            "exchange_info_url": EXCHANGE_INFO_URL,
            "websocket_url": WEBSOCKET_URL,
            "authentication": "NONE",
            "status": source_status,
            "exchange_info_sha256": exchange_info_hash,
            "symbol": EXPECTED_SYMBOL,
            "pair": EXPECTED_PAIR,
            "contract_size_usd": str(contract_size),
            "publication_semantics": "LATEST_ONE_PER_SYMBOL_PER_1000MS_SNAPSHOT",
            "complete_liquidation_tape": False,
        },
        "raw_events": events,
        "observation": {
            "event_count": len(events),
            "window_start": window_start(started_at).isoformat(),
            "window_complete": False,
            "state": "SOURCE_WINDOW_INCOMPLETE",
        },
        "signal": {
            "signal_id": f"SIG-{signal_digest}",
            "side": "FLAT",
            "rationale_code": "PROSPECTIVE_SOURCE_WINDOW_INCOMPLETE",
            "metric_eligible": False,
            "scorecard_eligible": False,
            "promotion_eligible": False,
        },
        "risk_decision": {
            "decision": "BLOCK",
            "reason": "NOT_PROMOTION_ELIGIBLE_AND_SOURCE_WINDOW_INCOMPLETE",
            "independent": True,
        },
        "authority": {
            "execution_authority": "NONE",
            "venue_connection": "NONE",
            "market_data_transport": "PUBLIC_READ_ONLY",
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
            "credentials_used": False,
        },
    }


def run_commit() -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if not 1 <= args.duration_seconds <= 3600:
        parser.error("--duration-seconds must be between 1 and 3600")
    return args


def main() -> int:
    args = parse_args()
    if not SPEC.is_file():
        raise SystemExit("prospective signal spec is missing")
    started_at = utc_now()
    exchange_info, contract_size = fetch_exchange_info()
    exchange_info_hash = sha256(exchange_info)
    raw_dir = args.output_dir / "raw"
    write_raw_content_addressed(raw_dir, "exchange_info", exchange_info)
    events, status = asyncio.run(capture(args.duration_seconds, contract_size))
    ended_at = utc_now()
    session = build_session(
        started_at=started_at,
        ended_at=ended_at,
        duration_seconds=args.duration_seconds,
        source_status=status,
        events=events,
        exchange_info_hash=exchange_info_hash,
        contract_size=contract_size,
        run_commit=run_commit(),
    )
    path = write_content_addressed(args.output_dir, "session", session)
    print(path)
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
