#!/usr/bin/env python3
"""Professional statistical-arbitrage pairs trading + production G10 (DSR).

The naive daily version (`run_stat_arb_pairs.py`) failed at DSR 0.15 for three fixable
reasons: (1) it traded EVERY curated pair whether or not the spread actually mean-reverts,
(2) it assumed a fixed 1:1 log spread, and (3) it ran daily. This professional version:

  1. COINTEGRATION GATE (Engle-Granger, in-sample only): OLS hedge ratio beta of
     log(A) on log(B), then a Dickey-Fuller t-stat on the residual. Only pairs whose
     IN-SAMPLE residual is stationary (t < DF_CRIT) are eligible — trading a
     non-cointegrated spread is trading a random walk.
  2. ESTIMATED HEDGE RATIO: spread = log(A) - beta*log(B) - alpha (beta from in-sample
     OLS), so the spread is genuinely beta-neutral, not 1:1.
  3. OUT-OF-SAMPLE-ONLY evaluation + DSR: pairs are selected on in-sample, the z-score
     mean-reversion is backtested and DSR-scored on the held-out tail — no selection
     lookahead. Hourly bars (~24x the sample) sharpen both reversion and the DSR.

Honest bar unchanged: DSR >= 0.95. RESEARCH-ONLY — the short leg needs perps/margin
(S4-gated); modelled are spread P&L + turnover fees. Short-borrow/funding cost, execution
slippage, and DF-augmentation lags are noted ceilings. Float math; execution_authority=NONE.

ponytail: reuses the parquet loader shape + the project DSR estimator; the only new code is
pure-Python OLS + a Dickey-Fuller t-stat (no numpy/statsmodels in this project by design).
"""

from __future__ import annotations

import json
import sys
from itertools import product
from math import log, sqrt
from pathlib import Path
from statistics import mean, pstdev

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from tios.validation.multiple_testing import (  # noqa: E402
    deflated_sharpe_ratio,
    sharpe_variance_from_trials,
)

MULTI = ROOT / "data" / "normalized_multi"
OUT = ROOT / "artifacts" / "validation" / "stat_arb_pro"
PPY = 24 * 365  # hourly bars per year
FEE = 0.002  # round-trip both legs of the spread
DSR_PASS = 0.95
MIN_BARS = 8000  # ~1 year of 1h bars minimum
IN_SAMPLE_FRAC = 0.6
DF_CRIT = -3.34  # Engle-Granger residual 5% critical value (2 vars), conservative
WINDOWS = (60, 120)  # rolling z window in 1h bars (~2.5d, ~5d)
ENTRY_ZS = (2.0, 2.5)
EXIT_Z = 0.5
# Economically-related large caps (a-priori, not data-mined combinations).
PAIRS = (
    ("ETHUSDT", "BTCUSDT"), ("BNBUSDT", "BTCUSDT"), ("BNBUSDT", "ETHUSDT"),
    ("LTCUSDT", "BTCUSDT"), ("ETHUSDT", "SOLUSDT"), ("LINKUSDT", "ETHUSDT"),
    ("DOTUSDT", "ETHUSDT"), ("AVAXUSDT", "SOLUSDT"), ("ADAUSDT", "DOTUSDT"),
    ("MATICUSDT", "ETHUSDT"),
)  # fmt: skip


def load_hourly() -> dict[str, list[float | None]]:
    """1h closes per pair aligned to the union time index (None before listing)."""
    series: dict[str, dict] = {}
    for path in sorted(MULTI.glob("*_1h.parquet")):
        t = pq.read_table(path, columns=["timestamp_open_utc", "close"])
        if t.num_rows < MIN_BARS:
            continue
        times = [d.as_py() for d in t.column("timestamp_open_utc")]
        closes = [float(c.as_py()) for c in t.column("close")]
        series[path.stem[:-3]] = dict(zip(times, closes, strict=True))
    all_times = sorted(set().union(*[set(s) for s in series.values()]))
    return {p: [s.get(ts) for ts in all_times] for p, s in series.items()}


