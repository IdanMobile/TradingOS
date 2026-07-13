"""Checks for the shared laddered TP/SL exit engine (pure math, no venue)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from tios.execution import exit_ladder as el

ENTRY, ATR = Decimal("64000"), Decimal("500")  # 2xATR default -> 1R = 1000


def test_build_ladder_long_stop_below_targets_above() -> None:
    ladder = el.build_ladder(direction=el.Direction.LONG, entry=ENTRY, atr=ATR)
    assert ladder.stop_loss == Decimal("63000") and ladder.risk_per_unit == Decimal("1000")
    assert [tp.price for tp in ladder.take_profits] == [
        Decimal("65000"), Decimal("66000"), Decimal("67000"), Decimal("68000")
    ]  # fmt: skip
    assert [tp.close_fraction for tp in ladder.take_profits] == [Decimal("0.25")] * 4


def test_build_ladder_short_mirrors() -> None:
    ladder = el.build_ladder(direction=el.Direction.SHORT, entry=ENTRY, atr=ATR)
    assert ladder.stop_loss == Decimal("65000")
    assert [tp.price for tp in ladder.take_profits] == [
        Decimal("63000"), Decimal("62000"), Decimal("61000"), Decimal("60000")
    ]  # fmt: skip


def test_position_size_follows_the_stop() -> None:
    # risk 1% of 10,000 = 100 USDT; stop 1000 away -> 0.1 units.
    size = el.position_size(
        equity=Decimal("10000"),
        risk_fraction=Decimal("0.01"),
        entry=ENTRY,
        stop_loss=Decimal("63000"),
    )
    assert size == Decimal("0.1")
    assert (
        el.position_size(
            equity=Decimal("10000"), risk_fraction=Decimal("0.01"), entry=ENTRY, stop_loss=ENTRY
        )
        == 0
    )


def test_evaluate_stop_hit_closes_the_remaining_position() -> None:
    ladder = el.build_ladder(direction=el.Direction.LONG, entry=ENTRY, atr=ATR)
    decision = el.evaluate(
        ladder=ladder,
        price=Decimal("62999"),
        taken_levels=frozenset({1}),
        current_stop=Decimal("63000"),
    )
    assert decision.stop_hit is True
    assert decision.close_fraction == Decimal("0.75")  # TP1's 0.25 already banked -> 0.75 remains


def test_evaluate_tp1_triggers_and_moves_stop_to_breakeven() -> None:
    ladder = el.build_ladder(direction=el.Direction.LONG, entry=ENTRY, atr=ATR)
    decision = el.evaluate(
        ladder=ladder,
        price=Decimal("65000"),
        taken_levels=frozenset(),
        current_stop=Decimal("63000"),
    )
    assert decision.triggered_tps == (1,) and decision.close_fraction == Decimal("0.25")
    assert decision.new_stop_loss == ENTRY  # risk-free after TP1


def test_evaluate_does_not_retrigger_a_taken_tp() -> None:
    ladder = el.build_ladder(direction=el.Direction.LONG, entry=ENTRY, atr=ATR)
    decision = el.evaluate(
        ladder=ladder, price=Decimal("66000"), taken_levels=frozenset({1}), current_stop=ENTRY
    )
    assert decision.triggered_tps == (2,) and decision.new_stop_loss is None  # already at breakeven


def test_config_rejects_bad_ladders() -> None:
    with pytest.raises(ValueError, match="ascending"):
        el.LadderConfig(
            Decimal("2"), (Decimal("2"), Decimal("1")), (Decimal("0.5"), Decimal("0.5"))
        )
    with pytest.raises(ValueError, match="sum to"):
        el.LadderConfig(Decimal("2"), (Decimal("1"),), (Decimal("1.5"),))
    with pytest.raises(ValueError, match="same length"):
        el.LadderConfig(Decimal("2"), (Decimal("1"), Decimal("2")), (Decimal("1"),))
