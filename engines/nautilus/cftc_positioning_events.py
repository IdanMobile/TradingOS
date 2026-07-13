"""Nautilus-environment event-order conformance for CFTC positioning."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import nautilus_trader
import numpy as np
import pandas as pd  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engines.cftc_positioning_data import (  # noqa: E402
    load_positioning,
    load_spot,
    trial_name,
)

BAR = pd.Timedelta(hours=1)
WEEK = pd.Timedelta(days=7)


def event_hash(
    spot: pd.DataFrame, positioning: pd.DataFrame, trial: dict[str, Any]
) -> tuple[str, int, int]:
    rows = list(positioning.itertuples(index=False))
    candidates: dict[pd.Timestamp, pd.Timestamp] = {}
    for index in range(trial["baseline_weeks"], len(rows)):
        sample = rows[index - trial["baseline_weeks"] : index + 1]
        if any(
            not pd.Timedelta(days=6) <= right.report_date - left.report_date <= pd.Timedelta(days=8)
            for left, right in zip(sample, sample[1:], strict=False)
        ):
            continue
        baseline = [float(item.net_share) for item in sample[:-1]]
        mean = sum(baseline) / len(baseline)
        variance = sum((value - mean) ** 2 for value in baseline) / len(baseline)
        if variance == 0:
            continue
        z_score = (float(sample[-1].net_share) - mean) / math.sqrt(variance)
        eligible = (
            z_score > trial["threshold"]
            if trial["interpretation"] == "ALIGNED_HIGH"
            else z_score < -trial["threshold"]
        )
        if eligible and sample[-1].available_at >= spot.index[0]:
            mapped = int(spot.index.searchsorted(sample[-1].available_at, side="right"))
            if mapped < len(spot):
                candidates[spot.index[mapped]] = sample[-1].report_date
    source_gaps: set[pd.Timestamp] = set()
    for left, right in zip(rows, rows[1:], strict=False):
        delta = right.report_date - left.report_date
        if (
            not pd.Timedelta(days=6) <= delta <= pd.Timedelta(days=8)
            and right.available_at >= spot.index[0]
        ):
            mapped = int(spot.index.searchsorted(right.available_at, side="right"))
            if mapped < len(spot):
                source_gaps.add(spot.index[mapped])
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    scheduled: pd.Timestamp | None = None
    previous: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (previous is not None and opened - previous != BAR) or opened in source_gaps
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = 1
            held = False
            scheduled = None
        if not (gap or held or was_held) and opened in candidates:
            entries[index] = 1
            held = True
            scheduled = opened + WEEK
        previous = opened
    digest = hashlib.sha256((entries + exits * 2).tobytes()).hexdigest()
    return digest, int(entries.sum()), int(exits.sum())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    spot_all = load_spot(ROOT, request["package_path"])
    positioning = load_positioning(ROOT, request["package_path"])
    segments = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = spot_all.loc[lower:upper]
        segments[segment] = {}
        for trial in request["trials"]:
            name = trial_name(trial["interpretation"], trial["baseline_weeks"], trial["threshold"])
            digest, buys, sells = event_hash(spot, positioning, trial)
            segments[segment][name] = {
                "event_hash": digest,
                "buy_count": buys,
                "sell_count": sells,
            }
    payload = {
        "engine": "nautilus_trader",
        "version": nautilus_trader.__version__,
        "segments": segments,
    }
    args.output.write_text(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
