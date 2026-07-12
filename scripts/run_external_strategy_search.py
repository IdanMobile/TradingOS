#!/usr/bin/env python3
"""Offline search over ~20 COPIED public strategies against the frozen grid.

Purpose (operator request, 2026-07-12): test well-known public trading systems —
not internally generated ones — to see whether any survives the same honest screen
the seed validation probe uses (positive holdout, beats buy-and-hold net of fees,
robust across its parameter neighborhood, consistent across both instruments).

This is research only. Every candidate stays UNVALIDATED / NOT_ELIGIBLE /
execution_authority=NONE. A screen PASS here is a *promotion-probe candidate*, NOT
an approval: it still owes production G10 (DSR>=0.95, PBO) and cross-engine
reproduction before any HG-3 / paper work. All strategy logic is long-only spot,
reusing the reproduced-seed cycle's deterministic primitives.

ponytail: reuses scripts.run_seed_research_cycle_v0 primitives + the probe's screen;
adds only the public-strategy signal builders and the aggregate screen.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_seed_research_cycle_v0 as seed  # noqa: E402

OUT = ROOT / "artifacts" / "research_lab" / "external_strategy_search"
INSTRUMENTS = ("BTCUSDT", "ETHUSDT")
TIMEFRAMES = ("5m", "15m", "1h")
# Robustness screen thresholds (deliberately conservative, matching the probe's intent).
MIN_TRADES = 10  # reject degenerate 0/1-trade fits
MIN_NEIGHBOURHOOD_POSITIVE = Decimal("0.6")  # >=60% of the param neighborhood positive

Candles = dict[str, list[Decimal]]
SignalBuilder = Callable[[Candles], tuple[list[bool], list[bool]]]


# --------------------------------------------------------------------------- #
# Small indicator helpers layered on the seed primitives (long-only, spot).
# --------------------------------------------------------------------------- #
def _sma(values: list[Decimal], window: int) -> list[Decimal | None]:
    return seed.rolling_mean(values, window)


def _ema(values: list[Decimal], window: int) -> list[Decimal | None]:
    return seed.rolling_ema(values, window)


def _rsi(values: list[Decimal], window: int) -> list[Decimal | None]:
    return seed.wilder_rsi(values, window)


def _bollinger(
    values: list[Decimal], window: int, std: Decimal
) -> list[tuple[Decimal, Decimal, Decimal] | None]:
    return seed.rolling_bollinger(values, window, std)


def _roc(values: list[Decimal], window: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    for i in range(window, len(values)):
        base = values[i - window]
        if base != 0:
            out[i] = values[i] / base - Decimal("1")
    return out


def _donchian(candles: Candles, window: int) -> tuple[list[Decimal | None], list[Decimal | None]]:
    high, low = candles["high"], candles["low"]
    upper: list[Decimal | None] = [None] * len(high)
    lower: list[Decimal | None] = [None] * len(high)
    for i in range(window, len(high)):
        upper[i] = max(high[i - window : i])
        lower[i] = min(low[i - window : i])
    return upper, lower


def _cross(fast: list[Decimal | None], slow: list[Decimal | None]) -> tuple[list[bool], list[bool]]:
    entries = [f is not None and s is not None and f > s for f, s in zip(fast, slow, strict=True)]
    exits = [f is not None and s is not None and f < s for f, s in zip(fast, slow, strict=True)]
    return entries, exits


# --------------------------------------------------------------------------- #
# Public strategy builders. Each is a documented, copied public system.
# --------------------------------------------------------------------------- #
def sma_cross(fast: int, slow: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        return _cross(_sma(c["close"], fast), _sma(c["close"], slow))

    return build


def ema_cross(fast: int, slow: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        return _cross(_ema(c["close"], fast), _ema(c["close"], slow))

    return build


def donchian_breakout(entry_w: int, exit_w: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        entry_upper, _ = _donchian(c, entry_w)
        _, exit_lower = _donchian(c, exit_w)
        entries = [u is not None and p > u for p, u in zip(close, entry_upper, strict=True)]
        exits = [lo is not None and p < lo for p, lo in zip(close, exit_lower, strict=True)]
        return entries, exits

    return build


def bollinger_reversion(window: int, std: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        bands = _bollinger(close, window, std)
        entries = [b is not None and p < b[0] for p, b in zip(close, bands, strict=True)]
        exits = [b is not None and p > b[1] for p, b in zip(close, bands, strict=True)]
        return entries, exits

    return build


def bollinger_breakout(window: int, std: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        bands = _bollinger(close, window, std)
        entries = [b is not None and p > b[2] for p, b in zip(close, bands, strict=True)]
        exits = [b is not None and p < b[1] for p, b in zip(close, bands, strict=True)]
        return entries, exits

    return build


def rsi_reversion(window: int, low: Decimal, high: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        rsi = _rsi(c["close"], window)
        entries = [r is not None and r < low for r in rsi]
        exits = [r is not None and r > high for r in rsi]
        return entries, exits

    return build


def connors_rsi2(rsi_w: int, trend_w: int, rsi_buy: Decimal, exit_sma: int) -> SignalBuilder:
    """Larry Connors RSI(2): buy dip in an uptrend, exit on short-MA recovery."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        rsi = _rsi(close, rsi_w)
        trend = _sma(close, trend_w)
        exit_ma = _sma(close, exit_sma)
        entries = [
            r is not None and t is not None and r < rsi_buy and p > t
            for p, r, t in zip(close, rsi, trend, strict=True)
        ]
        exits = [m is not None and p > m for p, m in zip(close, exit_ma, strict=True)]
        return entries, exits

    return build


