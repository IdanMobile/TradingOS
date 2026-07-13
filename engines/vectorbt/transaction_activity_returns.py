"""Vectorbt accelerator for the frozen transaction-activity campaign."""

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

from engines.transaction_activity_data import load_activity, load_spot, trial_name  # noqa: E402

BAR = pd.Timedelta(hours=1)
DAY = pd.Timedelta(days=1)


def build_events(
    spot: pd.DataFrame,
    activity: pd.DataFrame,
    *,
    side: str,
    window: int,
    holding_days: int,
    signal_start: pd.Timestamp,
    delay_bars: int = 0,
) -> tuple[pd.Series, pd.Series]:
    frame = activity.copy()
    frame["group"] = frame["source_day"].diff().ne(DAY).cumsum()
    frame["log_count"] = np.log(frame["count"].astype("float64"))
    prior = frame.groupby("group", sort=False)["log_count"].shift(1)
    grouped = prior.groupby(frame["group"], sort=False)
    mean = grouped.transform(lambda values: values.rolling(window, min_periods=window).mean())
    std = grouped.transform(lambda values: values.rolling(window, min_periods=window).std(ddof=0))
    frame["z"] = (frame["log_count"] - mean) / std
    ready = std.notna() & std.gt(0)
    eligible = frame["z"].gt(1) if side == "HIGH" else frame["z"].lt(-1)
    candidates = {
        row.source_day + DAY * 2 + BAR * (1 + delay_bars)
        for row in frame[ready & eligible].itertuples(index=False)
        if row.source_day >= signal_start - DAY * 2
    }
    source_gap_exits = {
        left + DAY * 3 + BAR
        for left, right in zip(frame["source_day"], frame["source_day"].iloc[1:], strict=False)
        if right - left != DAY
    }
    entries = pd.Series(False, index=spot.index, dtype="bool")
    exits = pd.Series(False, index=spot.index, dtype="bool")
    held = False
    scheduled_exit: pd.Timestamp | None = None
    for index, opened in enumerate(spot.index):
        was_held = held
        spot_gap = index > 0 and opened - spot.index[index - 1] != BAR
        source_gap = opened in source_gap_exits
        due = scheduled_exit is not None and opened >= scheduled_exit
        if held and (spot_gap or source_gap or due):
            exits.iloc[index] = True
            held = False
            scheduled_exit = None
        if spot_gap or source_gap or held or was_held:
            continue
        if opened in candidates:
            entries.iloc[index] = True
            held = True
            scheduled_exit = opened + DAY * holding_days
    return entries, exits


def _hash_flags(entries: pd.Series, exits: pd.Series) -> str:
    values = entries.to_numpy(np.uint8) + exits.to_numpy(np.uint8) * 2
    return hashlib.sha256(values.tobytes()).hexdigest()


def _return_hash(values: pd.Series) -> str:
    canonical = np.round(values.to_numpy("float64"), 12).astype("<f8", copy=False)
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def evaluate(
    spot: pd.DataFrame,
    activity: pd.DataFrame,
    trial: dict[str, Any],
    fee: float,
    slippage_bps: float,
    delay_bars: int = 0,
) -> dict[str, Any]:
    entries, exits = build_events(
        spot,
        activity,
        side=trial["side"],
        window=trial["window"],
        holding_days=trial["holding_days"],
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
        "trial": trial_name(trial["side"], trial["window"], trial["holding_days"]),
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
    activity = load_activity(ROOT / request["activity_path"])
    results: dict[str, Any] = {}
    for segment, bounds in request["segments"].items():
        lower, upper = (pd.Timestamp(value) for value in bounds)
        lower = lower.tz_localize("UTC") if lower.tzinfo is None else lower.tz_convert("UTC")
        upper = upper.tz_localize("UTC") if upper.tzinfo is None else upper.tz_convert("UTC")
        spot = spot_all.loc[lower:upper]
        results[segment] = {}
        for scenario in request["scenarios"]:
            results[segment][scenario["name"]] = {
                trial_name(item["side"], item["window"], item["holding_days"]): evaluate(
                    spot, activity, item, scenario["fee"], scenario["slippage_bps"]
                )
                for item in request["trials"]
            }
    payload = {"engine": "vectorbt", "version": vbt.__version__, "segments": results}
    args.output.write_text(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
