#!/usr/bin/env python3
"""Statistical-arbitrage pairs trading (mean-reverting spread) + production G10 (DSR).

A market-neutral strategy — the family the 2025 research says actually works in crypto
(dollar-neutral ~31% industry benchmark, stat-arb BTC-ETH Sharpe ~2.2, drawdowns <1%).
For an a-priori set of economically-related large-cap pairs, trade the log-price spread:
when it stretches beyond +/- entry_z it is expected to revert, so short/long the spread
and exit near the mean. Market-neutral (long one / short the other).

Pair set is CURATED (not all-combos) to keep multiple testing honest. RESEARCH-ONLY:
the short leg needs perps/margin (S4-gated); modelled here are spread P&L + turnover
fees (short-borrow/funding cost is a noted ceiling). Honest bar: DSR >= 0.95. Float
math for statistics; execution_authority=NONE.

ponytail: reuses the daily loader + DSR estimator; adds the spread/z-score engine.
"""

from __future__ import annotations

import json
import sys
from itertools import product
from math import log, sqrt
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import scripts.run_cross_sectional_momentum as xs  # noqa: E402
from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

OUT = ROOT / "artifacts" / "validation" / "stat_arb"
PPY = 365
FEE = 0.002  # round-trip both legs of the spread
DSR_PASS = 0.95
WINDOWS = (30, 60)
ENTRY_ZS = (2.0, 2.5)
EXIT_Z = 0.5
# Economically-related large caps (a-priori pairs, not data-mined combinations).
PAIRS = (
    ("ETHUSDT", "BTCUSDT"), ("BNBUSDT", "BTCUSDT"), ("BNBUSDT", "ETHUSDT"),
    ("LTCUSDT", "BTCUSDT"), ("ETHUSDT", "SOLUSDT"), ("LINKUSDT", "ETHUSDT"),
    ("DOTUSDT", "ETHUSDT"), ("AVAXUSDT", "SOLUSDT"), ("XRPUSDT", "XLMUSDT"),
    ("ADAUSDT", "DOTUSDT"),
)  # fmt: skip


def _spread(pa: list[float | None], pb: list[float | None]) -> list[float | None]:
    return [
        log(a / b) if a is not None and b is not None and a > 0 and b > 0 else None
        for a, b in zip(pa, pb, strict=True)
    ]


def backtest(
    pa: list[float | None], pb: list[float | None], window: int, entry_z: float
) -> tuple[list[float], int]:
    """Trade the mean-reverting log spread; +1 long / -1 short / 0 flat. -> (returns, trades)."""
    spread = _spread(pa, pb)
    n = len(spread)
    strat = [0.0] * n
    pos = 0
    trades = 0
    for t in range(n):
        if t > 0 and pos != 0 and spread[t] is not None and spread[t - 1] is not None:
            strat[t] = pos * (spread[t] - spread[t - 1])  # long spread profits when it rises
        window_vals = [
            spread[t - k] for k in range(1, window + 1) if t - k >= 0 and spread[t - k] is not None
        ]
        if spread[t] is not None and len(window_vals) >= window // 2:
            mu, sd = mean(window_vals), pstdev(window_vals)
            if sd > 0:
                z = (spread[t] - mu) / sd
                new = pos
                if pos == 0:
                    new = -1 if z > entry_z else (1 if z < -entry_z else 0)
                elif abs(z) < EXIT_Z:
                    new = 0
                if new != pos:
                    strat[t] -= FEE * abs(new - pos)
                    trades += 1
                    pos = new
    return strat, trades


def _metrics(strat: list[float], trades: int) -> dict:
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
        "trades": trades,
        "bars": len(strat),
    }


def build_report() -> dict:
    _, prices = xs.load_daily()
    trials = []
    for (a, b), window, entry_z in product(PAIRS, WINDOWS, ENTRY_ZS):
        if a not in prices or b not in prices:
            continue
        strat, trades = backtest(prices[a], prices[b], window, entry_z)
        m = _metrics(strat, trades)
        if m["trades"] < 10:
            continue
        m.update(pair=f"{a}/{b}", window=window, entry_z=entry_z)
        trials.append((m, strat))
    if not trials:
        return {"schema": "tios-stat-arb-v1", "error": "no trials"}
    sharpes = [m["sharpe_bar"] for m, _ in trials]
    best_m, best_ret = max(trials, key=lambda x: x[0]["sharpe_bar"])
    mr, sd = mean(best_ret), pstdev(best_ret)
    skew = (sum((r - mr) ** 3 for r in best_ret) / len(best_ret)) / sd**3 if sd > 0 else 0.0
    kurt = (sum((r - mr) ** 4 for r in best_ret) / len(best_ret)) / sd**4 if sd > 0 else 3.0
    dsr = deflated_sharpe_ratio(
        observed_sharpe=best_m["sharpe_bar"],
        sharpe_variance=sharpe_variance_from_trials(sharpes),
        independent_trials=len(trials),
        sample_count=best_m["bars"],
        skewness=skew,
        kurtosis=kurt,
    )
    keys = (
        "pair",
        "window",
        "entry_z",
        "sharpe_ann",
        "ann_return_pct",
        "max_drawdown_pct",
        "trades",
    )
    return {
        "schema": "tios-stat-arb-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "tradeability": "RESEARCH_ONLY — short leg needs perps/margin (S4-gated)",
        "trials_searched": len(trials),
        "best": {k: best_m[k] for k in (*keys, "total_return_pct")},
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "expected_max_noise_sharpe": round(dsr["expected_maximum_noise_sharpe"], 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "note": "PASS still requires RG-07 review; models spread P&L + fees, not "
            "short-borrow/funding cost or execution slippage.",
        },
        "top_configs": [
            {k: m[k] for k in keys}
            for m, _ in sorted(trials, key=lambda x: x[0]["sharpe_bar"], reverse=True)[:6]
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "STAT_ARB.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if "error" in report:
        print(report)
        return
    b, g = report["best"], report["g10_dsr"]
    print(f"trials: {report['trials_searched']} (curated pairs)")
    print(
        f"best: {b['pair']} w={b['window']} z={b['entry_z']} | Sharpe {b['sharpe_ann']} "
        f"ann {b['ann_return_pct']}% maxDD {b['max_drawdown_pct']}% {b['trades']} trades"
    )
    print(f"G10 DSR: {g['dsr']} (need >= {g['threshold']}) -> {g['verdict']}")


if __name__ == "__main__":
    main()
