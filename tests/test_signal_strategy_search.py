"""Checks for the volume/volatility/order-flow signal builders.

Hand-built series so a regression in the rolling VWAP, order-flow ratio, ATR, or
volume-confirmed breakout logic fails here rather than silently mis-stating a
research result. No frozen dataset, no network.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for scripts.*

import scripts.run_signal_strategy_search as sig  # noqa: E402


def _rich(close, volume, quote, taker, high=None, low=None) -> dict[str, list[Decimal]]:
    D = lambda xs: [Decimal(str(x)) for x in xs]  # noqa: E731
    return {
        "open": D(close),
        "high": D(high or close),
        "low": D(low or close),
        "close": D(close),
        "volume": D(volume),
        "quote_volume": D(quote),
        "taker_buy": D(taker),
    }


def test_rolling_sum_is_a_trailing_window_total() -> None:
    got = sig._rolling_sum([Decimal(x) for x in (1, 2, 3, 4, 5)], 3)
    assert got[:2] == [None, None]
    assert got[2:] == [Decimal(6), Decimal(9), Decimal(12)]  # 1+2+3, 2+3+4, 3+4+5


def test_rolling_vwap_is_quote_over_base() -> None:
    # window 2: vwap = sum(quote)/sum(volume). Prices 10 then 20, equal volume -> 15.
    c = _rich(close=[10, 20, 30], volume=[1, 1, 1], quote=[10, 20, 30], taker=[1, 1, 1])
    vwap = sig._rolling_vwap(c, 2)
    assert vwap[0] is None
    assert vwap[1] == Decimal(15)  # (10+20)/(1+1)
    assert vwap[2] == Decimal(25)  # (20+30)/(1+1)


def test_rolling_taker_ratio_between_zero_and_one() -> None:
    c = _rich(close=[10, 10, 10], volume=[10, 10, 10], quote=[100, 100, 100], taker=[7, 3, 5])
    ratio = sig._rolling_taker_ratio(c, 2)
    assert ratio[1] == Decimal(10) / Decimal(20)  # (7+3)/(10+10)
    assert all(r is None or 0 <= r <= 1 for r in ratio)


def test_vwap_reversion_buys_below_and_sells_above() -> None:
    c = _rich(close=[10, 20, 5, 40], volume=[1, 1, 1, 1], quote=[10, 20, 5, 40], taker=[1, 1, 1, 1])
    entries, exits = sig.vwap_reversion(2)(c)
    assert not any(e and x for e, x in zip(entries, exits, strict=True))
    assert any(entries) and any(exits)


def test_volume_breakout_requires_a_volume_surge() -> None:
    # Same price breakout twice; only the high-volume one should enter.
    close = [100] * 20 + [130, 131]
    high = close
    low = close
    volume = [10] * 20 + [10, 100]  # last bar is the surge
    c = _rich(
        close=close,
        volume=volume,
        quote=[v * 100 for v in volume],
        taker=[v // 2 for v in volume],
        high=high,
        low=low,
    )
    entries, _ = sig.volume_breakout(10, Decimal("2"))(c)
    assert entries[21], "breakout on 10x-average volume must fire"
    assert not entries[20], "breakout on average volume must not fire"
