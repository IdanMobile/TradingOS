"""Check the multi-dataset normalizer's missing-data handling (no network).

The new logic beyond the reused, already-tested primitives is: a pair/interval with
no downloaded months yields None (not a crash), so coins listed mid-window don't
break a normalize run. Fixture-free — uses a symbol that will never have raw files.
"""

from __future__ import annotations

from tios.dataset import normalize_multi as nm


def test_absent_pair_returns_none() -> None:
    assert nm.normalize_pair("NOSUCHCOINUSDT", "1d") is None


def test_scope_constants_are_wired() -> None:
    # The normalizer walks the same pair/timeframe scope the acquirer downloads.
    assert "BTCUSDT" in nm.TOP_PAIRS and "ETHUSDT" in nm.TOP_PAIRS
    assert nm.TIMEFRAMES == ("1m", "5m", "15m", "1h", "4h", "1d")
