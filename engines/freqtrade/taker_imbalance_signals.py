"""Freqtrade-environment dataframe conformance for Spot taker imbalance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import freqtrade
import numpy as np
import pandas as pd  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engines.taker_imbalance_data import load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
PULSE = pd.Timedelta(hours=6)


def signal_hash(
    spot: pd.DataFrame, source: pd.DataFrame, trial: dict[str, Any]
) -> tuple[str, int, int]:
    frame = source.copy()
    valid = (
        frame["quote_volume"].gt(0)
        & frame["taker_buy_quote_volume"].between(0, frame["quote_volume"])
        & frame["close_timestamp_utc"].ge(frame["timestamp_open_utc"])
    )
    consecutive = frame["timestamp_open_utc"].diff().eq(BAR)
    group = (~(valid & valid.shift(fill_value=False) & consecutive)).cumsum()
    feature = (2 * frame["taker_buy_quote_volume"] / frame["quote_volume"] - 1).where(valid)
    prior = feature.groupby(group).shift()
    mean = prior.groupby(group).transform(
        lambda value: value.rolling(trial["baseline_hours"]).mean()
    )
    std = prior.groupby(group).transform(
        lambda value: value.rolling(trial["baseline_hours"]).std(ddof=0)
    )
    z_score = (feature - mean) / std
    eligible = (
        z_score > trial["threshold"]
        if trial["interpretation"] == "CONTINUATION_HIGH"
        else z_score < -trial["threshold"]
    )
    candidates: set[pd.Timestamp] = set()
    for row in frame[valid & std.gt(0) & eligible].itertuples(index=False):
        if row.close_timestamp_utc >= spot.index[0]:
            mapped = int(spot.index.searchsorted(row.close_timestamp_utc, side="right"))
            if mapped < len(spot):
                candidates.add(spot.index[mapped])
    interruptions: set[pd.Timestamp] = set()
    for row in frame[~valid | ~consecutive].itertuples(index=False):
        boundary = max(row.timestamp_open_utc, row.close_timestamp_utc)
        mapped = int(spot.index.searchsorted(boundary, side="right"))
        if mapped < len(spot):
            interruptions.add(spot.index[mapped])
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
            digest, buys, sells = signal_hash(spot, source, trial)
            segments[segment][name] = {"event_hash": digest, "buy_count": buys, "sell_count": sells}
    args.output.write_text(
        json.dumps(
            {"engine": "freqtrade", "version": freqtrade.__version__, "segments": segments},
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
