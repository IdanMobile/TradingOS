"""Nautilus-environment event-order conformance for Spot taker imbalance."""

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

from engines.taker_imbalance_data import load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
PULSE = pd.Timedelta(hours=6)


def event_hash(
    spot: pd.DataFrame, source: pd.DataFrame, trial: dict[str, Any]
) -> tuple[str, int, int]:
    rows = list(source.itertuples(index=False))
    valid = [
        row.quote_volume > 0
        and 0 <= row.taker_buy_quote_volume <= row.quote_volume
        and row.close_timestamp_utc >= row.timestamp_open_utc
        for row in rows
    ]
    values = [
        2 * row.taker_buy_quote_volume / row.quote_volume - 1 if valid[index] else 0.0
        for index, row in enumerate(rows)
    ]
    candidates: set[pd.Timestamp] = set()
    width = trial["baseline_hours"]
    for index in range(width, len(rows)):
        start = index - width
        sample = rows[start : index + 1]
        if not all(valid[start : index + 1]) or any(
            right.timestamp_open_utc - left.timestamp_open_utc != BAR
            for left, right in zip(sample[:-1], sample[1:], strict=True)
        ):
            continue
        baseline = values[start:index]
        mean = sum(baseline) / width
        variance = sum((value - mean) ** 2 for value in baseline) / width
        if variance == 0:
            continue
        z_score = (values[index] - mean) / math.sqrt(variance)
        eligible = (
            z_score > trial["threshold"]
            if trial["interpretation"] == "CONTINUATION_HIGH"
            else z_score < -trial["threshold"]
        )
        if eligible and rows[index].close_timestamp_utc >= spot.index[0]:
            mapped = int(spot.index.searchsorted(rows[index].close_timestamp_utc, side="right"))
            if mapped < len(spot):
                candidates.add(spot.index[mapped])
    interruptions: set[pd.Timestamp] = set()
    for index, row in enumerate(rows):
        discontinuity = (
            index > 0 and row.timestamp_open_utc - rows[index - 1].timestamp_open_utc != BAR
        )
        if valid[index] and not discontinuity:
            continue
        boundary = max(row.timestamp_open_utc, row.close_timestamp_utc)
        mapped = int(spot.index.searchsorted(boundary, side="right"))
        if mapped < len(spot):
            interruptions.add(spot.index[mapped])
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    scheduled: pd.Timestamp | None = None
    previous: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (previous is not None and opened - previous != BAR) or opened in interruptions
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = 1
            held = False
            scheduled = None
        if not (gap or held or was_held) and opened in candidates:
            entries[index] = 1
            held = True
            scheduled = opened + PULSE
        previous = opened
    return (
        hashlib.sha256((entries + exits * 2).tobytes()).hexdigest(),
        int(entries.sum()),
        int(exits.sum()),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    source = load_spot(ROOT, request["package_path"])
    segments = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = source.loc[lower:upper]
        segments[segment] = {}
        for trial in request["trials"]:
            name = trial_name(trial["interpretation"], trial["baseline_hours"], trial["threshold"])
            digest, buys, sells = event_hash(spot, source, trial)
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
