"""Freqtrade-environment dataframe signal-conformance harness."""

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

from engines.transaction_activity_data import load_activity, load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
DAY = pd.Timedelta(days=1)


def signal_hash(
    spot: pd.DataFrame, activity: pd.DataFrame, trial: dict[str, Any], start: pd.Timestamp
) -> tuple[str, int, int]:
    frame = activity.copy()
    frame["group"] = frame["source_day"].diff().ne(DAY).cumsum()
    frame["log"] = np.log(frame["count"].astype("float64"))
    prior = frame.groupby("group")["log"].shift()
    grouped = prior.groupby(frame["group"])
    mean = grouped.transform(lambda values: values.rolling(trial["window"]).mean())
    std = grouped.transform(lambda values: values.rolling(trial["window"]).std(ddof=0))
    z_score = (frame["log"] - mean) / std
    eligible = z_score > 1 if trial["side"] == "HIGH" else z_score < -1
    candidates = set(
        frame.loc[std.gt(0) & eligible & (frame["source_day"] >= start - DAY * 2), "source_day"]
        + DAY * 2
        + BAR
    )
    gaps = {
        left + DAY * 3 + BAR
        for left, right in zip(frame["source_day"], frame["source_day"].iloc[1:], strict=False)
        if right - left != DAY
    }
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    scheduled: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (index > 0 and opened - spot.index[index - 1] != BAR) or opened in gaps
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits[index] = 1
            held = False
            scheduled = None
        if gap or held or was_held:
            continue
        if opened in candidates:
            entries[index] = 1
            held = True
            scheduled = opened + DAY * trial["holding_days"]
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
            digest, buys, sells = signal_hash(spot, activity, trial, spot.index[0])
            segments[segment][name] = {"event_hash": digest, "buy_count": buys, "sell_count": sells}
    payload = {"engine": "freqtrade", "version": freqtrade.__version__, "segments": segments}
    args.output.write_text(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