def _aligned_logs(
    pa: list[float | None], pb: list[float | None]
) -> tuple[list[float], list[float]]:
    """Log prices at indices where BOTH pairs trade and are positive."""
    la, lb = [], []
    for a, b in zip(pa, pb, strict=True):
        if a is not None and b is not None and a > 0 and b > 0:
            la.append(log(a))
            lb.append(log(b))
    return la, lb


def _ols(y: list[float], x: list[float]) -> tuple[float, float]:
    """Simple linear regression y = alpha + beta*x. Returns (alpha, beta)."""
    mx, my = mean(x), mean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    sxy = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y, strict=True))
    beta = sxy / sxx if sxx > 0 else 0.0
    return my - beta * mx, beta


def _df_tstat(s: list[float]) -> float:
    """Dickey-Fuller t-stat of rho in Δs_t = a + rho*s_{t-1}. Very negative => stationary.

    ponytail: no augmentation lags (plain DF). Add lagged diffs if serial correlation in the
    residual biases the stat; conservative DF_CRIT absorbs some of that for a first pass.
    """
    if len(s) < 20:
        return 0.0
    y = [s[t] - s[t - 1] for t in range(1, len(s))]
    x = [s[t - 1] for t in range(1, len(s))]
    a, rho = _ols(y, x)
    n = len(x)
    mx = mean(x)
    sxx = sum((xi - mx) ** 2 for xi in x)
    ssr = sum((yi - (a + rho * xi)) ** 2 for xi, yi in zip(x, y, strict=True))
    if sxx <= 0 or n <= 2:
        return 0.0
    se = sqrt((ssr / (n - 2)) / sxx)
    return rho / se if se > 0 else 0.0


def cointegrate(la: list[float], lb: list[float], split: int) -> tuple[float, float, float]:
    """In-sample Engle-Granger: hedge ratio + DF t-stat of the in-sample residual spread."""
    alpha, beta = _ols(la[:split], lb[:split])
    resid = [la[i] - beta * lb[i] - alpha for i in range(split)]
    return beta, alpha, _df_tstat(resid)


def backtest_oos(
    spread: list[float], split: int, window: int, entry_z: float
) -> tuple[list[float], int]:
    """Z-score mean-reversion on the held-out tail (t >= split). Rolling window may look back
    into in-sample bars (trailing only, no lookahead). Returns (oos_returns, trades)."""
    n = len(spread)
    strat: list[float] = []
    pos = 0
    trades = 0
    for t in range(split, n):
        ret = pos * (spread[t] - spread[t - 1]) if t > 0 else 0.0
        window_vals = spread[max(0, t - window) : t]
        if len(window_vals) >= window // 2:
            mu, sd = mean(window_vals), pstdev(window_vals)
            if sd > 0:
                z = (spread[t] - mu) / sd
                new = pos
                if pos == 0:
                    new = -1 if z > entry_z else (1 if z < -entry_z else 0)
                elif abs(z) < EXIT_Z:
                    new = 0
                if new != pos:
                    ret -= FEE * abs(new - pos)
                    trades += 1
                    pos = new
        strat.append(ret)
    return strat, trades


def _metrics(strat: list[float], trades: int) -> dict:
    equity = peak = 1.0
    max_dd = 0.0
    for r in strat:
        equity *= 1 + r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1)
    sd = pstdev(strat) if len(strat) > 1 else 0.0
    sharpe_bar = mean(strat) / sd if sd > 0 else 0.0
    return {
        "sharpe_bar": sharpe_bar,
        "sharpe_ann": round(sharpe_bar * sqrt(PPY), 2),
        "ann_return_pct": round((equity ** (PPY / len(strat)) - 1) * 100, 1)
        if equity > 0 and strat
        else -100.0,
        "max_drawdown_pct": round(max_dd * 100, 1),
        "total_return_pct": round((equity - 1) * 100, 1),
        "trades": trades,
        "bars": len(strat),
    }


