"""Freqtrade-environment dataframe signal-conformance harness."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import freqtrade
import numpy as np
import pandas as pd

from engines.funding_pressure_data import load_funding, load_spot, trial_name

ROOT = Path(__file__).resolve().parents[2]
BAR = pd.Timedelta(hours=1)


def signal_hash(
    spot: pd.DataFrame, funding: pd.DataFrame, trial: dict[str, Any], start: pd.Timestamp
) -> tuple[str, int, int]:
    frame = funding.copy()
    frame["mean"] = frame["last_funding_rate"].rolling(trial["lookback"]).mean()
    if trial["polarity"] == "CONTINUATION":
        frame["eligible"] = frame["mean"] > trial["threshold"]
    else:
        frame["eligible"] = frame["mean"] < -trial["threshold"]
    frame = frame[frame["mean"].notna() & (frame["calc_time"] >= start)].copy()
    frame["date"] = frame["calc_time"].dt.floor("h") + BAR
    state = frame.drop_duplicates("date", keep="last").set_index("date")["eligible"]
    target = state.reindex(spot.index)
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    for index, opened in enumerate(spot.index):
        if index and opened - spot.index[index - 1] != BAR:
            if held:
                exits[index] = 1
                held = False
            continue
        value = target.iloc[index]
        if pd.notna(value) and bool(value) != held:
            (entries if bool(value) else exits)[index] = 1
            held = bool(value)
    digest = hashlib.sha256((entries + exits * 2).tobytes()).hexdigest()
    return digest, int(entries.sum()), int(exits.sum())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    spot_all = load_spot(ROOT / request["spot_path"])
    funding = load_funding(ROOT / request["funding_root"])
    segments = {}
    for segment, bounds in request["segments"].items():
        spot = spot_all.loc[bounds[0] : bounds[1]]
        segments[segment] = {}
        for trial in request["trials"]:
            name = trial_name(trial["polarity"], trial["lookback"], trial["threshold"])
            digest, buys, sells = signal_hash(spot, funding, trial, spot.index[0])
            segments[segment][name] = {"event_hash": digest, "buy_count": buys, "sell_count": sells}
    payload = {"engine": "freqtrade", "version": freqtrade.__version__, "segments": segments}
    args.output.write_text(json.dumps(payload, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