def bollinger_rsi(window: int, std: Decimal, rsi_w: int, rsi_buy: Decimal) -> SignalBuilder:
    """Connors-style: buy below lower band while RSI oversold, exit at mid band."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        bands = _bollinger(close, window, std)
        rsi = _rsi(close, rsi_w)
        entries = [
            b is not None and r is not None and p < b[0] and r < rsi_buy
            for p, b, r in zip(close, bands, rsi, strict=True)
        ]
        exits = [b is not None and p > b[1] for p, b in zip(close, bands, strict=True)]
        return entries, exits

    return build


def roc_momentum(window: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        roc = _roc(c["close"], window)
        entries = [r is not None and r > 0 for r in roc]
        exits = [r is not None and r < 0 for r in roc]
        return entries, exits

    return build


def triple_ma(fast: int, mid: int, slow: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        f, m, s = _sma(close, fast), _sma(close, mid), _sma(close, slow)
        entries = [
            a is not None and b is not None and d is not None and a > b > d
            for a, b, d in zip(f, m, s, strict=True)
        ]
        exits = [a is not None and b is not None and a < b for a, b in zip(f, m, strict=True)]
        return entries, exits

    return build


def trend_filter(window: int) -> SignalBuilder:
    """Classic long-only trend filter: hold while price is above its long SMA."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        close = c["close"]
        ma = _sma(close, window)
        entries = [m is not None and p > m for p, m in zip(close, ma, strict=True)]
        exits = [m is not None and p < m for p, m in zip(close, ma, strict=True)]
        return entries, exits

    return build


@dataclass(frozen=True)
class Strategy:
    strategy_id: str
    source: str  # public origin (copied, not generated)
    family: str
    variants: dict[str, SignalBuilder]  # trial_key -> builder (the param neighborhood)


def _grid(prefix: str, builder_factory: Callable[..., SignalBuilder], grid: list[dict]) -> dict:
    return {
        prefix + "|" + ",".join(f"{k}={v}" for k, v in params.items()): builder_factory(**params)
        for params in grid
    }


