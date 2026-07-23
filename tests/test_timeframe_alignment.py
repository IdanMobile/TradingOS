from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tios.strategy.timeframe_alignment import (
    TimeframeAlignmentError,
    _validate_integral_ratio,
    align_last_closed_higher_bars,
)
from tios.trading_domain import Timeframe


@pytest.mark.parametrize(
    ("lower", "higher"),
    [
        (Timeframe.M1, Timeframe.M5),
        (Timeframe.M5, Timeframe.H1),
        (Timeframe.M15, Timeframe.H4),
        (Timeframe.H1, Timeframe.D1),
    ],
)
def test_alignment_exposes_only_already_closed_higher_bars(
    lower: Timeframe,
    higher: Timeframe,
) -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    lower_step = timedelta(seconds=lower.seconds)
    higher_step = timedelta(seconds=higher.seconds)
    ratio = higher.seconds // lower.seconds
    lower_closes = tuple(start + index * lower_step for index in range(1, 2 * ratio + 2))
    higher_closes = (start + higher_step, start + 2 * higher_step)

    aligned = align_last_closed_higher_bars(
        lower_closes,
        higher_closes,
        lower_timeframe=lower,
        higher_timeframe=higher,
    )

    assert aligned[0] is None
    assert aligned[ratio - 1] == higher_closes[0]
    assert aligned[2 * ratio - 1] == higher_closes[1]
    assert all(
        value is None or value <= lower_close
        for lower_close, value in zip(lower_closes, aligned, strict=True)
    )
    for lower_close, value in zip(lower_closes, aligned, strict=True):
        expected = next(
            (close for close in reversed(higher_closes) if close <= lower_close),
            None,
        )
        assert value == expected


@pytest.mark.parametrize(
    ("lower", "higher"),
    [
        (Timeframe.H1, Timeframe.H1),
        (Timeframe.H4, Timeframe.M15),
    ],
)
def test_alignment_rejects_equal_or_reversed_pairs(
    lower: Timeframe,
    higher: Timeframe,
) -> None:
    with pytest.raises(TimeframeAlignmentError, match="must be greater"):
        align_last_closed_higher_bars(
            (),
            (),
            lower_timeframe=lower,
            higher_timeframe=higher,
        )


def test_alignment_ratio_validation_rejects_non_integral_pair() -> None:
    with pytest.raises(TimeframeAlignmentError, match="integral"):
        _validate_integral_ratio(120, 300)


def test_alignment_rejects_noncanonical_timeframes_and_unordered_closes() -> None:
    start = datetime(2026, 7, 1, tzinfo=UTC)
    with pytest.raises(TimeframeAlignmentError, match="canonical"):
        align_last_closed_higher_bars(
            (),
            (),
            lower_timeframe="1m",  # type: ignore[arg-type]
            higher_timeframe=Timeframe.M5,
        )
    with pytest.raises(TimeframeAlignmentError, match="strictly increasing"):
        align_last_closed_higher_bars(
            (start, start),
            (),
            lower_timeframe=Timeframe.M1,
            higher_timeframe=Timeframe.M5,
        )
