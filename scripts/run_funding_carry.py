#!/usr/bin/env python3
"""Delta-neutral funding-rate carry across the pair universe + production G10 (DSR).

The first NON-PREDICTIVE strategy we test: instead of forecasting price, hold
long-spot / short-perp (delta-neutral) and collect the perpetual funding payment.
Being short the perp, our per-period return equals the funding rate (we receive it
when funding is positive, pay it when negative), while price risk cancels. A basket
across pairs diversifies; a selective filter only carries when trailing funding is
favorable, sidestepping negative-funding regimes (e.g. the 2022 bear).

This is why the research flagged it: it does not need the predictive edge our DSR
tests keep failing. Honest bar unchanged: DSR >= 0.95 over the config grid + sane
drawdown. RESEARCH-ONLY — trading it needs perps/margin (S4-gated); here we only
model the funding leg (price cancels in delta-neutral; basis risk is a noted ceiling).

ponytail: reads the raw funding zips directly + reuses the project DSR estimator.
Only the funding leg is modelled — basis/liquidation risk is a real-world ceiling.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from itertools import product
from math import sqrt
from pathlib import Path
from statistics import mean, pstdev

import pyarrow.csv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

RAW = ROOT / "data" / "raw" / "fundingRate"
OUT = ROOT / "artifacts" / "validation" / "funding_carry"
PPY = 3 * 365  # 8-hour funding periods per year
FEE = 0.0004  # round-trip cost of toggling a delta-neutral pair (both legs)
DSR_PASS = 0.95
THRESHOLDS = (0.0, 0.0001)  # min trailing funding to carry (per 8h)
LOOKBACKS = (9, 21, 63)  # periods for the trailing-funding filter
REBALANCES = (3, 9, 21)  # rebalance cadence in 8h periods (daily / 3-day / weekly)


def load_funding() -> tuple[list[int], dict[str, list[float | None]]]:
    """Funding rate per pair aligned to the union 8h-time index (None where absent)."""
    series: dict[str, dict[int, float]] = {}
    for pair_dir in sorted(RAW.glob("*")):
        if not pair_dir.is_dir():
            continue
        rows: dict[int, float] = {}
        for zp in sorted(pair_dir.glob("*.zip")):
            with zipfile.ZipFile(zp) as z:
                data = z.read(z.namelist()[0])
            table = pyarrow.csv.read_csv(io.BytesIO(data))
            times = table.column("calc_time").to_pylist()
            rates = table.column("last_funding_rate").to_pylist()
            for ts, rate in zip(times, rates, strict=True):
                rows[int(ts)] = float(rate)
        if len(rows) > 500:
            series[pair_dir.name] = rows
    all_times = sorted(set().union(*[set(s) for s in series.values()]))
    matrix = {p: [s.get(t) for t in all_times] for p, s in series.items()}
    return all_times, matrix


def backtest(
    matrix: dict[str, list[float | None]], threshold: float, lookback: int, rebalance: int
) -> list[float]:
    """Basket carry: hold pairs whose trailing-`lookback` mean funding exceeds
    `threshold`, rebalancing every `rebalance` periods (fees only at rebalance, on the
    fraction of the book actually swapped). Between rebalances, collect funding."""
    pairs = list(matrix)
    n = len(next(iter(matrix.values())))
    held: set[str] = set()
    strat = [0.0] * n
    for t in range(n):
        if t > 0 and held:
            got = [matrix[p][t] for p in held if matrix[p][t] is not None]
            strat[t] = sum(got) / len(got) if got else 0.0
        if t >= lookback and t % rebalance == 0:  # rebalance on cadence (no lookahead)
            new = set()
            for p in pairs:
                window = [matrix[p][t - k] for k in range(lookback) if matrix[p][t - k] is not None]
                if window and mean(window) > threshold:
                    new.add(p)
            if new != held:
                strat[t] -= FEE * len(new ^ held) / max(len(new | held), 1)
            held = new
    return strat


def _metrics(strat: list[float]) -> dict:
    equity = peak = 1.0
    max_dd = 0.0
    for r in strat:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    sd = pstdev(strat)
    sharpe_bar = mean(strat) / sd if sd > 0 else 0.0
    return {
        "sharpe_bar": sharpe_bar,
        "sharpe_ann": round(sharpe_bar * sqrt(PPY), 2),
        "ann_return_pct": round((equity ** (PPY / len(strat)) - 1) * 100, 1)
        if equity > 0
        else -100.0,
        "max_drawdown_pct": round(max_dd * 100, 1),
        "total_return_pct": round((equity - 1) * 100, 1),
        "bars": len(strat),
    }


def build_report() -> dict:
    times, matrix = load_funding()
    always_on = _metrics(backtest(matrix, threshold=-1.0, lookback=1, rebalance=21))
    trials = []
    for threshold, lookback, rebalance in product(THRESHOLDS, LOOKBACKS, REBALANCES):
        strat = backtest(matrix, threshold, lookback, rebalance)
        m = _metrics(strat)
        m.update(threshold=threshold, lookback=lookback, rebalance=rebalance, returns=strat)
        trials.append(m)
    sharpes = [t["sharpe_bar"] for t in trials]
    best = max(trials, key=lambda t: t["sharpe_bar"])
    ret = best["returns"]
    mr, sd = mean(ret), pstdev(ret)
    skew = (sum((r - mr) ** 3 for r in ret) / len(ret)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in ret) / len(ret)) / sd**4 if sd > 0 else 3.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best["sharpe_bar"],
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=len(trials),
        sample_count=best["bars"],
        skewness=skew,
        kurtosis=kurt,
    )
    keys = (
        "threshold",
        "lookback",
        "rebalance",
        "sharpe_ann",
        "ann_return_pct",
        "max_drawdown_pct",
    )
    return {
        "schema": "tios-funding-carry-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "tradeability": "RESEARCH_ONLY — needs perps/margin (S4-gated); funding leg only",
        "universe_pairs": len(matrix),
        "funding_periods": len(times),
        "always_on_basket": {
            k: always_on[k]
            for k in ("sharpe_ann", "ann_return_pct", "max_drawdown_pct", "total_return_pct")
        },
        "trials_searched": len(trials),
        "best_selective": {k: best[k] for k in (*keys, "total_return_pct")},
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "expected_max_noise_sharpe": round(dsr["expected_maximum_noise_sharpe"], 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "verdict_is_genuine": False,
            "note": "A PASS here is NOT a genuine validation. This models ONLY the funding "
            "leg; it omits basis divergence, liquidation, and execution/slippage — the "
            "dominant real risks. The smooth low-vol yield inflates Sharpe/DSR. The ~8-9% "
            "carry is real and literature-consistent, but honest validation needs "
            "perp-price/basis modelling, and trading needs perps/margin (S4-gated).",
        },
        "top_configs": [
            {k: t[k] for k in keys}
            for t in sorted(trials, key=lambda t: t["sharpe_bar"], reverse=True)[:5]
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "FUNDING_CARRY.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    a, b, g = report["always_on_basket"], report["best_selective"], report["g10_dsr"]
    print(
        f"universe: {report['universe_pairs']} pairs, {report['funding_periods']} funding periods"
    )
    print(
        f"always-on basket carry: Sharpe {a['sharpe_ann']}, ann {a['ann_return_pct']}%, "
        f"maxDD {a['max_drawdown_pct']}%"
    )
    print(
        f"best selective: Sharpe {b['sharpe_ann']} (thr={b['threshold']} lb={b['lookback']}) "
        f"ann {b['ann_return_pct']}% maxDD {b['max_drawdown_pct']}%"
    )
    print(f"G10 DSR: {g['dsr']}  (need >= {g['threshold']})  -> {g['verdict']}")


if __name__ == "__main__":
    main()
