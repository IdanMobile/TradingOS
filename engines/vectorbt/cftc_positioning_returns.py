"""Vectorbt accelerator for the frozen CFTC-positioning campaign."""

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

from engines.cftc_positioning_data import (  # noqa: E402
    load_positioning,
    load_spot,
    trial_name,
)

BAR = pd.Timedelta(hours=1)
WEEK = pd.Timedelta(days=7)


def _consecutive(delta: pd.Series) -> pd.Series:
    return delta.between(pd.Timedelta(days=6), pd.Timedelta(days=8))


def build_events(
    spot: pd.DataFrame,
    positioning: pd.DataFrame,
    *,
    interpretation: str,
    baseline_weeks: int,
    threshold: float,
    delay_bars: int = 0,
) -> tuple[pd.Series, pd.Series]:
    frame = positioning.copy()
    frame["group"] = (~_consecutive(frame["report_date"].diff())).cumsum()
    prior = frame.groupby("group", sort=False)["net_share"].shift(1)
    grouped = prior.groupby(frame["group"], sort=False)
    mean = grouped.transform(
        lambda values: values.rolling(baseline_weeks, min_periods=baseline_weeks).mean()
    )
    std = grouped.transform(
        lambda values: values.rolling(baseline_weeks, min_periods=baseline_weeks).std(ddof=0)
    )
    z_score = (frame["net_share"] - mean) / std
    eligible = z_score.gt(threshold) if interpretation == "ALIGNED_HIGH" else z_score.lt(-threshold)
    candidates: dict[pd.Timestamp, pd.Timestamp] = {}
    for row in frame[std.gt(0) & eligible].itertuples(index=False):
        if row.available_at < spot.index[0]:
            continue
        index = int(spot.index.searchsorted(row.available_at, side="right")) + delay_bars
        if index < len(spot):
            candidates[spot.index[index]] = row.report_date
    source_gaps: set[pd.Timestamp] = set()
    for row in (
        frame.loc[~_consecutive(frame["report_date"].diff())].iloc[1:].itertuples(index=False)
    ):
        if row.available_at >= spot.index[0]:
            index = int(spot.index.searchsorted(row.available_at, side="right"))
            if index < len(spot):
                source_gaps.add(spot.index[index])
    entries = pd.Series(False, index=spot.index, dtype="bool")
    exits = pd.Series(False, index=spot.index, dtype="bool")
    held = False
    scheduled: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        gap = (index > 0 and opened - spot.index[index - 1] != BAR) or opened in source_gaps
        if held and (gap or (scheduled is not None and opened >= scheduled)):
            exits.iloc[index] = True
            held = False
            scheduled = None
        if gap or held or was_held:
            continue
        if opened in candidates:
            entries.iloc[index] = True
            held = True
            scheduled = opened + WEEK
    return entries, exits


def _hash_flags(entries: pd.Series, exits: pd.Series) -> str:
    values = entries.to_numpy(np.uint8) + exits.to_numpy(np.uint8) * 2
    return hashlib.sha256(values.tobytes()).hexdigest()


def _return_hash(values: pd.Series) -> str:
    canonical = np.round(values.to_numpy("float64"), 12).astype("<f8", copy=False)
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def evaluate(
    spot: pd.DataFrame,
    positioning: pd.DataFrame,
    trial: dict[str, Any],
    fee: float,
    slippage_bps: float,
) -> dict[str, Any]:
    entries, exits = build_events(
        spot,
        positioning,
        interpretation=trial["interpretation"],
        baseline_weeks=trial["baseline_weeks"],
        threshold=trial["threshold"],
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
        "trial": trial_name(trial["interpretation"], trial["baseline_weeks"], trial["threshold"]),
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
    spot_all = load_spot(ROOT, request["package_path"])
    positioning = load_positioning(ROOT, request["package_path"])
    results: dict[str, Any] = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = spot_all.loc[lower:upper]
        results[segment] = {}
        for scenario in request["scenarios"]:
            results[segment][scenario["name"]] = {
                trial_name(
                    item["interpretation"], item["baseline_weeks"], item["threshold"]
                ): evaluate(spot, positioning, item, scenario["fee"], scenario["slippage_bps"])
                for item in request["trials"]
            }
    payload = {"engine": "vectorbt", "version": vbt.__version__, "segments": results}
    args.output.write_text(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