# 20 copied public strategies, each with a small parameter neighborhood for robustness.
STRATEGIES: tuple[Strategy, ...] = (
    Strategy(
        "EXT-TURTLE-S1",
        "Dennis/Eckhardt Turtle System 1 (public)",
        "breakout",
        _grid(
            "donchian",
            donchian_breakout,
            [
                {"entry_w": 20, "exit_w": 10},
                {"entry_w": 15, "exit_w": 7},
                {"entry_w": 25, "exit_w": 12},
            ],
        ),
    ),
    Strategy(
        "EXT-TURTLE-S2",
        "Dennis/Eckhardt Turtle System 2 (public)",
        "breakout",
        _grid(
            "donchian",
            donchian_breakout,
            [
                {"entry_w": 55, "exit_w": 20},
                {"entry_w": 40, "exit_w": 20},
                {"entry_w": 70, "exit_w": 25},
            ],
        ),
    ),
    Strategy(
        "EXT-DONCHIAN-40",
        "Donchian channel breakout, Ken-variant (public)",
        "breakout",
        _grid(
            "donchian",
            donchian_breakout,
            [
                {"entry_w": 40, "exit_w": 20},
                {"entry_w": 30, "exit_w": 15},
                {"entry_w": 50, "exit_w": 25},
            ],
        ),
    ),
    Strategy(
        "EXT-GOLDEN-CROSS",
        "Golden/Death Cross SMA50/200 (classic public)",
        "trend",
        _grid(
            "sma",
            sma_cross,
            [{"fast": 50, "slow": 200}, {"fast": 40, "slow": 180}, {"fast": 60, "slow": 220}],
        ),
    ),
    Strategy(
        "EXT-SMA-10-30",
        "SMA 10/30 crossover (classic public)",
        "trend",
        _grid(
            "sma",
            sma_cross,
            [{"fast": 10, "slow": 30}, {"fast": 8, "slow": 24}, {"fast": 12, "slow": 36}],
        ),
    ),
    Strategy(
        "EXT-SMA-20-50",
        "SMA 20/50 crossover (classic public)",
        "trend",
        _grid(
            "sma",
            sma_cross,
            [{"fast": 20, "slow": 50}, {"fast": 16, "slow": 40}, {"fast": 24, "slow": 60}],
        ),
    ),
    Strategy(
        "EXT-EMA-12-26",
        "EMA 12/26 crossover, MACD trend proxy (Appel, public)",
        "trend",
        _grid(
            "ema",
            ema_cross,
            [{"fast": 12, "slow": 26}, {"fast": 10, "slow": 21}, {"fast": 15, "slow": 30}],
        ),
    ),
    Strategy(
        "EXT-EMA-8-21",
        "EMA 8/21 crossover (classic public)",
        "trend",
        _grid(
            "ema",
            ema_cross,
            [{"fast": 8, "slow": 21}, {"fast": 6, "slow": 18}, {"fast": 9, "slow": 26}],
        ),
    ),
    Strategy(
        "EXT-EMA-20-50",
        "EMA 20/50 crossover (classic public)",
        "trend",
        _grid(
            "ema",
            ema_cross,
            [{"fast": 20, "slow": 50}, {"fast": 16, "slow": 40}, {"fast": 24, "slow": 60}],
        ),
    ),
    Strategy(
        "EXT-BB-REVERSION",
        "Bollinger Band mean reversion 20/2 (Bollinger, public)",
        "reversion",
        _grid(
            "bb",
            bollinger_reversion,
            [
                {"window": 20, "std": Decimal("2")},
                {"window": 20, "std": Decimal("2.5")},
                {"window": 15, "std": Decimal("2")},
            ],
        ),
    ),
    Strategy(
        "EXT-BB-BREAKOUT",
        "Bollinger Band breakout 20/2 (Bollinger, public)",
        "breakout",
        _grid(
            "bb",
            bollinger_breakout,
            [
                {"window": 20, "std": Decimal("2")},
                {"window": 20, "std": Decimal("1.5")},
                {"window": 25, "std": Decimal("2")},
            ],
        ),
    ),
    Strategy(
        "EXT-CONNORS-RSI2",
        "Larry Connors RSI(2) pullback (public)",
        "reversion",
        _grid(
            "rsi2",
            connors_rsi2,
            [
                {"rsi_w": 2, "trend_w": 200, "rsi_buy": Decimal("10"), "exit_sma": 5},
                {"rsi_w": 2, "trend_w": 200, "rsi_buy": Decimal("5"), "exit_sma": 5},
                {"rsi_w": 3, "trend_w": 150, "rsi_buy": Decimal("15"), "exit_sma": 5},
            ],
        ),
    ),
    Strategy(
        "EXT-RSI14",
        "RSI(14) 30/55 reversion (Wilder, public)",
        "reversion",
        _grid(
            "rsi",
            rsi_reversion,
            [
                {"window": 14, "low": Decimal("30"), "high": Decimal("55")},
                {"window": 14, "low": Decimal("25"), "high": Decimal("60")},
                {"window": 10, "low": Decimal("30"), "high": Decimal("55")},
            ],
        ),
    ),
    Strategy(
        "EXT-RSI4",
        "RSI(4) 25/55 reversion (public short-RSI)",
        "reversion",
        _grid(
            "rsi",
            rsi_reversion,
            [
                {"window": 4, "low": Decimal("25"), "high": Decimal("55")},
                {"window": 4, "low": Decimal("20"), "high": Decimal("60")},
                {"window": 5, "low": Decimal("25"), "high": Decimal("55")},
            ],
        ),
    ),
    Strategy(
        "EXT-ROC-12",
        "12-period Rate-of-Change momentum (public)",
        "momentum",
        _grid("roc", roc_momentum, [{"window": 12}, {"window": 10}, {"window": 15}]),
    ),
    Strategy(
        "EXT-ROC-20",
        "20-period Rate-of-Change momentum (public)",
        "momentum",
        _grid("roc", roc_momentum, [{"window": 20}, {"window": 16}, {"window": 26}]),
    ),
    Strategy(
        "EXT-TRIPLE-MA",
        "Triple SMA 10/20/50 alignment (classic public)",
        "trend",
        _grid(
            "tma",
            triple_ma,
            [
                {"fast": 10, "mid": 20, "slow": 50},
                {"fast": 8, "mid": 21, "slow": 55},
                {"fast": 12, "mid": 26, "slow": 50},
            ],
        ),
    ),
    Strategy(
        "EXT-TREND-SMA200",
        "Price>SMA200 long-only trend filter (classic public)",
        "trend",
        _grid("trend", trend_filter, [{"window": 200}, {"window": 150}, {"window": 100}]),
    ),
    Strategy(
        "EXT-BB-RSI",
        "Bollinger + RSI(3) confluence (Connors-style, public)",
        "reversion",
        _grid(
            "bbrsi",
            bollinger_rsi,
            [
                {"window": 20, "std": Decimal("2"), "rsi_w": 3, "rsi_buy": Decimal("15")},
                {"window": 20, "std": Decimal("2.5"), "rsi_w": 3, "rsi_buy": Decimal("10")},
                {"window": 15, "std": Decimal("2"), "rsi_w": 4, "rsi_buy": Decimal("15")},
            ],
        ),
    ),
    Strategy(
        "EXT-EMA-50-200",
        "EMA 50/200 golden-cross variant (classic public)",
        "trend",
        _grid(
            "ema",
            ema_cross,
            [{"fast": 50, "slow": 200}, {"fast": 40, "slow": 180}, {"fast": 60, "slow": 220}],
        ),
    ),
)


