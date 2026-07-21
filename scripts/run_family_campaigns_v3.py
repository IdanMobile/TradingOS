#!/usr/bin/env python3
"""Budgeted campaigns #4-#7: tx activity, cross-venue premium, CFTC positioning, funding.

Same discipline as campaigns #1-#3: pre-registered grids, train-only selection, per-trial
ledger, hierarchy-wide deflation, sealed holdout untouched. Each family's availability lag
is enforced structurally — every hourly row carries only values the calendar had already
released (tx: D+3 00:00 like MVRV; CFTC: report date + 8 calendar days; funding: exact
calc time; cross-venue: the bar's own recorded source close).

    python scripts/run_family_campaigns_v3.py
"""

from __future__ import annotations

import csv
import io
import json
import math
import sys
import zipfile
from collections import deque
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from tios.validation.campaign import TrialScore, run_campaign  # noqa: E402
from tios.validation.splits import split_temporal  # noqa: E402

SPOT_PARQUET = ROOT / "data" / "normalized" / "BTCUSDT_1h.parquet"
XVEN_PARQUET = ROOT / "data" / "normalized" / "cross_venue_btc_premium_1h_v1.parquet"
TX_RAW = ROOT / "data" / "raw" / "onchain" / "blockchain_info_n_transactions_6y_2026-07-13.json"
HOLDOUT_SEALED_UNTIL = datetime(2027, 1, 14, tzinfo=UTC)
FEE = 0.001
SLIP = 0.0001
HOUR = 3600.0
DAY = 86400.0


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


def load_spot_opens() -> list[tuple[float, float]]:
    t = pq.read_table(SPOT_PARQUET, columns=["timestamp_open_utc", "open"])
    ts = [v.timestamp() for v in t.column("timestamp_open_utc").to_pylist()]
    op = [float(v) for v in t.column("open").to_pylist()]
    return list(zip(ts, op, strict=True))


def attach_series(
    spot: list[tuple[float, float]], series: list[tuple[float, int, float]]
) -> list[tuple[float, float, int, float]]:
    """Attach the latest *available* (ordinal, value) to each hourly bar.

    `series` rows are (available_at_epoch, ordinal, value), sorted here. Rows before any
    value is available are dropped — evaluators must never see a placeholder.
    """
    series = sorted(series)
    out: list[tuple[float, float, int, float]] = []
    j = -1
    for ts, op in spot:
        while j + 1 < len(series) and series[j + 1][0] <= ts:
            j += 1
        if j >= 0:
            out.append((ts, op, series[j][1], series[j][2]))
    return out


def make_period_z_evaluator(max_ordinal_gap: int) -> Callable:
    """Pulse on a period series' z-score (daily or weekly), campaign #3 conventions.

    Params: window (periods), z_threshold, side HIGH|LOW, pulse_holding_hours.
    A source gap wider than `max_ordinal_gap` exits held exposure once observable.
    """

    def evaluate(window_rows: Sequence[tuple], params: dict[str, Any]) -> TrialScore:
        z_window = int(params["window"])
        z_thr = float(params["z_threshold"])
        hold_h = float(params["pulse_holding_hours"])
        low_side = params["side"] == "LOW"

        periods: list[tuple[int, float]] = []
        returns: list[float] = []
        trade_returns: list[float] = []
        bar_returns: list[float] = []
        held = False
        entry_price = entry_time = 0.0

        for i in range(len(window_rows) - 1):
            marked = len(returns)
            ts, op, ordinal, value = window_rows[i]
            new_period = not periods or ordinal > periods[-1][0]

            if held and ts >= entry_time + hold_h * HOUR:
                trade_returns.append(_trade_return(entry_price, op))
                returns.append(trade_returns[-1])
                held = False
            if held:
                returns.append(0.0)

            if new_period:
                if periods and ordinal - periods[-1][0] > max_ordinal_gap and held:
                    trade_returns.append(_trade_return(entry_price, op))
                    returns.append(trade_returns[-1])
                    held = False
                if len(periods) >= z_window and not held:
                    base = [v for _, v in periods[-z_window:]]
                    mean = sum(base) / z_window
                    var = sum((v - mean) ** 2 for v in base) / z_window
                    if var > 0:
                        z = (value - mean) / math.sqrt(var)
                        if (z < -z_thr) if low_side else (z > z_thr):
                            held = True
                            entry_price = window_rows[i + 1][1]
                            entry_time = window_rows[i + 1][0]
                periods.append((ordinal, value))
                if len(periods) > 60:
                    del periods[:-60]
            bar_returns.append(returns[-1] if len(returns) > marked else 0.0)
        return TrialScore(_per_bar_sharpe(returns), tuple(trade_returns), tuple(bar_returns))

    return evaluate


