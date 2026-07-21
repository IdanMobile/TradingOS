#!/usr/bin/env python3
"""Budgeted campaigns #2 and #3: MVRV dislocation and taker imbalance.

Both families come from canonical specs already registered with immutable identities
(SUP-010) and frozen data packages already byte-verified in-repo. Neither has ever faced
pre-registration, leak-proof splits, or hierarchy-wide deflation — that is what happens
here. Under D-108 each admission raises the bar for every family after it: these two
deflate against campaign #1's 36 trials plus their own.

Leak discipline, MVRV: the daily metric is published with a lag — the spec says a source
day's value is usable only after two further full UTC days. Each hourly row therefore
carries the latest *already-available* daily value, attached once up front; `evaluate`
reconstructs its daily history from the rows inside its own window and can never touch a
value the calendar hadn't released, in-window or out.

Costs: F1/S1 per campaign #1 — 0.1% fee + 1bp adverse slippage per side, next-open fills.

    python scripts/run_family_campaigns_v2.py
"""

from __future__ import annotations

import json
import math
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.validation.campaign import TrialScore, run_campaign  # noqa: E402
from tios.validation.splits import split_temporal  # noqa: E402

SPOT_PARQUET = ROOT / "data" / "normalized" / "BTCUSDT_1h.parquet"
MVRV_RAW = (
    ROOT
    / "data"
    / "raw"
    / "onchain"
    / "coinmetrics_btc_capmvrvcur_2020-07-01_2026-06-28_2026-07-13.json"
)
HOLDOUT_SEALED_UNTIL = datetime(2027, 1, 14, tzinfo=UTC)
FEE = 0.001
SLIP = 0.0001
HOUR = 3600.0

# Row layouts (plain tuples; picked apart positionally in the evaluators)
# taker: (open_epoch, open, quote_volume, taker_buy_quote)
# mvrv:  (open_epoch, open, avail_day_ordinal, avail_mvrv)


def load_spot() -> list[tuple[float, float, float, float, float]]:
    t = pq.read_table(
        SPOT_PARQUET,
        columns=["timestamp_open_utc", "open", "quote_volume", "taker_buy_quote_volume"],
    )
    ts = [v.timestamp() for v in t.column("timestamp_open_utc").to_pylist()]
    op = [float(v) for v in t.column("open").to_pylist()]
    qv = [float(v) for v in t.column("quote_volume").to_pylist()]
    tb = [float(v) for v in t.column("taker_buy_quote_volume").to_pylist()]
    return list(zip(ts, op, qv, tb, strict=True))


def _trade_return(entry_open: float, exit_open: float) -> float:
    entry = entry_open * (1 + SLIP) * (1 + FEE)
    exit_ = exit_open * (1 - SLIP) * (1 - FEE)
    return exit_ / entry - 1


def _per_bar_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / len(returns)
    return mean / math.sqrt(var) if var > 0 else 0.0


# ---------------------------------------------------------------- taker imbalance
def evaluate_taker(window: Sequence[tuple], params: dict[str, Any]) -> TrialScore:
    baseline = int(params["prior_baseline_hours"])
    z_thr = float(params["z_threshold"])
    hold_h = float(params["pulse_holding_hours"])
    reversal = params["interpretation"] == "REVERSAL_LOW"

    from collections import deque

    # Rolling baseline as sum/sumsq over a fixed-size deque: O(1) per bar. A naive
    # per-bar slice of a 720-hour baseline is ~5e9 ops across the grid.
    history: deque[float] = deque(maxlen=baseline)
    running_sum = 0.0
    running_sumsq = 0.0
    returns: list[float] = []
    trade_returns: list[float] = []
    bar_returns: list[float] = []
    held = False
    entry_price = 0.0
    entry_time = 0.0
    prev_ts = None

    def reset_baseline() -> None:
        nonlocal running_sum, running_sumsq
        history.clear()
        running_sum = running_sumsq = 0.0

    for i in range(len(window) - 1):
        marked = len(returns)
        ts, op, qv, tb = window[i][0], window[i][1], window[i][2], window[i][3]
        gap = prev_ts is not None and ts - prev_ts != HOUR
        prev_ts = ts

        if gap:
            reset_baseline()  # spec: a source gap resets warm-up
            if held:  # spec: gap exits held exposure at first observable open
                trade_returns.append(_trade_return(entry_price, op))
                returns.append(trade_returns[-1])
                held = False

        if qv <= 0 or tb < 0 or tb > qv:
            reset_baseline()
            bar_returns.append(returns[-1] if len(returns) > marked else 0.0)
            continue
        feature = 2 * tb / qv - 1

        if held and ts >= entry_time + hold_h * HOUR:
            trade_returns.append(_trade_return(entry_price, op))
            returns.append(trade_returns[-1])
            held = False

        if held:
            returns.append(0.0)  # mark bar, no realised return (campaign #1 convention)
        elif len(history) == baseline:
            mean = running_sum / baseline
            var = running_sumsq / baseline - mean * mean
            if var > 1e-18:
                z = (feature - mean) / math.sqrt(var)
                fired = z < -z_thr if reversal else z > z_thr
                if fired:
                    held = True
                    entry_price = window[i + 1][1]  # next open, strictly later
                    entry_time = window[i + 1][0]

        if len(history) == baseline:  # deque about to evict its oldest
            evicted = history[0]
            running_sum -= evicted
            running_sumsq -= evicted * evicted
        history.append(feature)
        running_sum += feature
        running_sumsq += feature * feature
        bar_returns.append(returns[-1] if len(returns) > marked else 0.0)
    return TrialScore(_per_bar_sharpe(returns), tuple(trade_returns), tuple(bar_returns))


