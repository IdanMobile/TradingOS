"""Causal micro-goldens for the frozen Spot taker-imbalance strategy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tios.strategy.taker_imbalance import (
    TakerImbalanceError,
    TakerObservation,
    project_taker_pulses,
    taker_shocks,
)

START = datetime(2024, 1, 1, tzinfo=UTC)


def _observation(index: int, imbalance: Decimal, *, valid: bool = True) -> TakerObservation:
    opened = START + timedelta(hours=index)
    total = Decimal(100) if valid else Decimal(0)
    bought = (imbalance + 1) * Decimal(50) if valid else Decimal(0)
    return TakerObservation(opened, opened + timedelta(minutes=59), total, bought)


def _high_sample() -> tuple[TakerObservation, ...]:
    baseline = tuple(
        _observation(index, Decimal("0.1") if index % 2 else Decimal("-0.1")) for index in range(24)
    )
    return (*baseline, _observation(24, Decimal("0.5")))


def test_strict_later_fill_and_six_hour_nonextending_exit() -> None:
    observations = _high_sample()
    spot = tuple(START + timedelta(hours=index) for index in range(32))
    actions = project_taker_pulses(
        observations,
        spot,
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
    )
    assert [(item.side, item.open_time) for item in actions] == [
        ("BUY", START + timedelta(hours=25)),
        ("SELL", START + timedelta(hours=31)),
    ]


def test_low_reversal_polarity_and_zero_variance() -> None:
    baseline = tuple(
        _observation(index, Decimal("0.1") if index % 2 else Decimal("-0.1")) for index in range(24)
    )
    low = (*baseline, _observation(24, Decimal("-0.5")))
    assert not taker_shocks(
        low, interpretation="CONTINUATION_HIGH", baseline_hours=24, threshold=Decimal("1.0")
    )
    assert (
        len(
            taker_shocks(
                low, interpretation="REVERSAL_LOW", baseline_hours=24, threshold=Decimal("1.0")
            )
        )
        == 1
    )
    flat = tuple(_observation(index, Decimal("0")) for index in range(25))
    assert not taker_shocks(
        flat, interpretation="CONTINUATION_HIGH", baseline_hours=24, threshold=Decimal("1.0")
    )


def test_invalid_row_resets_warmup_and_future_append_is_causal() -> None:
    sample = list(_high_sample())
    sample[10] = _observation(10, Decimal(0), valid=False)
    assert not taker_shocks(
        tuple(sample),
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
    )
    original = taker_shocks(
        _high_sample(),
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
    )
    appended = taker_shocks(
        (*_high_sample(), _observation(25, Decimal("-0.9"))),
        interpretation="CONTINUATION_HIGH",
        baseline_hours=24,
        threshold=Decimal("1.0"),
    )
    assert appended[: len(original)] == original


def test_invalid_parameters_fail_closed() -> None:
    with pytest.raises(TakerImbalanceError, match="outside the frozen roster"):
        taker_shocks(
            _high_sample(),
            interpretation="CONTINUATION_HIGH",
            baseline_hours=23,
            threshold=Decimal("1.0"),
        )