def evaluate_hourly_z(window_rows: Sequence[tuple], params: dict[str, Any]) -> TrialScore:
    """Hourly feature z pulse (campaign #2 conventions, rolling O(1) baseline).

    Rows: (ts, fill_open, feature). Params: prior_baseline_hours, z_threshold,
    pulse_holding_hours, interpretation CONTINUATION_POSITIVE|REVERSAL_NEGATIVE.
    """
    baseline = int(params["prior_baseline_hours"])
    z_thr = float(params["z_threshold"])
    hold_h = float(params["pulse_holding_hours"])
    reversal = params["interpretation"] == "REVERSAL_NEGATIVE"

    history: deque[float] = deque(maxlen=baseline)
    running_sum = running_sumsq = 0.0
    returns: list[float] = []
    trade_returns: list[float] = []
    bar_returns: list[float] = []
    held = False
    entry_price = entry_time = 0.0
    prev_ts = None

    for i in range(len(window_rows) - 1):
        marked = len(returns)
        ts, op, feature = window_rows[i]
        gap = prev_ts is not None and ts - prev_ts != HOUR
        prev_ts = ts
        if gap:
            history.clear()
            running_sum = running_sumsq = 0.0
            if held:
                trade_returns.append(_trade_return(entry_price, op))
                returns.append(trade_returns[-1])
                held = False

        if held and ts >= entry_time + hold_h * HOUR:
            trade_returns.append(_trade_return(entry_price, op))
            returns.append(trade_returns[-1])
            held = False
        if held:
            returns.append(0.0)
        elif len(history) == baseline:
            mean = running_sum / baseline
            var = running_sumsq / baseline - mean * mean
            if var > 1e-24:
                z = (feature - mean) / math.sqrt(var)
                if (z < -z_thr) if reversal else (z > z_thr):
                    held = True
                    entry_price = window_rows[i + 1][1]
                    entry_time = window_rows[i + 1][0]

        if len(history) == baseline:
            evicted = history[0]
            running_sum -= evicted
            running_sumsq -= evicted * evicted
        history.append(feature)
        running_sum += feature
        running_sumsq += feature * feature
        bar_returns.append(returns[-1] if len(returns) > marked else 0.0)
    return TrialScore(_per_bar_sharpe(returns), tuple(trade_returns), tuple(bar_returns))


def evaluate_funding(window_rows: Sequence[tuple], params: dict[str, Any]) -> TrialScore:
    """Funding regime rule: long while the mean of the last N observations clears the
    threshold under the chosen polarity, cash otherwise. Rows: (ts, open, obs_idx, rate).
    """
    lookback = int(params["lookback_observations"])
    threshold = float(params["absolute_mean_rate_threshold"])
    contrarian = params["polarity"] == "CONTRARIAN"

    rates: deque[float] = deque(maxlen=lookback)
    last_idx = -1
    returns: list[float] = []
    trade_returns: list[float] = []
    bar_returns: list[float] = []
    held = False
    entry_price = 0.0

    for i in range(len(window_rows) - 1):
        marked = len(returns)
        _ts, op, obs_idx, rate = window_rows[i]
        if obs_idx > last_idx:
            rates.append(rate)
            last_idx = obs_idx

        eligible = False
        if len(rates) == lookback:
            mean = sum(rates) / lookback
            eligible = (mean < -threshold) if contrarian else (mean > threshold)

        if held and not eligible:
            trade_returns.append(_trade_return(entry_price, op))
            returns.append(trade_returns[-1])
            held = False
        elif held:
            returns.append(0.0)
        elif eligible:
            held = True
            entry_price = window_rows[i + 1][1]
        bar_returns.append(returns[-1] if len(returns) > marked else 0.0)
    return TrialScore(_per_bar_sharpe(returns), tuple(trade_returns), tuple(bar_returns))