# ---------------------------------------------------------------- MVRV dislocation
def attach_mvrv(
    spot: list[tuple], mvrv_raw: list[dict[str, Any]]
) -> list[tuple[float, float, int, float]]:
    """Attach the latest *available* daily value to each hourly bar, lag applied once."""
    daily = []
    for row in mvrv_raw:
        day = datetime.fromisoformat(row["time"].replace("Z", "+00:00"))
        # Source day D becomes usable after two further full UTC days => from D+3 00:00.
        available_at = day.timestamp() + 3 * 24 * HOUR
        daily.append((available_at, day.toordinal(), math.log(float(row["CapMVRVCur"]))))
    daily.sort()

    out = []
    j = -1
    for ts, op, _qv, _tb in spot:
        while j + 1 < len(daily) and daily[j + 1][0] <= ts:
            j += 1
        if j >= 0:
            out.append((ts, op, daily[j][1], daily[j][2]))
    return out


def evaluate_mvrv(window: Sequence[tuple], params: dict[str, Any]) -> TrialScore:
    z_window = int(params["prior_window_days"])
    z_thr = float(params["z_threshold"])
    hold_h = float(params["pulse_holding_hours"])
    low_side = params["side"] == "LOW"

    days: list[tuple[int, float]] = []  # (day_ordinal, log_mvrv) as they become available
    returns: list[float] = []
    trade_returns: list[float] = []
    bar_returns: list[float] = []
    held = False
    entry_price = 0.0
    entry_time = 0.0

    for i in range(len(window) - 1):
        marked = len(returns)
        ts, op, day_ord, log_mvrv = window[i]
        new_day = not days or day_ord > days[-1][0]

        if held and ts >= entry_time + hold_h * HOUR:
            trade_returns.append(_trade_return(entry_price, op))
            returns.append(trade_returns[-1])
            held = False

        if held:
            returns.append(0.0)  # mark bar (campaign #1 convention)

        if new_day:
            if days and day_ord - days[-1][0] > 1 and held:
                # spec: a missing source day exits held exposure once observable
                trade_returns.append(_trade_return(entry_price, op))
                returns.append(trade_returns[-1])
                held = False
            if len(days) >= z_window and not held:
                base = [v for _, v in days[-z_window:]]
                mean = sum(base) / z_window
                var = sum((v - mean) ** 2 for v in base) / z_window
                if var > 0:
                    z = (log_mvrv - mean) / math.sqrt(var)
                    fired = z < -z_thr if low_side else z > z_thr
                    if fired:
                        held = True
                        entry_price = window[i + 1][1]
                        entry_time = window[i + 1][0]
            days.append((day_ord, log_mvrv))
            if len(days) > 60:  # bound memory; > max 45d z-window
                del days[:-60]
        bar_returns.append(returns[-1] if len(returns) > marked else 0.0)
    return TrialScore(_per_bar_sharpe(returns), tuple(trade_returns), tuple(bar_returns))


# ---------------------------------------------------------------- runners
def _report(result: Any) -> None:
    print(f"  registration:  {result.registration_ref}")
    print(
        f"  trials family/hierarchy: {result.ledger_trials}/{result.hierarchy_trials} "
        f"across {result.admitted_families} families"
    )
    print(f"  selected:      {result.selected.parameters if result.selected else None}")
    if result.selected:
        print(f"  train sharpe:  {result.selected.train_score:+.6f}")
    print(f"  validation:    {result.validation_score:+.6f}")
    print(f"  val trades:    {result.validation_trades} (min {result.min_validation_trades})")
    if result.dsr:
        print(
            f"  noise bar:     {result.dsr['expected_maximum_noise_sharpe']:.6f}  "
            f"DSR: {result.dsr['dsr']:.4f}  (eff trials {result.effective_trials})"
        )
    if result.insufficient_activity:
        verdict = "INSUFFICIENT_ACTIVITY - too few completed trades to claim a DSR"
    elif result.dsr and result.dsr["dsr"] >= 0.95 and result.validation_score > 0:
        verdict = "PASS-ELIGIBLE (still requires G1-G11 + specialist review + prospective evidence)"
    else:
        verdict = "FAIL - does not clear the deflated bar"
    print(f"  VERDICT:       {verdict}")