@dataclass(frozen=True)
class TrialResult:
    trial_key: str
    total_return: Decimal
    trades: int


def _run_variant(candles: Candles, builder: SignalBuilder, key: str) -> TrialResult:
    entries, exits = builder(candles)
    equity, trades = seed.simulate_next_open(candles["open"], entries, exits)
    return TrialResult(key, equity / seed.INITIAL_CASH - Decimal("1"), trades)


def _slice(candles: Candles, start: int, stop: int) -> Candles:
    return {name: values[start:stop] for name, values in candles.items()}


def _buy_hold(candles: Candles) -> Decimal:
    opens = candles["open"]
    if len(opens) < 2:
        return Decimal("-1")
    qty = (seed.INITIAL_CASH * (Decimal("1") - seed.FEES)) / opens[0]
    return qty * opens[-1] * (Decimal("1") - seed.FEES) / seed.INITIAL_CASH - Decimal("1")


def _thirds_all_positive(candles: Candles, builder: SignalBuilder, key: str) -> tuple[bool, dict]:
    n = len(candles["open"])
    spans = {
        "train": (0, n // 3),
        "validation": (n // 3, (2 * n) // 3),
        "holdout": ((2 * n) // 3, n),
    }
    rows = {
        name: _run_variant(_slice(candles, a, b), builder, key) for name, (a, b) in spans.items()
    }
    all_positive = all(r.total_return > 0 for r in rows.values())
    return all_positive, {name: str(r.total_return) for name, r in rows.items()}


def evaluate_strategy(strategy: Strategy) -> dict:
    """Screen a strategy across the full grid; report every context and any that pass."""
    contexts: list[dict] = []
    best_contexts: list[dict] = []
    for instrument in INSTRUMENTS:
        for timeframe in TIMEFRAMES:
            dataset = f"{instrument}_{timeframe}"
            candles = seed.load_candles(seed.DATASETS[dataset])
            trials = [_run_variant(candles, b, k) for k, b in strategy.variants.items()]
            best = max(trials, key=lambda t: t.total_return)
            positive_fraction = Decimal(sum(1 for t in trials if t.total_return > 0)) / Decimal(
                len(trials)
            )
            bh = _buy_hold(candles)
            builder = strategy.variants[best.trial_key]
            thirds_ok, thirds = _thirds_all_positive(candles, builder, best.trial_key)
            beats_bh = best.total_return > bh
            robust = positive_fraction >= MIN_NEIGHBOURHOOD_POSITIVE
            enough_trades = best.trades >= MIN_TRADES
            screen_pass = bool(
                best.total_return > 0 and beats_bh and thirds_ok and robust and enough_trades
            )
            row = {
                "dataset": dataset,
                "best_trial_key": best.trial_key,
                "best_total_return": str(best.total_return),
                "best_trades": best.trades,
                "buy_hold_return": str(bh),
                "beats_buy_hold": beats_bh,
                "neighbourhood_positive_fraction": str(positive_fraction),
                "thirds": thirds,
                "thirds_all_positive": thirds_ok,
                "screen_pass": screen_pass,
            }
            contexts.append(row)
            if screen_pass:
                best_contexts.append(row)
    return {
        "strategy_id": strategy.strategy_id,
        "source": strategy.source,
        "family": strategy.family,
        "variant_count": len(strategy.variants),
        "approval_status": "NOT_ELIGIBLE",
        "execution_authority": "NONE",
        "screen_pass_contexts": best_contexts,
        "contexts": contexts,
    }


def build_report() -> dict:
    results = [evaluate_strategy(s) for s in STRATEGIES]
    survivors = [
        {"strategy_id": r["strategy_id"], "contexts": r["screen_pass_contexts"]}
        for r in results
        if r["screen_pass_contexts"]
    ]
    return {
        "schema": "tios-external-strategy-search-v1",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "winner_selected": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "screen": {
            "rule": "best>0 AND beats_buy_hold AND all_three_thirds_positive "
            "AND neighbourhood_positive_fraction>=0.6 AND trades>=10",
            "note": "A screen PASS is a promotion-PROBE candidate only; production G10 "
            "(DSR>=0.95, PBO) and cross-engine reproduction remain mandatory before HG-3.",
            "min_trades": MIN_TRADES,
            "min_neighbourhood_positive": str(MIN_NEIGHBOURHOOD_POSITIVE),
        },
        "strategy_count": len(STRATEGIES),
        "survivor_count": len(survivors),
        "survivors": survivors,
        "strategies": results,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    artifact = OUT / "EXTERNAL_STRATEGY_SEARCH_2026_07_12.json"
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(artifact.relative_to(ROOT)),
                "strategies": report["strategy_count"],
                "survivors": report["survivor_count"],
                "survivor_ids": [s["strategy_id"] for s in report["survivors"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
