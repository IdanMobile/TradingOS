"""Checks for the stat-arb pairs engine (no files, no network)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scripts.run_stat_arb_pairs as sa  # noqa: E402


def test_spread_is_log_ratio() -> None:
    s = sa._spread([100.0, 200.0], [50.0, 50.0])
    assert abs(s[0] - math.log(2)) < 1e-9 and abs(s[1] - math.log(4)) < 1e-9


def test_backtest_trades_a_mean_reverting_spread() -> None:
    n = 400
    a = [100.0] * n
    # B oscillates around A, so log(A/B) is mean-reverting -> the engine should trade it.
    b = [100.0 / (1 + 0.15 * math.sin(i / 5)) for i in range(n)]
    strat, trades = sa.backtest(a, b, window=30, entry_z=1.5)
    assert len(strat) == n
    assert trades > 0  # a mean-reverting spread produces round trips


def test_flat_spread_never_trades() -> None:
    n = 200
    strat, trades = sa.backtest([100.0] * n, [100.0] * n, window=30, entry_z=2.0)
    assert trades == 0 and all(r == 0.0 for r in strat)
