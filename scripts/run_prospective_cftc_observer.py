#!/usr/bin/env python3
"""Prospective observer for the frozen CFTC positioning variant (D-111).

Fetches the CFTC legacy futures-only Commitments of Traders report for BTC
(CME contract market code 133741, Socrata dataset 6dca-aqww) from the public
publicreporting.cftc.gov API (keyless GET), applies the exact frozen rule from
research/PROSPECTIVE_CFTC_POSITIONING_V1.yaml, and appends at most one
observation row per weekly report_date. It records signal state only — never
prices, returns, or any performance number; those wait for the first review.

    python scripts/run_prospective_cftc_observer.py

Intended to be run weekly (orchestrator loop or cron). Idempotent per report_date.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "artifacts" / "prospective" / "CFTC-POSITIONING-V1"
OBS_PATH = OUT_DIR / "observations.jsonl"
PREREG = "research/PROSPECTIVE_CFTC_POSITIONING_V1.yaml"

# Frozen rule (must mirror the prereg exactly; the prereg file is the authority).
WINDOW_WEEKS = 26
Z_THRESHOLD = 1.5
SIDE = "LOW"
AVAILABILITY_LAG_DAYS = 8  # report date + 8 calendar days at 00:00 UTC
BOUNDARY_REPORT_DATE = "2026-07-14"  # on/before this report date is in-sample, never prospective

# Socrata legacy futures-only COT dataset, verified against
# research/CFTC_BTC_POSITIONING_DATA_PACKAGE_V1.json (same dataset/contract code the
# freezing campaign used) and a live test fetch on 2026-07-21:
#   https://publicreporting.cftc.gov/resource/6dca-aqww.json
#     ?$where=cftc_contract_market_code="133741"
#     &$select=report_date_as_yyyy_mm_dd,noncomm_positions_long_all,
#              noncomm_positions_short_all,open_interest_all
#     &$order=report_date_as_yyyy_mm_dd&$limit=5000
# Field names confirmed empirically to match exactly (no surprises).
DATASET_ID = "6dca-aqww"
CONTRACT_MARKET_CODE = "133741"  # BITCOIN - CHICAGO MERCANTILE EXCHANGE
API = (
    f"https://publicreporting.cftc.gov/resource/{DATASET_ID}.json"
    f'?$where=cftc_contract_market_code="{CONTRACT_MARKET_CODE}"'
    "&$select=report_date_as_yyyy_mm_dd,noncomm_positions_long_all,"
    "noncomm_positions_short_all,open_interest_all"
    "&$order=report_date_as_yyyy_mm_dd&$limit=5000"
)


def fetch_series() -> list[tuple[str, float]]:
    with urllib.request.urlopen(API, timeout=30) as response:  # noqa: S310 - fixed public host
        payload = json.loads(response.read())
    rows = []
    for item in payload:
        report_date = item["report_date_as_yyyy_mm_dd"][:10]
        oi = float(item["open_interest_all"])
        if oi <= 0:
            continue
        share = (
            float(item["noncomm_positions_long_all"]) - float(item["noncomm_positions_short_all"])
        ) / oi
        rows.append((report_date, share))
    return sorted(rows)


def latest_available(rows: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Drop reports the availability lag has not yet released."""
    cutoff = (datetime.now(tz=UTC) - timedelta(days=AVAILABILITY_LAG_DAYS)).date().isoformat()
    return [(day, value) for day, value in rows if day <= cutoff]


def observe() -> dict:
    rows = latest_available(fetch_series())
    if not rows:
        raise RuntimeError("CFTC API returned no available reports")
    day, value = rows[-1]
    prior = [v for _, v in rows[-(WINDOW_WEEKS + 1) : -1]]

    if len(prior) < WINDOW_WEEKS:
        state, z = "WARMING_UP", None
    else:
        mean = sum(prior) / WINDOW_WEEKS
        var = sum((v - mean) ** 2 for v in prior) / WINDOW_WEEKS
        if var <= 0:
            state, z = "FLAT", None
        else:
            z = (value - mean) / math.sqrt(var)
            triggered = z <= -Z_THRESHOLD if SIDE == "LOW" else z >= Z_THRESHOLD
            state = "WOULD_ENTER" if triggered else "FLAT"

    availability_utc = (
        datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(days=AVAILABILITY_LAG_DAYS)
    ).isoformat()

    return {
        "schema_version": 1,
        "prereg": PREREG,
        "observed_at": datetime.now(tz=UTC).isoformat(),
        "report_date": day,
        "availability_utc": availability_utc,
        "net_noncomm_share": round(value, 8),
        "z_score": round(z, 6) if z is not None else None,
        "signal_state": state,
        "prospective": day > BOUNDARY_REPORT_DATE,
        "frozen_params": {
            "prior_window_weeks": WINDOW_WEEKS,
            "z_threshold": Z_THRESHOLD,
            "side": SIDE,
            "availability_lag_days": AVAILABILITY_LAG_DAYS,
            "boundary_report_date": BOUNDARY_REPORT_DATE,
        },
    }


def main() -> int:
    row = observe()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report_date = row["report_date"]
    if OBS_PATH.exists():
        for line in OBS_PATH.read_text().splitlines():
            if json.loads(line)["report_date"] == report_date:
                print(f"already observed report_date {report_date}; no-op")
                return 0
    with OBS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
