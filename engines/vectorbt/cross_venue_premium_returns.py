"""Vectorbt accelerator for the frozen D-075 campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
import vectorbt as vbt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engines.cross_venue_premium_data import load_cross_venue, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
PULSE = pd.Timedelta(hours=6)


def build_events(
    spot: pd.DataFrame,
    source: pd.DataFrame,
    *,
    interpretation: str,
    baseline_hours: int,
    threshold: float,
    delay_bars: int = 0,
) -> tuple[pd.Series, pd.Series]:
    frame = source.copy()
    consecutive = frame["timestamp_open_utc"].diff().eq(BAR)
    group = (~consecutive).cumsum()
    prior = frame["log_premium"].groupby(group).shift()
    grouped = prior.groupby(group)
    mean = grouped.transform(lambda value: value.rolling(baseline_hours).mean())
    std = grouped.transform(lambda value: value.rolling(baseline_hours).std(ddof=0))
    z_score = (frame["log_premium"] - mean) / std
    eligible = (
        z_score.gt(threshold)
        if interpretation == "CONTINUATION_POSITIVE"
        else z_score.lt(-threshold)
    )
    candidates: set[pd.Timestamp] = set()
    for row in frame[std.gt(0) & eligible].itertuples(index=False):
        if row.source_close_utc < spot.index[0]:
            continue
        mapped = int(spot.index.searchsorted(row.source_close_utc, side="right")) + delay_bars
        if mapped < len(spot):
            candidates.add(spot.index[mapped])
    interruptions = {
        spot.index[mapped]
        for row in frame[~consecutive].itertuples(index=False)
        if (mapped := int(spot.index.searchsorted(row.source_close_utc, side="right"))) < len(spot)
    }
    entries = pd.Series(False, index=spot.index, dtype="bool")
    exits = pd.Series(False, index=spot.index, dtype="bool")
    held = False
    scheduled: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (index > 0 and opened - spot.index[index - 1] != BAR) or opened in interruptions
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits.iloc[index] = True
            held = False
            scheduled = None
        if not (gap or held or was_held) and opened in candidates:
            entries.iloc[index] = True
            held = True
            scheduled = opened + PULSE
    return entries, exits


def _hash_flags(entries: pd.Series, exits: pd.Series) -> str:
    values = entries.to_numpy(np.uint8) + exits.to_numpy(np.uint8) * 2
    return hashlib.sha256(values.tobytes()).hexdigest()


def _return_hash(values: pd.Series) -> str:
    canonical = np.round(values.to_numpy("float64"), 12).astype("<f8", copy=False)
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def evaluate(
    spot: pd.DataFrame, source: pd.DataFrame, trial: dict[str, Any], fee: float, slippage_bps: float
) -> dict[str, Any]:
    entries, exits = build_events(
        spot,
        source,
        interpretation=trial["interpretation"],
        baseline_hours=trial["baseline_hours"],
        threshold=trial["threshold"],
    )
    portfolio = vbt.Portfolio.from_signals(
        spot["binance_btcusdt_close"],
        entries,
        exits,
        price=spot["binance_btcusdt_open"],
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
    equity = (1 + returns).cumprod()
    return {
        "trial": trial_name(trial["interpretation"], trial["baseline_hours"], trial["threshold"]),
        "total_return": float(portfolio.total_return()),
        "sharpe_per_bar": float(returns.mean()) / deviation if deviation > 0 else 0.0,
        "max_drawdown": float((equity / equity.cummax() - 1).min()),
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
    source = load_cross_venue(ROOT, request["package_path"])
    results: dict[str, Any] = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = source.loc[lower:upper]
        results[segment] = {}
        for scenario in request["scenarios"]:
            results[segment][scenario["name"]] = {
                trial_name(
                    item["interpretation"], item["baseline_hours"], item["threshold"]
                ): evaluate(spot, source, item, scenario["fee"], scenario["slippage_bps"])
                for item in request["trials"]
            }
    args.output.write_text(
        json.dumps(
            {"engine": "vectorbt", "version": vbt.__version__, "segments": results},
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
