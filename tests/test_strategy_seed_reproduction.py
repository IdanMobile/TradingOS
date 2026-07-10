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
SEED = Path(__file__).parent.parent / "strategies" / "seed"


def _rows() -> list[dict[str, float]]:
    with FIXTURE.open() as f:
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
