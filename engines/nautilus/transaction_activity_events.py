"""Nautilus-environment event-order conformance harness."""

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

from engines.transaction_activity_data import load_activity, load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
DAY = pd.Timedelta(days=1)


def event_hash(
    spot: pd.DataFrame, activity: pd.DataFrame, trial: dict[str, Any], start: pd.Timestamp
) -> tuple[str, int, int]:
    rows = list(activity.itertuples(index=False))
    candidates: set[pd.Timestamp] = set()
    for index in range(trial["window"], len(rows)):
        sample = rows[index - trial["window"] : index + 1]
        if any(
            right.source_day - left.source_day != DAY
            for left, right in zip(sample, sample[1:], strict=False)
        ):
            continue
        baseline = [math.log(item.count) for item in sample[:-1]]
        mean = sum(baseline) / len(baseline)
        variance = sum((value - mean) ** 2 for value in baseline) / len(baseline)
        if variance == 0:
            continue
        z_score = (math.log(sample[-1].count) - mean) / math.sqrt(variance)
        eligible = z_score > 1 if trial["side"] == "HIGH" else z_score < -1
        if eligible and sample[-1].source_day >= start - DAY * 2:
            candidates.add(sample[-1].source_day + DAY * 2 + BAR)
    gaps = {
        left.source_day + DAY * 3 + BAR
        for left, right in zip(rows, rows[1:], strict=False)
        if right.source_day - left.source_day != DAY
    }
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    scheduled: pd.Timestamp | None = None
    previous: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (previous is not None and opened - previous != BAR) or opened in gaps
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = 1
            held = False
            scheduled = None
        if not (gap or held or was_held) and opened in candidates:
            entries[index] = 1
            held = True
            scheduled = opened + DAY * trial["holding_days"]
        previous = opened
    digest = hashlib.sha256((entries + exits * 2).tobytes()).hexdigest()
    return digest, int(entries.sum()), int(exits.sum())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    spot_all = load_spot(ROOT / request["spot_path"])
    activity = load_activity(ROOT / request["activity_path"])
    segments = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = spot_all.loc[lower:upper]
        segments[segment] = {}
        for trial in request["trials"]:
            name = trial_name(trial["side"], trial["window"], trial["holding_days"])
            digest, buys, sells = event_hash(spot, activity, trial, spot.index[0])
            segments[segment][name] = {"event_hash": digest, "buy_count": buys, "sell_count": sells}
    payload = {
        "engine": "nautilus_trader",
        "version": nautilus_trader.__version__,
        "segments": segments,
    }
    args.output.write_text(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
