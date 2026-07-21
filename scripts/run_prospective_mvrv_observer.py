#!/usr/bin/env python3
"""Prospective observer for the frozen MVRV dislocation variant (D-110 / D-111).

Fetches recent daily CapMVRVCur from the public CoinMetrics community API (keyless GET),
applies the exact frozen rule from research/PROSPECTIVE_MVRV_DISLOCATION_V1.yaml, and
appends at most one observation row per source day. It records signal state only — never
returns, hit rates, or any performance number; those wait for the first review.

    python scripts/run_prospective_mvrv_observer.py

Intended to be run daily (orchestrator loop or cron). Idempotent per source day.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "prospective" / "MVRV-DISLOCATION-V1"
OBS_PATH = OUT_DIR / "observations.jsonl"
PREREG = "research/PROSPECTIVE_MVRV_DISLOCATION_V1.yaml"

# Frozen rule (must mirror the prereg exactly; the prereg file is the authority).
WINDOW_DAYS = 30
Z_THRESHOLD = 2.0
SIDE = "LOW"
AVAILABILITY_LAG_DAYS = 3  # source day D usable from D+3 00:00 UTC
BOUNDARY_SOURCE_DAY = "2026-06-28"  # on/before this day is in-sample, never prospective

API = (
    "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
    "?assets=btc&metrics=CapMVRVCur&frequency=1d&page_size=120&start_time={start}"
)


def fetch_series() -> list[tuple[str, float]]:
    start = (datetime.now(tz=UTC) - timedelta(days=WINDOW_DAYS + AVAILABILITY_LAG_DAYS + 20)).date()
    url = API.format(start=start.isoformat())
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed public host
        payload = json.loads(response.read())
    rows = []
    for item in payload.get("data", []):
        day = item["time"][:10]
        value = float(item["CapMVRVCur"])
        if value > 0:
            rows.append((day, value))
    return sorted(rows)


def latest_available(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Drop source days the availability lag has not yet released."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=AVAILABILITY_LAG_DAYS)).date().isoformat()
    return [(day, value) for day, value in rows if day <= cutoff]


def observe() -> dict:
    rows = latest_available(fetch_series())
    if not rows:
        raise RuntimeError("CoinMetrics returned no available rows")
    day, value = rows[-1]
    prior = [math.log(v) for _, v in rows[-(WINDOW_DAYS + 1) : -1]]

    if len(prior) < WINDOW_DAYS:
        state, z = "WARMING_UP", None
    else:
        mean = sum(prior) / WINDOW_DAYS
        var = sum((v - mean) ** 2 for v in prior) / WINDOW_DAYS
        if var <= 0:
            state, z = "FLAT", None
        else:
            z = (math.log(value) - mean) / math.sqrt(var)
            triggered = z < -Z_THRESHOLD if SIDE == "LOW" else z > Z_THRESHOLD
            state = "WOULD_ENTER" if triggered else "FLAT"

    return {
        "schema_version": 1,
        "prereg": PREREG,
        "observed_at": datetime.now(tz=UTC).isoformat(),
        "latest_available_source_day": day,
        "log_mvrv": round(math.log(value), 8),
        "z_score": round(z, 6) if z is not None else None,
        "signal_state": state,
        "prospective": day > BOUNDARY_SOURCE_DAY,
    }


def main() -> int:
    row = observe()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_day = row["latest_available_source_day"]
    if OBS_PATH.exists():
        for line in OBS_PATH.read_text().splitlines():
            if json.loads(line)["latest_available_source_day"] == source_day:
                print(f"already observed source day {source_day}; no-op")
                return 0
    with OBS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