# ---------------------------------------------------------------- data loaders
def tx_series() -> list[tuple[float, int, float]]:
    values = json.loads(TX_RAW.read_text())["values"]
    out = []
    for row in values:
        day_epoch = float(row["x"])
        count = float(row["y"])
        if count > 0:
            # Spec lag: source day usable after two further full UTC days => D+3 00:00.
            out.append((day_epoch + 3 * DAY, int(day_epoch // DAY), math.log(count)))
    return out


def cftc_series() -> list[tuple[float, int, float]]:
    import verify_cftc_btc_positioning_data as cftc

    pkg = cftc.load_package()
    feature = pkg["cftc_feature"]
    csv_bytes = cftc.decode_source(feature["sources"][0], ROOT)
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    out = []
    for row in rows:
        report = datetime.fromisoformat(row["report_date_as_yyyy_mm_dd"][:10]).replace(tzinfo=UTC)
        oi = float(row["open_interest_all"])
        if oi <= 0:
            continue
        share = (
            float(row["noncomm_positions_long_all"]) - float(row["noncomm_positions_short_all"])
        ) / oi
        # Package availability rule: report date plus 8 calendar days at 00:00 UTC.
        out.append((report.timestamp() + 8 * DAY, int(report.timestamp() // DAY), share))
    return out


def funding_series() -> list[tuple[float, int, float]]:
    import verify_funding_pressure_data as fund

    pkg = fund.load_package()
    feature = pkg["funding_feature"]
    raw_root = ROOT / feature["raw_root"]
    out = []
    idx = 0
    for path in sorted(raw_root.glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            member = archive.namelist()[0]
            text = archive.read(member).decode("utf-8")
        for row in csv.DictReader(io.StringIO(text)):
            calc_ms = float(row["calc_time"])
            rate = float(row["last_funding_rate"])
            out.append((calc_ms / 1000.0, idx, rate))  # available at exact calc time
            idx += 1
    return out


def xven_rows() -> list[tuple[float, float, float]]:
    t = pq.read_table(
        XVEN_PARQUET, columns=["timestamp_open_utc", "binance_btcusdt_open", "log_premium"]
    )
    ts = [v.timestamp() for v in t.column("timestamp_open_utc").to_pylist()]
    op = [float(v) for v in t.column("binance_btcusdt_open").to_pylist()]
    lp = [float(v) for v in t.column("log_premium").to_pylist()]
    return [(a, b, c) for a, b, c in zip(ts, op, lp, strict=True) if not math.isnan(c)]


# ---------------------------------------------------------------- run
def _report(result: Any) -> str:
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
    print(f"  VERDICT:       {verdict}\n")
    return verdict


COMMON = {
    "primary_endpoint": "per_bar_sharpe_after_f1s1_costs",
    # PBO is not computed on this path (D-112, F3a): declaring an unenforced pbo_max is worse
    # than omitting it. Only controls this runner enforces are pre-registered.
    "thresholds": {"dsr_min": 0.95, "min_validation_trades": 10},
    "stop_rules": "no_rescue_on_fail; no widening after registration",
}
COSTS = {
    "scenario": "F1/S1",
    "fee_rate_per_side": FEE,
    "slippage_rate_per_side": SLIP,
    "order_assumption": "MARKET_TAKER_AT_NEXT_OPEN_WITH_ADVERSE_SLIPPAGE",
}


def main() -> int:
    spot = load_spot_opens()
    print(f"spot bars: {len(spot)}")

    campaigns = []

    # #4 tx activity (daily on-chain, D+3 lag)
    tx_rows = attach_series(spot, tx_series())
    tx_grid = [
        {"window": w, "z_threshold": z, "side": s, "pulse_holding_hours": h}
        for w in (7, 14, 30)
        for z in (1.0, 1.5, 2.0)
        for s in ("HIGH", "LOW")
        for h in (24, 168)
    ]
    campaigns.append(
        (
            "FAM-TX-ACTIVITY-V1",
            tx_rows,
            tx_grid,
            make_period_z_evaluator(max_ordinal_gap=1),
            1200,
            {
                "window": [7, 14, 30],
                "z_threshold": [1.0, 1.5, 2.0],
                "side": ["HIGH", "LOW"],
                "pulse_holding_hours": [24, 168],
            },
            f"BTCUSDT 1h + blockchain.info daily tx count, {len(tx_rows)} joined rows",
            {"metric_lag": "source day usable from D+3 00:00 UTC"},
        )
    )

    # #5 cross-venue premium (hourly log premium)
    xv = xven_rows()
    xv_grid = [
        {
            "prior_baseline_hours": b,
            "z_threshold": z,
            "pulse_holding_hours": h,
            "interpretation": it,
        }
        for b in (24, 168, 720)
        for z in (1.0, 1.5, 2.0)
        for h in (6, 24)
        for it in ("CONTINUATION_POSITIVE", "REVERSAL_NEGATIVE")
    ]
    campaigns.append(
        (
            "FAM-CROSS-VENUE-PREMIUM-V1",
            xv,
            xv_grid,
            evaluate_hourly_z,
            800,
            {
                "prior_baseline_hours": [24, 168, 720],
                "z_threshold": [1.0, 1.5, 2.0],
                "pulse_holding_hours": [6, 24],
                "interpretation": ["CONTINUATION_POSITIVE", "REVERSAL_NEGATIVE"],
            },
            f"Coinbase-implied vs Binance BTCUSDT log premium 1h, {len(xv)} rows",
            {},
        )
    )

    # #6 CFTC positioning (weekly, report+8d availability)
    cftc_rows = attach_series(spot, cftc_series())
    cftc_grid = [
        {"window": w, "z_threshold": z, "side": s, "pulse_holding_hours": h}
        for w in (13, 26, 52)
        for z in (0.5, 1.0, 1.5)
        for s in ("HIGH", "LOW")
        for h in (168, 672)
    ]
    campaigns.append(
        (
            "FAM-CFTC-POSITIONING-V1",
            cftc_rows,
            cftc_grid,
            make_period_z_evaluator(max_ordinal_gap=21),  # weekly cadence, exceptions tolerated
            2000,  # > 52w of weekly values cannot fit a gap; bound instead by warm-up realism
            {
                "window": [13, 26, 52],
                "z_threshold": [0.5, 1.0, 1.5],
                "side": ["HIGH", "LOW"],
                "pulse_holding_hours": [168, 672],
            },
            f"BTCUSDT 1h + CFTC weekly noncommercial net share, {len(cftc_rows)} joined rows",
            {"metric_lag": "report date + 8 calendar days at 00:00 UTC"},
        )
    )

    # #7 funding pressure (regime rule on last-N funding mean)
    fund_rows = attach_series(spot, funding_series())
    fund_grid = [
        {"lookback_observations": n, "absolute_mean_rate_threshold": t, "polarity": p}
        for n in (1, 3, 6)
        for t in (0.0, 0.0001, 0.0003)
        for p in ("CONTINUATION", "CONTRARIAN")
    ]
    campaigns.append(
        (
            "FAM-FUNDING-PRESSURE-V1",
            fund_rows,
            fund_grid,
            evaluate_funding,
            800,
            {
                "lookback_observations": [1, 3, 6],
                "absolute_mean_rate_threshold": [0.0, 0.0001, 0.0003],
                "polarity": ["CONTINUATION", "CONTRARIAN"],
            },
            f"BTCUSDT 1h + Binance 8h funding observations, {len(fund_rows)} joined rows",
            {"metric_lag": "exact calc time (EXACT_CALC_TIME_MS)"},
        )
    )

    verdicts = {}
    for family, rows, grid, evaluate, gap_bars, space, chronology, extra_cost in campaigns:
        split = split_temporal(
            rows,
            train_fraction=0.6,
            validation_fraction=0.2,
            gap_bars=gap_bars,
            sealed_until=HOLDOUT_SEALED_UNTIL,
        )
        print(f"{family}  ({len(grid)} trials, split {split.sizes()})")
        result = run_campaign(
            ROOT,
            family=family,
            search_space=space,
            cost_model={**COSTS, **extra_cost},
            chronology=chronology + ", 60/20/20 chronological with boundary gaps",
            split=split,
            parameter_grid=grid,
            evaluate=evaluate,
            fold_count=5,
            **COMMON,
        )
        verdicts[family] = _report(result)

    print(json.dumps(verdicts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