def main() -> int:
    spot = load_spot()
    mvrv_raw = json.loads(MVRV_RAW.read_text())["data"]
    print(f"spot bars: {len(spot)} | mvrv days: {len(mvrv_raw)}")

    # Campaign #2 — taker imbalance (z of taker-buy share, continuation vs reversal)
    taker_grid = [
        {
            "prior_baseline_hours": b,
            "z_threshold": z,
            "pulse_holding_hours": h,
            "interpretation": interp,
        }
        for b in (24, 168, 720)
        for z in (1.0, 1.5, 2.0)
        for h in (6, 24)
        for interp in ("CONTINUATION_HIGH", "REVERSAL_LOW")
    ]
    split = split_temporal(
        spot,
        train_fraction=0.6,
        validation_fraction=0.2,
        gap_bars=800,
        sealed_until=HOLDOUT_SEALED_UNTIL,  # > max 720h warm-up
    )
    print(f"\nFAM-TAKER-IMBALANCE-V1  ({len(taker_grid)} trials, split {split.sizes()})")
    taker = run_campaign(
        ROOT,
        family="FAM-TAKER-IMBALANCE-V1",
        search_space={
            "prior_baseline_hours": [24, 168, 720],
            "z_threshold": [1.0, 1.5, 2.0],
            "pulse_holding_hours": [6, 24],
            "interpretation": ["CONTINUATION_HIGH", "REVERSAL_LOW"],
        },
        primary_endpoint="per_bar_sharpe_after_f1s1_costs",
        cost_model={
            "scenario": "F1/S1",
            "fee_rate_per_side": FEE,
            "slippage_rate_per_side": SLIP,
            "order_assumption": "MARKET_TAKER_AT_NEXT_OPEN_WITH_ADVERSE_SLIPPAGE",
        },
        chronology=f"BTCUSDT 1h normalized, {len(spot)} bars, 60/20/20 with 800-bar gaps",
        thresholds={"dsr_min": 0.95, "min_validation_trades": 10},
        stop_rules="no_rescue_on_fail; no widening after registration",
        split=split,
        parameter_grid=taker_grid,
        evaluate=evaluate_taker,
        fold_count=5,
    )
    _report(taker)

    # Campaign #3 — MVRV dislocation (daily on-chain valuation z, lag-honest)
    mvrv_rows = attach_mvrv(spot, mvrv_raw)
    mvrv_grid = [
        {
            "prior_window_days": w,
            "z_threshold": z,
            "side": side,
            "pulse_holding_hours": h,
        }
        for w in (20, 30, 45)
        for z in (1.0, 1.5, 2.0)
        for side in ("HIGH", "LOW")
        for h in (24, 168)
    ]
    split2 = split_temporal(
        mvrv_rows,
        train_fraction=0.6,
        validation_fraction=0.2,
        gap_bars=1200,
        sealed_until=HOLDOUT_SEALED_UNTIL,  # > 45d z-window + 3d lag
    )
    print(f"\nFAM-MVRV-DISLOCATION-V1  ({len(mvrv_grid)} trials, split {split2.sizes()})")
    mvrv = run_campaign(
        ROOT,
        family="FAM-MVRV-DISLOCATION-V1",
        search_space={
            "prior_window_days": [20, 30, 45],
            "z_threshold": [1.0, 1.5, 2.0],
            "side": ["HIGH", "LOW"],
            "pulse_holding_hours": [24, 168],
        },
        primary_endpoint="per_bar_sharpe_after_f1s1_costs",
        cost_model={
            "scenario": "F1/S1",
            "fee_rate_per_side": FEE,
            "slippage_rate_per_side": SLIP,
            "order_assumption": "MARKET_TAKER_AT_NEXT_OPEN_WITH_ADVERSE_SLIPPAGE",
            "metric_lag": "source day usable from D+3 00:00 UTC (spec availability lag)",
        },
        chronology=f"BTCUSDT 1h + CoinMetrics MVRV daily, {len(mvrv_rows)} joined rows, "
        "60/20/20 with 1200-bar gaps",
        thresholds={"dsr_min": 0.95, "min_validation_trades": 10},
        stop_rules="no_rescue_on_fail; no widening after registration",
        split=split2,
        parameter_grid=mvrv_grid,
        evaluate=evaluate_mvrv,
        fold_count=5,
    )
    _report(mvrv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
