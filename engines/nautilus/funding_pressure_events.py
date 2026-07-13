"""Nautilus-environment event-order conformance harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import nautilus_trader
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engines.funding_pressure_data import load_funding, load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)


def event_hash(
    spot: pd.DataFrame, funding: pd.DataFrame, trial: dict[str, Any], start: pd.Timestamp
) -> tuple[str, int, int]:
    rates: list[float] = []
    desired: dict[pd.Timestamp, bool] = {}
    for row in funding.itertuples(index=False):
        rates.append(float(row.last_funding_rate))
        if len(rates) < trial["lookback"] or row.calc_time < start:
            continue
        average = sum(rates[-trial["lookback"] :]) / trial["lookback"]
        eligible = (
            average > trial["threshold"]
            if trial["polarity"] == "CONTINUATION"
            else average < -trial["threshold"]
        )
        desired[row.calc_time.floor("h") + BAR] = eligible
    entries = np.zeros(len(spot), dtype=np.uint8)
    exits = np.zeros(len(spot), dtype=np.uint8)
    held = False
    previous: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        if previous is not None and opened - previous != BAR:
            if held:
                exits[index] = 1
                held = False
            previous = opened
            continue
        state = desired.get(opened)
        if state is not None and state != held:
            (entries if state else exits)[index] = 1
            held = state
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
    funding = load_funding(ROOT / request["funding_root"])
    segments = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = spot_all.loc[lower:upper]
        segments[segment] = {}
        for trial in request["trials"]:
            name = trial_name(trial["polarity"], trial["lookback"], trial["threshold"])
            digest, buys, sells = event_hash(spot, funding, trial, spot.index[0])
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
