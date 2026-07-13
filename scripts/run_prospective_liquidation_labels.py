#!/usr/bin/env python3
"""Causally evaluate and offline-verify prospective liquidation labels."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from run_prospective_liquidation_observer import (
    AUTHORITY,
    DEFAULT_OUTPUT,
    canonical_bytes,
    parse_utc,
    sha256,
    verify_directory,
    write_bytes_content_addressed,
)

from tios.strategy.liquidation_stress import LiquidationStressError
from tios.strategy.prospective_labels import HORIZONS, gross_return, label_times, parse_exact_kline

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_LABEL_CONTRACT_V1.yaml"
ENDPOINT = "https://data-api.binance.vision/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1m"


def utc_now() -> datetime:
    return datetime.now(UTC)


def fetch_exact_kline(at: datetime) -> bytes:
    start = int(at.timestamp() * 1000)
    query = urllib.parse.urlencode(
        {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "startTime": start,
            "endTime": start + 59_999,
            "limit": 1,
        }
    )
    request = urllib.request.Request(
        f"{ENDPOINT}?{query}",
        headers={"Accept": "application/json", "User-Agent": "TradingOS-Prospective-Labels/1"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - fixed HTTPS URL
        return bytes(response.read())


def complete_windows(directory: Path) -> list[tuple[str, datetime]]:
    rows: list[tuple[str, datetime]] = []
    for path in sorted(directory.glob("session_*.json")):
        payload = json.loads(path.read_text())
        session_hash = path.stem.removeprefix("session_")
        for row in payload.get("observation", {}).get("complete_windows", []):
            rows.append((session_hash, parse_utc(row["start"])))
    return sorted(rows, key=lambda item: item[1])


def build_snapshot(directory: Path, *, evaluated_at: datetime) -> dict[str, Any]:
    contract_hash = sha256(CONTRACT.read_bytes())
    label_rows: list[dict[str, Any]] = []
    raw_directory = directory / "labels" / "raw"
    for session_hash, window in complete_windows(directory):
        for horizon in HORIZONS:
            timing = label_times(window, horizon)
            base: dict[str, Any] = {
                "source_session_sha256": session_hash,
                "window_start": window.isoformat(),
                "window_close": timing.window_close.isoformat(),
                "horizon": horizon,
                "entry_open_time": timing.entry_open.isoformat(),
                "exit_open_time": timing.exit_open.isoformat(),
                "available_at": timing.available_at.isoformat(),
            }
            if evaluated_at < timing.available_at:
                label_rows.append(
                    base
                    | {
                        "status": "NOT_AVAILABLE",
                        "entry_raw_sha256": None,
                        "exit_raw_sha256": None,
                        "entry_open": None,
                        "exit_open": None,
                        "gross_return": None,
                    }
                )
                continue
            entry_raw = fetch_exact_kline(timing.entry_open)
            exit_raw = fetch_exact_kline(timing.exit_open)
            entry = parse_exact_kline(entry_raw, expected_open=timing.entry_open)
            exit_ = parse_exact_kline(exit_raw, expected_open=timing.exit_open)
            entry_hash = sha256(entry_raw)
            exit_hash = sha256(exit_raw)
            write_bytes_content_addressed(raw_directory, "kline", entry_raw)
            write_bytes_content_addressed(raw_directory, "kline", exit_raw)
            label_rows.append(
                base
                | {
                    "status": "AVAILABLE_RETAIN_ONLY",
                    "entry_raw_sha256": entry_hash,
                    "exit_raw_sha256": exit_hash,
                    "entry_open": str(entry),
                    "exit_open": str(exit_),
                    "gross_return": str(gross_return(entry, exit_)),
                }
            )
    return {
        "schema_version": 1,
        "label_contract_id": "PROSPECTIVE-BTC-LIQUIDATION-LABELS-V1",
        "label_contract_sha256": contract_hash,
        "evaluated_at": evaluated_at.isoformat(),
        "source": {
            "endpoint": ENDPOINT,
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "authentication": "NONE",
        },
        "labels": label_rows,
        "analysis": "PROHIBITED_DURING_WARMUP",
        "metric_eligible": False,
        "scorecard_eligible": False,
        "promotion_eligible": False,
        "authority": AUTHORITY,
    }


def verify_snapshot(path: Path, directory: Path) -> None:
    if path.stem.removeprefix("label_snapshot_") != sha256(path.read_bytes()):
        raise LiquidationStressError("label snapshot hash mismatch")
    payload = json.loads(path.read_text())
    if payload.get("label_contract_sha256") != sha256(CONTRACT.read_bytes()):
        raise LiquidationStressError("label contract hash mismatch")
    expected_source = {
        "endpoint": ENDPOINT,
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "authentication": "NONE",
    }
    if payload.get("source") != expected_source:
        raise LiquidationStressError("label source contract changed")
    if payload.get("authority") != AUTHORITY:
        raise LiquidationStressError("label authority boundary changed")
    eligibility_fields = ("metric_eligible", "scorecard_eligible", "promotion_eligible")
    if any(payload.get(key) is not False for key in eligibility_fields):
        raise LiquidationStressError("label eligibility boundary changed")
    if payload.get("analysis") != "PROHIBITED_DURING_WARMUP":
        raise LiquidationStressError("warmup analysis boundary changed")
    evaluated_at = parse_utc(payload["evaluated_at"])
    expected_windows = {
        (session, window)
        for session, window in complete_windows(directory)
        if label_times(window, "1H").window_close <= evaluated_at
    }
    seen: set[tuple[str, datetime, str]] = set()
    for row in payload["labels"]:
        window = parse_utc(row["window_start"])
        key = (row["source_session_sha256"], window, row["horizon"])
        if key[:2] not in expected_windows or key in seen:
            raise LiquidationStressError("label window identity is invalid or duplicated")
        seen.add(key)
        timing = label_times(window, row["horizon"])
        expected_times = (
            ("window_close", timing.window_close),
            ("entry_open_time", timing.entry_open),
            ("exit_open_time", timing.exit_open),
            ("available_at", timing.available_at),
        )
        for field, value in expected_times:
            if row[field] != value.isoformat():
                raise LiquidationStressError("label timing drift")
        if evaluated_at < timing.available_at:
            expected_null = {
                "status": "NOT_AVAILABLE",
                "entry_raw_sha256": None,
                "exit_raw_sha256": None,
                "entry_open": None,
                "exit_open": None,
                "gross_return": None,
            }
            if any(row.get(field) != value for field, value in expected_null.items()):
                raise LiquidationStressError("future label was exposed early")
            continue
        if row.get("status") != "AVAILABLE_RETAIN_ONLY":
            raise LiquidationStressError("causally available label is missing")
        prices = []
        for prefix, expected_open in (("entry", timing.entry_open), ("exit", timing.exit_open)):
            digest = row[f"{prefix}_raw_sha256"]
            raw_path = directory / "labels" / "raw" / f"kline_{digest}.json"
            if not raw_path.is_file() or sha256(raw_path.read_bytes()) != digest:
                raise LiquidationStressError("label raw-byte hash mismatch")
            price = parse_exact_kline(raw_path.read_bytes(), expected_open=expected_open)
            if row[f"{prefix}_open"] != str(price):
                raise LiquidationStressError("label price drift")
            prices.append(price)
        if row.get("gross_return") != str(gross_return(prices[0], prices[1])):
            raise LiquidationStressError("label return reconstruction mismatch")
    expected_keys = {
        (session, window, horizon) for session, window in expected_windows for horizon in HORIZONS
    }
    if seen != expected_keys:
        raise LiquidationStressError("label snapshot is incomplete")


def verify_all(directory: Path) -> int:
    verify_directory(directory)
    paths = sorted((directory / "labels").glob("label_snapshot_*.json"))
    for path in paths:
        verify_snapshot(path, directory)
    return len(paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not CONTRACT.is_file():
        raise SystemExit("prospective label contract is missing")
    verified = verify_all(args.output_dir)
    if args.verify_only:
        print(f"verified {verified} prospective label snapshots")
        return 0
    snapshot = build_snapshot(args.output_dir, evaluated_at=utc_now())
    path = write_bytes_content_addressed(
        args.output_dir / "labels", "label_snapshot", canonical_bytes(snapshot)
    )
    verify_snapshot(path, args.output_dir)
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
