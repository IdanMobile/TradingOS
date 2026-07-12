"""Checks for the human-readable backtest view (win/loss, rolling channel, slicing).

Hand-built series so a regression in the round-trip win/loss accounting, the O(n)
Donchian channel, or the time-window slicing fails here rather than silently
mis-stating a dollar outcome. No frozen dataset, no network.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*

import scripts.backtest_human_view as hv  # noqa: E402


def _candles(closes: list[float]) -> dict[str, list[Decimal]]:
    s = [Decimal(str(c)) for c in closes]
    return {"open": s, "high": s, "low": s, "close": s}


def test_prior_extreme_excludes_current_bar() -> None:
    vals = [Decimal(x) for x in (5, 3, 8, 1, 9, 2)]
    hi = hv._prior_extreme(vals, 2, want_max=True)
    lo = hv._prior_extreme(vals, 2, want_max=False)
    # index 2: prior 2 = {5,3} -> max 5, min 3; index 4: prior 2 = {8,1} -> max 8, min 1.
    assert hi[0] is None and hi[1] is None
    assert hi[2] == Decimal(5) and lo[2] == Decimal(3)
    assert hi[4] == Decimal(8) and lo[4] == Decimal(1)


def test_per_trade_backtest_counts_a_loss() -> None:
    # Donchian-2: breakout up (enter high), then the market collapses (exit low) -> loss.
    closes = [100, 100, 100, 120, 130, 80, 70, 60]
    entries, exits = hv.fast_donchian(2)(_candles(closes))
    out = hv.per_trade_backtest(_candles(closes), entries, exits)
    assert out.trades == out.wins + out.losses
    assert out.trades == 1 and out.wins == 0 and out.losses == 1
    assert Decimal(out.end_usd) < hv.START_CAPITAL  # ended below the $1000 stake
    assert 0 <= int(out.win_rate_pct) <= 100


def test_per_trade_backtest_pure_uptrend_all_win() -> None:
    closes = [100 + i for i in range(30)]
    entries, exits = hv.fast_donchian(3)(_candles(closes))
    out = hv.per_trade_backtest(_candles(closes), entries, exits)
    assert Decimal(out.end_usd) > hv.START_CAPITAL  # made money in a clean uptrend
    assert out.losses == 0


def test_slice_window_keeps_last_days() -> None:
    base = datetime(2020, 1, 1, tzinfo=UTC)
    times = [base + timedelta(days=i) for i in range(100)]  # 100 daily bars
    data = hv.Loaded(_candles([100 + i for i in range(100)]), times)
    sliced = hv.slice_window(data, days=10)
    # Last 10 days inclusive of the cutoff boundary -> ~11 bars, never the whole set.
    assert 10 <= len(sliced["close"]) <= 12
    assert sliced["close"][-1] == Decimal("199")
