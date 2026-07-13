"""Logic checks for the copied-public-strategy search.

Exercises the signal builders and the proxy screen on hand-built synthetic
candles, so a regression in entry/exit semantics or the buy-and-hold benchmark
fails here rather than silently corrupting a research artifact. No real dataset,
no network, no engines.
"""

from __future__ import annotations

import math
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


def test_temporal_screen_selects_without_seeing_holdout() -> None:
    def always_long(candles):
        n = len(candles["open"])
        return [True] * n, [False] * n

    def never_trade(candles):
        n = len(candles["open"])
        return [False] * n, [False] * n

    prefix = [100 + i for i in range(60)]
    rising_holdout = prefix + [160 + i for i in range(30)]
    falling_holdout = prefix + [160 - 2 * i for i in range(30)]
    variants = {"always-long": always_long, "never-trade": never_trade}

    rising = ext._temporal_screen(_candles(rising_holdout), variants)
    falling = ext._temporal_screen(_candles(falling_holdout), variants)

    assert rising["selected_trial_key"] == falling["selected_trial_key"] == "always-long"
    assert rising["train_total_return"] == falling["train_total_return"]
    assert rising["holdout_total_return"] != falling["holdout_total_return"]
    assert rising["split_indices"] == {
        "train": {"start_inclusive": 0, "stop_exclusive": 30},
        "validation": {"start_inclusive": 30, "stop_exclusive": 60},
        "holdout": {"start_inclusive": 60, "stop_exclusive": 90},
    }
    assert rising["selection_partition"] == "train"
    assert rising["parameters_frozen_after_train"] is True
    assert rising["validation_used_for_selection"] is False
    assert rising["holdout_used_for_selection"] is False
    assert rising["holdout_evaluation_count"] == 1
    assert rising["promotion_eligible"] is False


def test_report_is_method_blocked_without_global_candidate(monkeypatch) -> None:
    monkeypatch.setattr(
        ext,
        "evaluate_strategy",
        lambda strategy: {
            "strategy_id": strategy.strategy_id,
            "screen_pass_contexts": [],
        },
    )
    report = ext.build_report()
    assert report["winner_selected"] is False
    assert report["search_lineage_complete"] is False
    assert report["promotion_status"] == "METHOD_BLOCKED"
    assert report["screen"]["global_candidate_frozen"] is False
    assert report["screen"]["promotion_eligible"] is False


def seed_fees() -> Decimal:
    return ext.seed.FEES


def test_public_strategy_roster_is_registered() -> None:
    # 20 original + 8 indicators + 4 candlestick patterns; each carries a public source.
    assert len(ext.STRATEGIES) == 32
    assert all(s.source and s.variants for s in ext.STRATEGIES)
    assert len({s.strategy_id for s in ext.STRATEGIES}) == 32
    assert sum(1 for s in ext.STRATEGIES if s.family == "pattern") == 4


def test_engulfing_pattern_detects_a_bullish_reversal() -> None:
    # A down bar, then an up bar whose body engulfs it -> bullish engulfing entry.
    o = [Decimal("100"), Decimal("97")]
    close = [Decimal("98"), Decimal("101")]
    candles = {"open": o, "high": close, "low": o, "close": close, "volume": close}
    entries, exits = ext.engulfing(Decimal("1.0"))(candles)
    assert entries[1] is True and exits[1] is False


def _ohlc_up(n: int, spread: str = "0.5") -> dict[str, list[Decimal]]:
    closes = [Decimal(100 + i) for i in range(n)]
    s = Decimal(spread)
    return {
        "open": closes,
        "high": [c + s for c in closes],
        "low": [c - s for c in closes],
        "close": closes,
        "volume": closes,
    }


def test_new_oscillators_stay_in_bounds() -> None:
    c = _candles([100 + (i % 7) - 3 for i in range(60)])  # oscillating
    stoch = [v for v in ext._stochastic_k(c, 14) if v is not None]
    williams = [v for v in ext._williams(c, 14) if v is not None]
    assert stoch and all(Decimal(0) <= v <= Decimal(100) for v in stoch)
    assert williams and all(Decimal(-100) <= v <= Decimal(0) for v in williams)


def test_new_trend_builders_signal_on_a_clean_uptrend() -> None:
    c = _ohlc_up(120)
    for builder in (ext.vortex_cross(14), ext.aroon_cross(25), ext.ichimoku_trend(9, 26)):
        entries, exits = builder(c)
        assert any(entries)  # a clean uptrend must produce at least one long entry
        assert not any(e and x for e, x in zip(entries, exits, strict=True))


def test_macd_cross_fires_on_changing_momentum() -> None:
    # A linear trend has a constant MACD (no cross); an oscillating market must cross both ways.
    closes = [100 + 20 * math.sin(i / 8) for i in range(200)]
    entries, exits = ext.macd_cross(12, 26, 9)(_candles(closes))
    assert any(entries) and any(exits)
