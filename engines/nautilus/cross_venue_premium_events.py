"""Nautilus-environment event-order conformance for D-075."""

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

from engines.cross_venue_premium_data import load_cross_venue, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
PULSE = pd.Timedelta(hours=6)


def event_hash(
    spot: pd.DataFrame, source: pd.DataFrame, trial: dict[str, Any]
) -> tuple[str, int, int]:
    rows = list(source.itertuples(index=False))
    values = [float(row.log_premium) for row in rows]
    prefix = [0.0]
    squared = [0.0]
    run_length: list[int] = []
    for index, value in enumerate(values):
        prefix.append(prefix[-1] + value)
        squared.append(squared[-1] + value * value)
        consecutive = (
            index > 0 and rows[index].timestamp_open_utc - rows[index - 1].timestamp_open_utc == BAR
        )
        run_length.append(run_length[-1] + 1 if consecutive else 1)
    candidates: set[pd.Timestamp] = set()
    width = trial["baseline_hours"]
    for index in range(width, len(rows)):
        if run_length[index] < width + 1:
            continue
        start = index - width
        mean = (prefix[index] - prefix[start]) / width
        variance = (squared[index] - squared[start]) / width - mean * mean
        if variance <= 0:
            continue
        z_score = (values[index] - mean) / math.sqrt(variance)
        eligible = (
            z_score > trial["threshold"]
            if trial["interpretation"] == "CONTINUATION_POSITIVE"
            else z_score < -trial["threshold"]
        )
        if eligible and rows[index].source_close_utc >= spot.index[0]:
            mapped = int(spot.index.searchsorted(rows[index].source_close_utc, side="right"))
            if mapped < len(spot):
                candidates.add(spot.index[mapped])
    interruptions = {
        spot.index[mapped]
        for index, row in enumerate(rows)
        if index > 0
        and row.timestamp_open_utc - rows[index - 1].timestamp_open_utc != BAR
        and (mapped := int(spot.index.searchsorted(row.source_close_utc, side="right"))) < len(spot)
    }
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    scheduled: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (index > 0 and opened - spot.index[index - 1] != BAR) or opened in interruptions
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = 1
            held = False
            scheduled = None
        if not (gap or held or was_held) and opened in candidates:
            entries[index] = 1
            held = True
            scheduled = opened + PULSE
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
    source = load_cross_venue(ROOT, request["package_path"])
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
    args.output.write_text(
        json.dumps(
            {
                "engine": "nautilus_trader",
                "version": nautilus_trader.__version__,
                "segments": segments,
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
