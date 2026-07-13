#!/usr/bin/env python3
"""Offline search over ~20 COPIED public strategies against the frozen grid.

Purpose (operator request, 2026-07-12): test well-known public trading systems —
not internally generated ones — to see whether any survives the same honest screen
the seed validation probe uses (positive holdout, beats buy-and-hold net of fees,
robust across its parameter neighborhood, consistent across both instruments).

This is research only. Every context stays UNVALIDATED / NOT_ELIGIBLE /
execution_authority=NONE. A context PASS is exploratory evidence, not a globally
frozen candidate or promotion result. All strategy logic is long-only spot, reusing
the reproduced-seed cycle's deterministic primitives.

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


# --------------------------------------------------------------------------- #
# Additional public indicators (OHLC-only; long-only spot). Batch added 2026-07-13.
# --------------------------------------------------------------------------- #
def _rolling_max(values: list[Decimal], window: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    for i in range(window - 1, len(values)):
        out[i] = max(values[i - window + 1 : i + 1])
    return out


def _rolling_min(values: list[Decimal], window: int) -> list[Decimal | None]:
    out: list[Decimal | None] = [None] * len(values)
    for i in range(window - 1, len(values)):
        out[i] = min(values[i - window + 1 : i + 1])
    return out


def _true_range(c: Candles) -> list[Decimal]:
    high, low, close = c["high"], c["low"], c["close"]
    tr = [high[0] - low[0]]
    for i in range(1, len(high)):
        pc = close[i - 1]
        tr.append(max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc)))
    return tr


def _atr(c: Candles, window: int) -> list[Decimal | None]:
    return seed.rolling_mean(_true_range(c), window)


def _stochastic_k(c: Candles, window: int) -> list[Decimal | None]:
    hh, ll, close = _rolling_max(c["high"], window), _rolling_min(c["low"], window), c["close"]
    out: list[Decimal | None] = [None] * len(close)
    for i in range(len(close)):
        if hh[i] is not None and ll[i] is not None and hh[i] != ll[i]:
            out[i] = (close[i] - ll[i]) / (hh[i] - ll[i]) * Decimal(100)
    return out


def _williams(c: Candles, window: int) -> list[Decimal | None]:
    hh, ll, close = _rolling_max(c["high"], window), _rolling_min(c["low"], window), c["close"]
    out: list[Decimal | None] = [None] * len(close)
    for i in range(len(close)):
        if hh[i] is not None and ll[i] is not None and hh[i] != ll[i]:
            out[i] = (hh[i] - close[i]) / (hh[i] - ll[i]) * Decimal(-100)
    return out


def _cci(c: Candles, window: int) -> list[Decimal | None]:
    tp = [(h + low + cl) / 3 for h, low, cl in zip(c["high"], c["low"], c["close"], strict=True)]
    sma = seed.rolling_mean(tp, window)
    out: list[Decimal | None] = [None] * len(tp)
    for i in range(window - 1, len(tp)):
        mean = sma[i]
        if mean is None:
            continue
        mad = sum(abs(tp[j] - mean) for j in range(i - window + 1, i + 1)) / window
        if mad != 0:
            out[i] = (tp[i] - mean) / (Decimal("0.015") * mad)
    return out


def _keltner(
    c: Candles, ema_w: int, atr_w: int, mult: Decimal
) -> tuple[list[Decimal | None], list[Decimal | None]]:
    mid, atr = _ema(c["close"], ema_w), _atr(c, atr_w)
    upper: list[Decimal | None] = [None] * len(mid)
    for i in range(len(mid)):
        if mid[i] is not None and atr[i] is not None:
            upper[i] = mid[i] + mult * atr[i]
    return upper, mid


def _ichimoku(
    c: Candles, tenkan_w: int, kijun_w: int
) -> tuple[list[Decimal | None], list[Decimal | None]]:
    def midline(window: int) -> list[Decimal | None]:
        hh, ll = _rolling_max(c["high"], window), _rolling_min(c["low"], window)
        return [
            (hh[i] + ll[i]) / 2 if hh[i] is not None and ll[i] is not None else None
            for i in range(len(hh))
        ]

    return midline(tenkan_w), midline(kijun_w)


def _macd(
    c: Candles, fast: int, slow: int, signal_w: int
) -> tuple[list[Decimal | None], list[Decimal | None]]:
    ef, es = _ema(c["close"], fast), _ema(c["close"], slow)
    macd: list[Decimal | None] = [
        f - s if f is not None and s is not None else None for f, s in zip(ef, es, strict=True)
    ]
    sig: list[Decimal | None] = [None] * len(macd)
    k, prev, count = Decimal(2) / (signal_w + 1), None, 0
    for i, m in enumerate(macd):
        if m is None:
            continue
        prev = m if prev is None else m * k + prev * (Decimal(1) - k)
        count += 1
        if count >= signal_w:
            sig[i] = prev
    return macd, sig


def _vortex(c: Candles, window: int) -> tuple[list[Decimal | None], list[Decimal | None]]:
    high, low, tr = c["high"], c["low"], _true_range(c)
    vm_plus = [Decimal(0)] + [abs(high[i] - low[i - 1]) for i in range(1, len(high))]
    vm_minus = [Decimal(0)] + [abs(low[i] - high[i - 1]) for i in range(1, len(high))]
    vip: list[Decimal | None] = [None] * len(high)
    vim: list[Decimal | None] = [None] * len(high)
    for i in range(window, len(high)):
        tr_sum = sum(tr[i - window + 1 : i + 1])
        if tr_sum != 0:
            vip[i] = sum(vm_plus[i - window + 1 : i + 1]) / tr_sum
            vim[i] = sum(vm_minus[i - window + 1 : i + 1]) / tr_sum
    return vip, vim


def _aroon(c: Candles, window: int) -> tuple[list[Decimal | None], list[Decimal | None]]:
    high, low = c["high"], c["low"]
    up: list[Decimal | None] = [None] * len(high)
    down: list[Decimal | None] = [None] * len(high)
    for i in range(window, len(high)):
        window_high = high[i - window : i + 1]
        window_low = low[i - window : i + 1]
        since_high = window - window_high.index(max(window_high))
        since_low = window - window_low.index(min(window_low))
        up[i] = Decimal(window - since_high) / window * 100
        down[i] = Decimal(window - since_low) / window * 100
    return up, down


def macd_cross(fast: int, slow: int, signal_w: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        macd, sig = _macd(c, fast, slow, signal_w)
        return _cross(macd, sig)

    return build


def stochastic_reversion(window: int, low: Decimal, high: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        k = _stochastic_k(c, window)
        entries = [v is not None and v < low for v in k]
        exits = [v is not None and v > high for v in k]
        return entries, exits

    return build


def williams_reversion(window: int, low: Decimal, high: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        wr = _williams(c, window)
        entries = [v is not None and v < low for v in wr]
        exits = [v is not None and v > high for v in wr]
        return entries, exits

    return build


def cci_breakout(window: int, level: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        cci = _cci(c, window)
        entries = [v is not None and v > level for v in cci]
        exits = [v is not None and v < -level for v in cci]
        return entries, exits

    return build


def keltner_breakout(ema_w: int, atr_w: int, mult: Decimal) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        upper, mid = _keltner(c, ema_w, atr_w, mult)
        close = c["close"]
        entries = [u is not None and p > u for p, u in zip(close, upper, strict=True)]
        exits = [m is not None and p < m for p, m in zip(close, mid, strict=True)]
        return entries, exits

    return build


def ichimoku_trend(tenkan_w: int, kijun_w: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        tenkan, kijun = _ichimoku(c, tenkan_w, kijun_w)
        close = c["close"]
        entries = [
            t is not None and k is not None and p > k and t > k
            for p, t, k in zip(close, tenkan, kijun, strict=True)
        ]
        exits = [k is not None and p < k for p, k in zip(close, kijun, strict=True)]
        return entries, exits

    return build


def vortex_cross(window: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        return _cross(*_vortex(c, window))

    return build


def aroon_cross(window: int) -> SignalBuilder:
    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        return _cross(*_aroon(c, window))

    return build


# --------------------------------------------------------------------------- #
# Candlestick-pattern strategies (bullish pattern = entry, bearish mirror = exit).
# Long-only spot; every one is a copied public pattern. Batch added 2026-07-13.
# --------------------------------------------------------------------------- #
def engulfing(min_ratio: Decimal) -> SignalBuilder:
    """Bullish/bearish engulfing: current body engulfs the prior body (>= min_ratio bigger)."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        o, cl = c["open"], c["close"]
        entries, exits = [False] * len(o), [False] * len(o)
        for i in range(1, len(o)):
            prev_body, body = abs(cl[i - 1] - o[i - 1]), abs(cl[i] - o[i])
            if body < min_ratio * prev_body:
                continue
            if cl[i] > o[i] and cl[i - 1] < o[i - 1] and cl[i] >= o[i - 1] and o[i] <= cl[i - 1]:
                entries[i] = True  # bullish engulfing
            if cl[i] < o[i] and cl[i - 1] > o[i - 1] and o[i] >= cl[i - 1] and cl[i] <= o[i - 1]:
                exits[i] = True  # bearish engulfing
        return entries, exits

    return build


