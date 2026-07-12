"""Logic checks for the copied-public-strategy search.

Exercises the signal builders and the proxy screen on hand-built synthetic
candles, so a regression in entry/exit semantics or the buy-and-hold benchmark
fails here rather than silently corrupting a research artifact. No real dataset,
no network, no engines.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*

import scripts.run_external_strategy_search as ext  # noqa: E402


def _candles(closes: list[float]) -> dict[str, list[Decimal]]:
    """Flat OHLC where open==high==low==close (execution uses next-bar open)."""
    series = [Decimal(str(c)) for c in closes]
    return {"open": series, "high": series, "low": series, "close": series, "volume": series}


def test_sma_cross_enters_when_fast_above_slow() -> None:
    # Rising then falling: fast SMA leads slow up, then crosses back down.
    closes = [10, 10, 10, 11, 12, 13, 14, 15, 14, 12, 10, 9]
    entries, exits = ext.sma_cross(2, 4)(_candles(closes))
    assert any(entries), "a fast>slow crossover must produce an entry"
    assert any(exits), "a fast<slow crossover must produce an exit"
    # Entries and exits are mutually exclusive per bar (fast can't be both > and < slow).
    assert not any(e and x for e, x in zip(entries, exits, strict=True))


def test_donchian_breakout_triggers_on_new_high() -> None:
    # Flat channel, then a decisive breakout above the prior-window high.
    closes = [100] * 12 + [130, 131, 132]
    entries, exits = ext.donchian_breakout(entry_w=10, exit_w=5)(_candles(closes))
    assert entries[12], "close above the prior 10-bar high must enter"
    assert not entries[5], "no breakout inside the flat channel"


def test_rsi_reversion_buys_oversold() -> None:
    # Sharp sustained decline drives RSI below the oversold threshold.
    closes = [100 - i for i in range(20)]
    entries, _ = ext.rsi_reversion(window=14, low=Decimal("30"), high=Decimal("55"))(
        _candles(closes)
    )
    assert any(entries), "a monotonic decline must push RSI below 30 and enter"


def test_buy_hold_matches_price_ratio_net_of_fees() -> None:
    candles = _candles([100, 100, 200])  # execution at opens: buy@100, mark@200
    got = ext._buy_hold(candles)
    fee = seed_fees()
    expected = (Decimal("1") - fee) * (Decimal("200") / Decimal("100")) * (
        Decimal("1") - fee
    ) - Decimal("1")
    assert got == expected


def test_run_variant_profits_on_clean_uptrend() -> None:
    # Always-long trend filter on a monotone uptrend must beat zero after fees.
    closes = [100 + i for i in range(250)]
    result = ext._run_variant(_candles(closes), ext.trend_filter(200), "trend|window=200")
    assert result.total_return > 0
    assert result.trades >= 1


def seed_fees() -> Decimal:
    return ext.seed.FEES


def test_twenty_public_strategies_registered() -> None:
    # The operator asked for ~20 copied public strategies; guard the roster size
    # and that every one carries a public source attribution (copied, not generated).
    assert len(ext.STRATEGIES) == 20
    assert all(s.source and s.variants for s in ext.STRATEGIES)
    assert len({s.strategy_id for s in ext.STRATEGIES}) == 20
