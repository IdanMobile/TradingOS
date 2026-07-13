"""Offline checks for the combination/ensemble tester (no dataset, no network)."""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import scripts.run_strategy_combinations as comb  # noqa: E402


def _builder(entries: list[bool], exits: list[bool]):  # type: ignore[no-untyped-def]
    return lambda _c: (entries, exits)


def test_confluence_is_and_on_entries_or_on_exits() -> None:
    a = _builder([True, True, False], [False, False, True])
    b = _builder([True, False, False], [False, True, False])
    entries, exits = comb.confluence([a, b])({"close": [Decimal(1), Decimal(2), Decimal(3)]})
    assert entries == [True, False, False]  # both must agree to enter
    assert exits == [False, True, True]  # either can trigger an exit


def test_voting_counts_agreeing_members() -> None:
    builders = [
        _builder([True, False], [False, False]),
        _builder([True, True], [False, False]),
        _builder([False, True], [False, False]),
    ]
    entries, _ = comb.voting(builders, 2)({"close": [Decimal(1), Decimal(2)]})
    assert entries == [True, True]  # bar0: 2 agree; bar1: 2 agree


def test_backtest_returns_captures_move_and_charges_fees() -> None:
    candles = {"close": [Decimal("100"), Decimal("100"), Decimal("110"), Decimal("110")]}
    signals = ([True, False, False, False], [False, False, True, False])  # enter bar0, exit bar2
    returns, trades = comb.backtest_returns(candles, signals)
    assert trades == 2  # one entry toggle + one exit toggle
    assert returns[1] == pytest.approx(-comb.FEE)  # entry fee on the toggle bar
    assert returns[2] == pytest.approx(0.10)  # the +10% move captured while long