def hammer_star(shadow_ratio: Decimal) -> SignalBuilder:
    """Hammer (long lower shadow) = entry; shooting star (long upper shadow) = exit."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        o, h, low, cl = c["open"], c["high"], c["low"], c["close"]
        entries, exits = [False] * len(o), [False] * len(o)
        for i in range(len(o)):
            body = abs(cl[i] - o[i])
            if body <= 0:
                continue
            upper = h[i] - max(o[i], cl[i])
            lower = min(o[i], cl[i]) - low[i]
            if lower >= shadow_ratio * body and upper <= body:
                entries[i] = True  # hammer
            if upper >= shadow_ratio * body and lower <= body:
                exits[i] = True  # shooting star
        return entries, exits

    return build


def piercing_darkcloud(penetration: Decimal) -> SignalBuilder:
    """Piercing line = entry; dark-cloud cover = exit (penetration into the prior body)."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        o, cl = c["open"], c["close"]
        entries, exits = [False] * len(o), [False] * len(o)
        for i in range(1, len(o)):
            prev = abs(cl[i - 1] - o[i - 1])
            if prev <= 0:
                continue
            if cl[i - 1] < o[i - 1] and cl[i] > o[i] and o[i] < cl[i - 1]:
                if cl[i] >= cl[i - 1] + penetration * prev:  # closes into prior bearish body
                    entries[i] = True
            if cl[i - 1] > o[i - 1] and cl[i] < o[i] and o[i] > cl[i - 1]:
                if cl[i] <= cl[i - 1] - penetration * prev:  # closes into prior bullish body
                    exits[i] = True
        return entries, exits

    return build


