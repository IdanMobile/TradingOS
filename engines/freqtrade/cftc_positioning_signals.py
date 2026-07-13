"""Freqtrade-environment dataframe conformance for CFTC positioning."""

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

from engines.cftc_positioning_data import (  # noqa: E402
    load_positioning,
    load_spot,
    trial_name,
)

BAR = pd.Timedelta(hours=1)
WEEK = pd.Timedelta(days=7)


def signal_hash(
    spot: pd.DataFrame, positioning: pd.DataFrame, trial: dict[str, Any]
) -> tuple[str, int, int]:
    frame = positioning.copy()
    consecutive = frame["report_date"].diff().between(pd.Timedelta(days=6), pd.Timedelta(days=8))
    frame["group"] = (~consecutive).cumsum()
    prior = frame.groupby("group")["net_share"].shift()
    grouped = prior.groupby(frame["group"])
    mean = grouped.transform(lambda values: values.rolling(trial["baseline_weeks"]).mean())
    std = grouped.transform(lambda values: values.rolling(trial["baseline_weeks"]).std(ddof=0))
    z_score = (frame["net_share"] - mean) / std
    eligible = (
        z_score > trial["threshold"]
        if trial["interpretation"] == "ALIGNED_HIGH"
        else z_score < -trial["threshold"]
    )
    candidates: set[pd.Timestamp] = set()
    for row in frame[std.gt(0) & eligible].itertuples(index=False):
        if row.available_at >= spot.index[0]:
            index = int(spot.index.searchsorted(row.available_at, side="right"))
            if index < len(spot):
                candidates.add(spot.index[index])
    source_gaps: set[pd.Timestamp] = set()
    for row in frame.loc[~consecutive].iloc[1:].itertuples(index=False):
        if row.available_at >= spot.index[0]:
            index = int(spot.index.searchsorted(row.available_at, side="right"))
            if index < len(spot):
                source_gaps.add(spot.index[index])
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    scheduled: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (index > 0 and opened - spot.index[index - 1] != BAR) or opened in source_gaps
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = 1
            held = False
            scheduled = None
        if gap or held or was_held:
            continue
        if opened in candidates:
            entries[index] = 1
            held = True
            scheduled = opened + WEEK
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
            digest, buys, sells = signal_hash(spot, positioning, trial)
            segments[segment][name] = {
                "event_hash": digest,
                "buy_count": buys,
                "sell_count": sells,
            }
    payload = {"engine": "freqtrade", "version": freqtrade.__version__, "segments": segments}
    args.output.write_text(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
