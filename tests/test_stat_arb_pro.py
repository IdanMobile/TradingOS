"""Offline checks for the professional stat-arb (no files, no network).

Deterministic synthetic series via a tiny LCG — no numpy/random-seed dependence.
"""

from __future__ import annotations

import sys
from math import exp
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_stat_arb_pro as sap  # noqa: E402


def _noise(n: int, seed: int = 1) -> list[float]:
    """Deterministic uniform(-0.5,0.5) stream from a linear congruential generator."""
    out, x = [], seed
    for _ in range(n):
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        out.append(x / 0x7FFFFFFF - 0.5)
    return out


def test_ols_recovers_line() -> None:
    x = [float(i) for i in range(50)]
    y = [3.0 + 2.0 * xi for xi in x]
    alpha, beta = sap._ols(y, x)
    assert abs(alpha - 3.0) < 1e-9 and abs(beta - 2.0) < 1e-9


def test_df_tstat_stationary_vs_random_walk() -> None:
    eps = _noise(600)
    # Stationary AR: mean-reverting around 0 -> strongly negative DF t-stat.
    ar, prev = [], 0.0
    for e in eps:
        prev = 0.2 * prev + e
        ar.append(prev)
    # Random walk: cumulative sum -> DF t-stat near 0 (not stationary).
    rw, acc = [], 0.0
    for e in eps:
        acc += e
        rw.append(acc)
    assert sap._df_tstat(ar) < sap.DF_CRIT  # rejects unit root -> stationary
    assert sap._df_tstat(rw) > sap.DF_CRIT  # fails to reject -> non-stationary


def test_cointegration_gate_detects_and_rejects() -> None:
    eps_a, eps_b, eps_s = _noise(800, 1), _noise(800, 7), _noise(800, 99)
    a_log, acc = [], 0.0
    for e in eps_a:
        acc += e * 0.01
        a_log.append(acc)  # random-walk log price for A
    # Cointegrated B: tracks A (beta 1.5) plus a STATIONARY noise -> spread mean-reverts.
    b_log = [1.5 * a + 0.02 * s for a, s in zip(a_log, eps_s, strict=True)]
    # Independent B2: its own random walk -> not cointegrated with A.
    b2_log, acc2 = [], 0.0
    for e in eps_b:
        acc2 += e * 0.01
        b2_log.append(acc2)
    split = 500
    # cointegrate() takes (log A, log B); here A ~ beta*B, so regress a on b.
    _, _, df_coint = sap.cointegrate(a_log, b_log, split)
    _, _, df_indep = sap.cointegrate(a_log, b2_log, split)
    assert df_coint < sap.DF_CRIT  # constructed pair is cointegrated
    assert df_indep > df_coint  # independent walk is far less stationary


def test_backtest_oos_trades_on_mean_reverting_spread() -> None:
    # A spread that oscillates will cross entry/exit z-bands and generate trades.
    spread = [0.3 * (1 if i % 40 < 20 else -1) + 0.01 * n for i, n in enumerate(_noise(600))]
    strat, trades = sap.backtest_oos(spread, split=200, window=60, entry_z=1.0)
    assert len(strat) == len(spread) - 200
    assert trades > 0


def test_prices_are_positive_guard() -> None:
    # _aligned_logs must drop None / non-positive without raising.
    la, lb = sap._aligned_logs([1.0, None, exp(2.0)], [exp(1.0), 5.0, None])
    assert la == [0.0]  # only index 0 has both positive
    assert len(lb) == 1
