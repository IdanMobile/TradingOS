"""Reproduction spot-check for two seed-batch items (T-010-12 verification gate:
"spot-check 2 of the 10 seed items reproduce their stated original result").

Each test independently recomputes the item's indicator in plain Python from
the frozen micro fixture, then evaluates the item's ACTUAL entry_long/exit_long
`RuleTree` (parsed from its own canonical_strategy_spec.yaml via
`tios.strategy.spec`) bar-by-bar, asserting the two derivations agree. This
checks source-fidelity/warm-up/timing per the reproduction gates table, not
historical P&L (neither source carries an inherited profit claim).
"""

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from tios.strategy.spec import Comparison, RuleTree, parse_spec

FIXTURE = Path(__file__).parent.parent / "fixtures" / "micro" / "bars.csv"
FIXTURE_LONG = Path(__file__).parent.parent / "fixtures" / "micro" / "bars_long.csv"
SEED = Path(__file__).parent.parent / "strategies" / "seed"


def _rows(path: Path = FIXTURE) -> list[dict[str, float]]:
    with path.open() as f:
        return [
            {k: float(v) for k, v in row.items() if k != "timestamp_open_utc"}
            for row in csv.DictReader(f)
        ]


def _sma(values: list[float], window: int, idx: int) -> float | None:
    """SMA over `window` bars ending at 0-based idx; None if not enough history."""
    if idx + 1 < window:
        return None
    return sum(values[idx + 1 - window : idx + 1]) / window


def _donchian(
    highs: list[float], lows: list[float], window: int, idx: int
) -> tuple[float, float] | None:
    """Donchian channel over the PRIOR `window` bars, excluding bar idx (0-based)."""
    if idx < window:
        return None
    return max(highs[idx - window : idx]), min(lows[idx - window : idx])


def _eval_comparison(c: Comparison, ctx: dict[str, float]) -> bool:
    def resolve(token: str) -> float:
        try:
            return float(token)
        except ValueError:
            return ctx[token]

    left, right = resolve(c.left), resolve(c.right)
    ops = {
        "<=": left <= right,
        ">=": left >= right,
        "==": left == right,
        "!=": left != right,
        "<": left < right,
        ">": left > right,
    }
    return ops[c.op]


def _eval_tree(tree: RuleTree | None, ctx: dict[str, float]) -> bool:
    if tree is None:
        return False
    results = [_eval_comparison(c, ctx) for c in tree.comparisons]
    results += [_eval_tree(t, ctx) for t in tree.subtrees]
    return all(results) if tree.kind == "all" else any(results)


def _spec(item_dir: str):
    raw = yaml.safe_load((SEED / item_dir / "canonical_strategy_spec.yaml").read_text())
    return parse_spec(raw)


def test_qc1_dual_ma_cross_reproduction() -> None:
    spec = _spec("01-qc-dual-ma-cross")
    closes = [r["close"] for r in _rows()]
    fast_w = int(spec.indicators[0].parameters["window"])
    slow_w = int(spec.indicators[1].parameters["window"])

    for i, close in enumerate(closes):
        bar = i + 1
        sma_fast = _sma(closes, fast_w, i)
        sma_slow = _sma(closes, slow_w, i)
        if sma_fast is None or sma_slow is None:
            continue  # warm-up: bars 1-4 produce no signal, per spec assumption
        ctx = {"close": close, "sma_fast": sma_fast, "sma_slow": sma_slow}
        entry = _eval_tree(spec.entry_long, ctx)
        exit_ = _eval_tree(spec.exit_long, ctx)
        if bar == 5:
            assert not entry and not exit_, "bar5: sma_fast == sma_slow must be no-signal (tie)"
        elif 6 <= bar <= 12:
            assert entry and not exit_, f"bar{bar}: expected long entry signal"
        else:
            assert exit_ and not entry, f"bar{bar}: expected exit signal after crossover"


def _bollinger(
    closes: list[float], window: int, deviations: float, idx: int
) -> tuple[float, float, float] | None:
    """BB over `window` bars ending at idx (population std, the talib/Pine default)."""
    if idx + 1 < window:
        return None
    values = closes[idx + 1 - window : idx + 1]
    mid = sum(values) / window
    std = (sum((value - mid) ** 2 for value in values) / window) ** 0.5
    return mid - deviations * std, mid, mid + deviations * std


def _wilder_rsi(closes: list[float], window: int) -> list[float | None]:
    """Wilder-smoothed RSI (the talib/freqtrade convention)."""
    result: list[float | None] = [None] * len(closes)
    average_gain = average_loss = 0.0
    for index in range(1, len(closes)):
        delta = closes[index] - closes[index - 1]
        gain, loss = max(delta, 0.0), max(-delta, 0.0)
        if index <= window:
            average_gain += gain / window
            average_loss += loss / window
            if index < window:
                continue
        else:
            average_gain = (average_gain * (window - 1) + gain) / window
            average_loss = (average_loss * (window - 1) + loss) / window
        result[index] = (
            100.0 if average_loss == 0 else 100.0 - 100.0 / (1 + average_gain / average_loss)
        )
    return result


