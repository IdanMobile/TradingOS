"""Causal micro-goldens for the frozen D-075 premium strategy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from tios.strategy.cross_venue_premium import (
    CrossVenuePremiumError,
    PremiumObservation,
    premium_shocks,
    project_premium_pulses,
)

START = datetime(2024, 1, 1, tzinfo=UTC)


def _observation(index: int, value: Decimal) -> PremiumObservation:
    opened = START + timedelta(hours=index)
    return PremiumObservation(opened, opened + timedelta(minutes=59), value)


def _sample(extreme: Decimal) -> tuple[PremiumObservation, ...]:
    baseline = tuple(
        _observation(index, Decimal("0.001") if index % 2 else Decimal("-0.001"))
        for index in range(168)
    )
    return (*baseline, _observation(168, extreme))


def test_strict_later_fill_and_six_hour_exit() -> None:
    spot = tuple(START + timedelta(hours=index) for index in range(176))
    actions = project_premium_pulses(
        _sample(Decimal("0.01")),
        spot,
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    assert [(item.side, item.open_time) for item in actions] == [
        ("BUY", START + timedelta(hours=169)),
        ("SELL", START + timedelta(hours=175)),
    ]


def test_negative_reversal_polarity_and_zero_variance() -> None:
    low = _sample(Decimal("-0.01"))
    assert not premium_shocks(
        low,
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    assert (
        len(
            premium_shocks(
                low,
                interpretation="REVERSAL_NEGATIVE",
                baseline_hours=168,
                threshold=Decimal("1.0"),
            )
        )
        == 1
    )
    flat = tuple(_observation(index, Decimal(0)) for index in range(169))
    assert not premium_shocks(
        flat,
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )


def test_gap_resets_warmup_and_future_append_is_causal() -> None:
    sample = list(_sample(Decimal("0.01")))
    sample.pop(80)
    sample.append(_observation(169, Decimal("0.02")))
    assert not premium_shocks(
        tuple(sample),
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    original = premium_shocks(
        _sample(Decimal("0.01")),
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    appended = premium_shocks(
        (*_sample(Decimal("0.01")), _observation(169, Decimal("-0.02"))),
        interpretation="CONTINUATION_POSITIVE",
        baseline_hours=168,
        threshold=Decimal("1.0"),
    )
    assert appended[: len(original)] == original


def test_invalid_parameters_fail_closed() -> None:
    with pytest.raises(CrossVenuePremiumError, match="outside the frozen roster"):
        premium_shocks(
            _sample(Decimal("0.01")),
            interpretation="CONTINUATION_POSITIVE",
            baseline_hours=167,
            threshold=Decimal("1.0"),
        )
