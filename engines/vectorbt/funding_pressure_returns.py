"""Vectorbt accelerator for the frozen funding-pressure campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engines.funding_pressure_data import load_funding, load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)


def build_events(
    spot: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    polarity: str,
    lookback: int,
    threshold: float,
    signal_start: pd.Timestamp,
    delay_bars: int = 0,
) -> tuple[pd.Series, pd.Series]:
    average = funding["last_funding_rate"].rolling(lookback, min_periods=lookback).mean()
    eligible = average > threshold if polarity == "CONTINUATION" else average < -threshold
    desired: dict[pd.Timestamp, bool] = {}
    for observed, value, ready in zip(funding["calc_time"], eligible, average.notna(), strict=True):
        if not ready or observed < signal_start:
            continue
        expected = observed.floor("h") + BAR * (1 + delay_bars)
        if expected in spot.index:
            desired[expected] = bool(value)
    entries = pd.Series(False, index=spot.index, dtype="bool")
    exits = pd.Series(False, index=spot.index, dtype="bool")
    held = False
    for index, opened in enumerate(spot.index):
        if index and opened - spot.index[index - 1] != BAR:
            if held:
                exits.iloc[index] = True
                held = False
            continue
        state = desired.get(opened)
        if state is True and not held:
            entries.iloc[index] = True
            held = True
        elif state is False and held:
            exits.iloc[index] = True
            held = False
    return entries, exits


def _hash_flags(entries: pd.Series, exits: pd.Series) -> str:
    values = entries.to_numpy(np.uint8) + exits.to_numpy(np.uint8) * 2
    return hashlib.sha256(values.tobytes()).hexdigest()


def _return_hash(values: pd.Series) -> str:
    canonical = np.round(values.to_numpy("float64"), 12).astype("<f8", copy=False)
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def evaluate(
    spot: pd.DataFrame,
    funding: pd.DataFrame,
    trial: dict[str, Any],
    fee: float,
    slippage_bps: float,
    delay_bars: int = 0,
) -> dict[str, Any]:
    entries, exits = build_events(
        spot,
        funding,
        polarity=trial["polarity"],
        lookback=trial["lookback"],
        threshold=trial["threshold"],
        signal_start=spot.index[0],
        delay_bars=delay_bars,
    )
    portfolio = vbt.Portfolio.from_signals(
        spot["close"],
        entries,
        exits,
        price=spot["open"],
        fees=fee,
        slippage=slippage_bps / 10_000,
        init_cash=1000.0,
        direction="longonly",
        accumulate=False,
        freq=BAR,
    )
    returns = pd.Series(portfolio.returns(), index=spot.index)
    deviation = float(returns.std(ddof=1))
    sides = portfolio.orders.records_readable["Side"].value_counts()
    return {
        "trial": trial_name(trial["polarity"], trial["lookback"], trial["threshold"]),
        "total_return": float(portfolio.total_return()),
        "sharpe_per_bar": float(returns.mean()) / deviation if deviation > 0 else 0.0,
        "max_drawdown": float(
            ((1 + returns).cumprod() / (1 + returns).cumprod().cummax() - 1).min()
        ),
        "buy_count": int(sides.get("Buy", 0)),
        "sell_count": int(sides.get("Sell", 0)),
        "event_hash": _hash_flags(entries, exits),
        "return_hash_12dp": _return_hash(returns),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    spot_all = load_spot(ROOT / request["spot_path"])
    funding = load_funding(ROOT / request["funding_root"])
    results: dict[str, Any] = {}
    for segment, bounds in request["segments"].items():
        spot = spot_all.loc[bounds[0] : bounds[1]]
        results[segment] = {}
        for scenario in request["scenarios"]:
            results[segment][scenario["name"]] = {
                trial_name(item["polarity"], item["lookback"], item["threshold"]): evaluate(
                    spot, funding, item, scenario["fee"], scenario["slippage_bps"]
                )
                for item in request["trials"]
            }
    payload = {"engine": "vectorbt", "version": vbt.__version__, "segments": results}
    args.output.write_text(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