def test_pine1_bb_strategy_reproduction() -> None:
    # bars_long.csv is designed so BB(20,2) completes warm-up: a dip below the
    # lower band (bars 21-23), a recovery, then a rally through the upper band
    # (bars 27-29). Entry/exit bars are double-derived: designed analytically,
    # recomputed here independently, and asserted exactly.
    spec = _spec("07-pine-bb-strategy")
    closes = [r["close"] for r in _rows(FIXTURE_LONG)]
    window = int(spec.indicators[0].parameters["window"])
    deviations = float(spec.indicators[0].parameters["std"])
    entry_bars, exit_bars = {21, 22, 23}, {27, 28, 29}
    for i, close in enumerate(closes):
        bar = i + 1
        band = _bollinger(closes, window, deviations, i)
        if band is None:
            assert bar < window, f"bar{bar}: warm-up must end at the window boundary"
            continue
        lower, mid, upper = band
        ctx = {"close": close, "bb_lower": lower, "bb_mid": mid, "bb_upper": upper}
        entry = _eval_tree(spec.entry_long, ctx)
        exit_ = _eval_tree(spec.exit_long, ctx)
        assert entry == (bar in entry_bars), f"bar{bar}: entry mismatch"
        assert exit_ == (bar in exit_bars), f"bar{bar}: exit mismatch"


def test_ft1_sample_strategy_reproduction() -> None:
    # Same fixture as PINE1; the RSI(14)<30 guard admits only the deepest dip
    # bar (23), and the mid-band exit convention fires earlier (bar 25 onward)
    # than PINE1's upper-band exit — both differentiators are asserted exactly.
    spec = _spec("03-ft-sample-strategy")
    closes = [r["close"] for r in _rows(FIXTURE_LONG)]
    window = int(spec.indicators[0].parameters["window"])
    deviations = float(spec.indicators[0].parameters["std"])
    rsi = _wilder_rsi(closes, int(spec.indicators[1].parameters["window"]))
    entry_bars, exit_bars = {23}, {20, 25, 26, 27, 28, 29, 30, 31, 32}
    for i, close in enumerate(closes):
        bar = i + 1
        band = _bollinger(closes, window, deviations, i)
        if band is None or rsi[i] is None:
            continue
        lower, mid, upper = band
        ctx = {
            "close": close,
            "bb_lower": lower,
            "bb_mid": mid,
            "bb_upper": upper,
            "rsi": rsi[i],
        }
        entry = _eval_tree(spec.entry_long, ctx)
        exit_ = _eval_tree(spec.exit_long, ctx)
        assert entry == (bar in entry_bars), f"bar{bar}: entry mismatch (rsi={rsi[i]:.1f})"
        assert exit_ == (bar in exit_bars), f"bar{bar}: exit mismatch"


def _ema(values: list[float], window: int) -> list[float | None]:
    """True recursive EMA, talib convention: SMA seed, alpha = 2/(window+1)."""
    result: list[float | None] = [None] * len(values)
    alpha = 2.0 / (window + 1)
    for index in range(len(values)):
        if index + 1 < window:
            continue
        if index + 1 == window:
            result[index] = sum(values[:window]) / window
        else:
            previous = result[index - 1]
            assert previous is not None
            result[index] = alpha * values[index] + (1 - alpha) * previous
    return result


def test_ft2_ema_cross_reproduction() -> None:
    # True recursive EMA (SMA seed) replaces the spec's flagged "treat like SMA
    # warm-up" approximation. On bars_long.csv the state-based signals whipsaw
    # deterministically during the 100/101 oscillation (fast EMA flips around
    # the slow one each bar), then hold EXIT through the dip and ENTRY through
    # the rally — all three regimes are asserted exactly.
    spec = _spec("04-ft-ema-cross")
    closes = [r["close"] for r in _rows(FIXTURE_LONG)]
    short_window = int(spec.indicators[0].parameters["window"])
    long_window = int(spec.indicators[1].parameters["window"])
    ema_short = _ema(closes, short_window)
    ema_long = _ema(closes, long_window)
    for i, close in enumerate(closes):
        bar = i + 1
        if ema_long[i] is None:
            assert bar < long_window + 1, f"bar{bar}: warm-up must end at the long window"
            continue
        assert ema_short[i] is not None
        ctx = {"close": close, "ema_short": ema_short[i], "ema_long": ema_long[i]}
        entry = _eval_tree(spec.entry_long, ctx)
        exit_ = _eval_tree(spec.exit_long, ctx)
        if 10 <= bar <= 20:
            expected_entry = bar % 2 == 0  # oscillation: fast EMA above on 101-closes
        elif 21 <= bar <= 25:
            expected_entry = False  # dip: fast EMA below slow
        else:
            expected_entry = True  # rally from bar 26 onward
        assert entry == expected_entry, f"bar{bar}: entry mismatch"
        assert exit_ == (not expected_entry), f"bar{bar}: exit mismatch"


def test_qc2_donchian_breakout_reproduction() -> None:
    spec = _spec("02-qc-donchian-breakout")
    rows = _rows()
    closes = [r["close"] for r in rows]
    highs = [r["high"] for r in rows]
    lows = [r["low"] for r in rows]
    window = int(spec.indicators[0].parameters["window"])

    no_signal_bars = {5, 11, 12, 15, 16}
    entry_bars = {6, 7, 8, 9, 10}
    exit_bars = {13, 14}

    for i, close in enumerate(closes):
        bar = i + 1
        channel = _donchian(highs, lows, window, i)
        if channel is None:
            continue  # warm-up: bars 1-4 produce no signal, per spec assumption
        upper, lower = channel
        ctx = {"close": close, "donchian_upper": upper, "donchian_lower": lower}
        entry = _eval_tree(spec.entry_long, ctx)
        exit_ = _eval_tree(spec.exit_long, ctx)
        if bar in entry_bars:
            assert entry and not exit_, f"bar{bar}: expected breakout entry signal"
        elif bar in exit_bars:
            assert exit_ and not entry, f"bar{bar}: expected breakdown exit signal"
        elif bar in no_signal_bars:
            assert not entry and not exit_, f"bar{bar}: expected no signal (inside channel)"