def morning_evening_star(star_max: Decimal) -> SignalBuilder:
    """Morning star (3-bar bottom) = entry; evening star (3-bar top) = exit."""

    def build(c: Candles) -> tuple[list[bool], list[bool]]:
        o, cl = c["open"], c["close"]
        entries, exits = [False] * len(o), [False] * len(o)
        for i in range(2, len(o)):
            body0, body1 = abs(cl[i - 2] - o[i - 2]), abs(cl[i - 1] - o[i - 1])
            mid0 = (o[i - 2] + cl[i - 2]) / 2
            if body0 <= 0 or body1 > star_max * body0:
                continue
            if cl[i - 2] < o[i - 2] and cl[i] > o[i] and cl[i] >= mid0:
                entries[i] = True  # morning star
            if cl[i - 2] > o[i - 2] and cl[i] < o[i] and cl[i] <= mid0:
                exits[i] = True  # evening star
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
    Strategy(
        "EXT-MACD-CROSS",
        "MACD line/signal crossover 12/26/9 (Appel, public)",
        "momentum",
        _grid(
            "macd",
            macd_cross,
            [
                {"fast": 12, "slow": 26, "signal_w": 9},
                {"fast": 10, "slow": 21, "signal_w": 9},
                {"fast": 8, "slow": 17, "signal_w": 9},
            ],
        ),
    ),
    Strategy(
        "EXT-STOCHASTIC",
        "Stochastic %K oversold/overbought reversion (Lane, public)",
        "reversion",
        _grid(
            "stoch",
            stochastic_reversion,
            [
                {"window": 14, "low": Decimal("20"), "high": Decimal("80")},
                {"window": 14, "low": Decimal("25"), "high": Decimal("75")},
                {"window": 10, "low": Decimal("20"), "high": Decimal("80")},
            ],
        ),
    ),
    Strategy(
        "EXT-WILLIAMS-R",
        "Williams %R oversold/overbought reversion (Williams, public)",
        "reversion",
        _grid(
            "williams",
            williams_reversion,
            [
                {"window": 14, "low": Decimal("-80"), "high": Decimal("-20")},
                {"window": 10, "low": Decimal("-85"), "high": Decimal("-15")},
                {"window": 21, "low": Decimal("-80"), "high": Decimal("-20")},
            ],
        ),
    ),
    Strategy(
        "EXT-CCI-BREAKOUT",
        "Commodity Channel Index +/-100 breakout (Lambert, public)",
        "momentum",
        _grid(
            "cci",
            cci_breakout,
            [
                {"window": 20, "level": Decimal("100")},
                {"window": 14, "level": Decimal("100")},
                {"window": 20, "level": Decimal("150")},
            ],
        ),
    ),
    Strategy(
        "EXT-KELTNER-BREAKOUT",
        "Keltner Channel EMA+ATR breakout (Keltner/Chester, public)",
        "breakout",
        _grid(
            "keltner",
            keltner_breakout,
            [
                {"ema_w": 20, "atr_w": 10, "mult": Decimal("2")},
                {"ema_w": 20, "atr_w": 10, "mult": Decimal("1.5")},
                {"ema_w": 14, "atr_w": 10, "mult": Decimal("2")},
            ],
        ),
    ),
    Strategy(
        "EXT-ICHIMOKU",
        "Ichimoku tenkan/kijun trend (Hosoda, public)",
        "trend",
        _grid(
            "ichimoku",
            ichimoku_trend,
            [
                {"tenkan_w": 9, "kijun_w": 26},
                {"tenkan_w": 7, "kijun_w": 22},
                {"tenkan_w": 12, "kijun_w": 30},
            ],
        ),
    ),
    Strategy(
        "EXT-VORTEX",
        "Vortex Indicator VI+/VI- crossover (Botes/Siepman, public)",
        "trend",
        _grid("vortex", vortex_cross, [{"window": 14}, {"window": 10}, {"window": 21}]),
    ),
    Strategy(
        "EXT-AROON",
        "Aroon up/down crossover (Chande, public)",
        "trend",
        _grid("aroon", aroon_cross, [{"window": 25}, {"window": 14}, {"window": 20}]),
    ),
    Strategy(
        "EXT-PAT-ENGULFING",
        "Bullish/bearish engulfing candlestick pattern (public)",
        "pattern",
        _grid(
            "engulf",
            engulfing,
            [
                {"min_ratio": Decimal("1.0")},
                {"min_ratio": Decimal("1.2")},
                {"min_ratio": Decimal("1.5")},
            ],
        ),
    ),
    Strategy(
        "EXT-PAT-HAMMER",
        "Hammer / shooting-star candlestick pattern (public)",
        "pattern",
        _grid(
            "hammer",
            hammer_star,
            [
                {"shadow_ratio": Decimal("2")},
                {"shadow_ratio": Decimal("2.5")},
                {"shadow_ratio": Decimal("3")},
            ],
        ),
    ),
    Strategy(
        "EXT-PAT-PIERCING",
        "Piercing line / dark-cloud cover candlestick pattern (public)",
        "pattern",
        _grid(
            "piercing",
            piercing_darkcloud,
            [
                {"penetration": Decimal("0.5")},
                {"penetration": Decimal("0.6")},
                {"penetration": Decimal("0.7")},
            ],
        ),
    ),
    Strategy(
        "EXT-PAT-STAR",
        "Morning star / evening star candlestick pattern (public)",
        "pattern",
        _grid(
            "star",
            morning_evening_star,
            [
                {"star_max": Decimal("0.3")},
                {"star_max": Decimal("0.5")},
                {"star_max": Decimal("0.7")},
            ],
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


def _temporal_screen(candles: Candles, variants: dict[str, SignalBuilder]) -> dict:
    """Select on train only, then evaluate the frozen variant once per later split."""
    n = len(candles["open"])
    spans = {
        "train": (0, n // 3),
        "validation": (n // 3, (2 * n) // 3),
        "holdout": ((2 * n) // 3, n),
    }
    train = _slice(candles, *spans["train"])
    train_trials = [_run_variant(train, builder, key) for key, builder in variants.items()]
    selected = max(train_trials, key=lambda trial: trial.total_return)
    builder = variants[selected.trial_key]
    results = {
        "train": selected,
        "validation": _run_variant(
            _slice(candles, *spans["validation"]), builder, selected.trial_key
        ),
        "holdout": _run_variant(_slice(candles, *spans["holdout"]), builder, selected.trial_key),
    }
    thirds = {name: str(result.total_return) for name, result in results.items()}
    positive_fraction = Decimal(
        sum(1 for trial in train_trials if trial.total_return > 0)
    ) / Decimal(len(train_trials))
    holdout = _slice(candles, *spans["holdout"])
    holdout_bh = _buy_hold(holdout)
    all_positive = all(result.total_return > 0 for result in results.values())
    total_trades = sum(result.trades for result in results.values())
    screen_pass = bool(
        all_positive
        and results["holdout"].total_return > holdout_bh
        and positive_fraction >= MIN_NEIGHBOURHOOD_POSITIVE
        and total_trades >= MIN_TRADES
    )
    return {
        # Compatibility aliases now explicitly mean the train-selected result.
        "best_trial_key": selected.trial_key,
        "best_total_return": str(selected.total_return),
        "best_trades": selected.trades,
        "selected_trial_key": selected.trial_key,
        "selection_partition": "train",
        "selection_objective": "max_net_total_return",
        "selection_candidate_count": len(train_trials),
        "selection_tie_break": "variant_declaration_order",
        "split_indices": {
            name: {"start_inclusive": start, "stop_exclusive": stop}
            for name, (start, stop) in spans.items()
        },
        "parameters_frozen_after_train": True,
        "validation_used_for_selection": False,
        "holdout_used_for_selection": False,
        "holdout_evaluation_count": 1,
        "train_total_return": str(results["train"].total_return),
        "validation_total_return": str(results["validation"].total_return),
        "holdout_total_return": str(results["holdout"].total_return),
        "train_trades": results["train"].trades,
        "validation_trades": results["validation"].trades,
        "holdout_trades": results["holdout"].trades,
        "total_trades": total_trades,
        "holdout_buy_hold_return": str(holdout_bh),
        "beats_buy_hold": results["holdout"].total_return > holdout_bh,
        "neighbourhood_positive_fraction": str(positive_fraction),
        "thirds": thirds,
        "thirds_all_positive": all_positive,
        "screen_pass": screen_pass,
        "evidence_scope": "CONTEXT_LEVEL_EXPLORATORY_SCREEN",
        "promotion_eligible": False,
    }


def evaluate_strategy(strategy: Strategy) -> dict:
    """Screen a strategy across the full grid; report every context and any that pass."""
    contexts: list[dict] = []
    best_contexts: list[dict] = []
    for instrument in INSTRUMENTS:
        for timeframe in TIMEFRAMES:
            dataset = f"{instrument}_{timeframe}"
            candles = seed.load_candles(seed.DATASETS[dataset])
            row = {
                "dataset": dataset,
                **_temporal_screen(candles, strategy.variants),
            }
            contexts.append(row)
            if row["screen_pass"]:
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
    context_passes = [
        {"strategy_id": r["strategy_id"], "contexts": r["screen_pass_contexts"]}
        for r in results
        if r["screen_pass_contexts"]
    ]
    return {
        "schema": "tios-external-strategy-search-v2",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "promotion_status": "METHOD_BLOCKED",
        "search_lineage_complete": False,
        "winner_selected": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "screen": {
            "method_id": "train-select-validation-freeze-single-holdout-v1",
            "scope": "context-level exploratory screen; not globally frozen-candidate validation",
            "split_rule": "chronological contiguous thirds",
            "candidate_roster_selection": "predeclared before evaluation; no winner selected",
            "selection_rule": "select max net total return on train only; "
            "declaration order breaks ties",
            "freeze_rule": "selected parameters are unchanged for validation and holdout",
            "holdout_rule": "evaluate the frozen variant once; holdout never participates "
            "in selection",
            "global_candidate_frozen": False,
            "promotion_eligible": False,
            "pass_rule": "all thirds positive AND holdout beats holdout buy-and-hold "
            "AND train-neighbourhood positive fraction>=0.6 AND total trades>=10",
            "note": "A context PASS is exploratory evidence only; source/spec lineage "
            "and one globally frozen candidate are still missing.",
            "min_trades": MIN_TRADES,
            "min_neighbourhood_positive": str(MIN_NEIGHBOURHOOD_POSITIVE),
        },
        "strategy_count": len(STRATEGIES),
        "context_pass_count": len(context_passes),
        "context_passes": context_passes,
        "strategies": results,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = build_report()
    artifact = OUT / "EXTERNAL_STRATEGY_SEARCH_TRAIN_SELECT_V2_2026_07_13.json"
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "artifact": str(artifact.relative_to(ROOT)),
                "strategies": report["strategy_count"],
                "context_passes": report["context_pass_count"],
                "context_pass_ids": [s["strategy_id"] for s in report["context_passes"]],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