def build_report() -> dict:
    prices = load_hourly()
    cointegrated = []
    trials: list[tuple[dict, list[float]]] = []
    for a, b in PAIRS:
        if a not in prices or b not in prices:
            continue
        la, lb = _aligned_logs(prices[a], prices[b])
        if len(la) < MIN_BARS:
            continue
        split = int(len(la) * IN_SAMPLE_FRAC)
        beta, alpha, df_t = cointegrate(la, lb, split)
        pair_id = f"{a}/{b}"
        cointegrated.append(
            {
                "pair": pair_id,
                "beta": round(beta, 4),
                "df_tstat": round(df_t, 3),
                "cointegrated": df_t < DF_CRIT,
                "oos_bars": len(la) - split,
            }
        )
        if df_t >= DF_CRIT:  # not cointegrated in-sample -> do not trade it
            continue
        spread = [la[i] - beta * lb[i] - alpha for i in range(len(la))]
        for window, entry_z in product(WINDOWS, ENTRY_ZS):
            strat, trades = backtest_oos(spread, split, window, entry_z)
            m = _metrics(strat, trades)
            if m["trades"] < 10:
                continue
            m.update(pair=pair_id, window=window, entry_z=entry_z, beta=round(beta, 4))
            trials.append((m, strat))

    n_coint = sum(1 for c in cointegrated if c["cointegrated"])
    if not trials:
        return {
            "schema": "tios-stat-arb-pro-v1",
            "mode": "OFFLINE_RESEARCH_ONLY",
            "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
            "execution_authority": "NONE",
            "pairs_tested": len(cointegrated),
            "pairs_cointegrated_in_sample": n_coint,
            "cointegration": cointegrated,
            "g10_dsr": {"verdict": "FAIL", "reason": "no cointegrated pair produced tradeable OOS"},
        }

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
    keys = ("pair", "beta", "window", "entry_z", "sharpe_ann", "ann_return_pct",
            "max_drawdown_pct", "trades")  # fmt: skip
    return {
        "schema": "tios-stat-arb-pro-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "execution_authority": "NONE",
        "tradeability": "RESEARCH_ONLY — short leg needs perps/margin (S4-gated)",
        "frequency": "1h",
        "in_sample_frac": IN_SAMPLE_FRAC,
        "pairs_tested": len(cointegrated),
        "pairs_cointegrated_in_sample": n_coint,
        "cointegration": cointegrated,
        "trials_searched": len(trials),
        "best": {k: best_m[k] for k in (*keys, "total_return_pct", "bars")},
        "g10_dsr": {
            "dsr": round(dsr["dsr"], 4),
            "expected_max_noise_sharpe": round(dsr["expected_maximum_noise_sharpe"], 4),
            "threshold": DSR_PASS,
            "verdict": "PASS" if dsr["dsr"] >= DSR_PASS else "FAIL",
            "verdict_is_genuine": dsr["dsr"] >= DSR_PASS,
            "note": "OUT-OF-SAMPLE DSR on in-sample-cointegrated pairs only (no selection "
            "lookahead), estimated hedge ratio, 1h. A PASS is a genuine market-neutral OOS "
            "edge subject to noted ceilings: short-borrow/funding cost, execution slippage, "
            "DF-augmentation lags, and cointegration decay (re-test the gate live).",
        },
        "top_configs": [
            {k: m[k] for k in keys}
            for m, _ in sorted(trials, key=lambda x: x[0]["sharpe_bar"], reverse=True)[:6]
        ],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    (OUT / "STAT_ARB_PRO.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"pairs tested: {report['pairs_tested']}  cointegrated in-sample: "
        f"{report['pairs_cointegrated_in_sample']}"
    )
    g = report["g10_dsr"]
    if "dsr" not in g:
        print(f"G10 DSR: {g['verdict']} — {g.get('reason', '')}")
        return
    b = report["best"]
    print(
        f"best OOS: {b['pair']} beta={b['beta']} w={b['window']} z={b['entry_z']} | "
        f"Sharpe {b['sharpe_ann']} ann {b['ann_return_pct']}% maxDD {b['max_drawdown_pct']}% "
        f"{b['trades']} trades ({b['bars']} OOS bars)"
    )
    print(
        f"G10 DSR: {g['dsr']} (need >= {g['threshold']}) -> {g['verdict']}  "
        f"genuine={g['verdict_is_genuine']}"
    )


if __name__ == "__main__":
    main()
