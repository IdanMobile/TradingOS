"""Pure causal alignment of lower-frame closes to already-closed higher bars."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from tios.trading_domain import Timeframe


class TimeframeAlignmentError(ValueError):
    """The requested timeframe pair or close-time sequence is not safely alignable."""


def _validate_integral_ratio(lower_seconds: int, higher_seconds: int) -> None:
    if higher_seconds <= lower_seconds:
        raise TimeframeAlignmentError("higher timeframe must be greater than lower timeframe")
    if higher_seconds % lower_seconds:
        raise TimeframeAlignmentError("higher timeframe must be an integral lower-frame multiple")


def _validate_closes(closes: Sequence[datetime], label: str) -> None:
    for close in closes:
        if (
            not isinstance(close, datetime)
            or close.tzinfo is None
            or close.utcoffset() != UTC.utcoffset(close)
        ):
            raise TimeframeAlignmentError(f"{label} close times must be UTC datetimes")
    if any(previous >= current for previous, current in zip(closes, closes[1:], strict=False)):
        raise TimeframeAlignmentError(f"{label} close times must be strictly increasing")


def align_last_closed_higher_bars(
    lower_close_times: Sequence[datetime],
    higher_close_times: Sequence[datetime],
    *,
    lower_timeframe: Timeframe,
    higher_timeframe: Timeframe,
) -> tuple[datetime | None, ...]:
    """Return the latest higher close observable at each lower close.

    A higher bar is observable only when its close time is less than or equal to the
    lower bar's close time. The helper aligns timestamps only; it does not resample,
    synthesize, or evaluate higher-frame bars.
    """
    if not isinstance(lower_timeframe, Timeframe) or not isinstance(higher_timeframe, Timeframe):
        raise TimeframeAlignmentError("timeframes must be canonical Timeframe values")
    _validate_integral_ratio(lower_timeframe.seconds, higher_timeframe.seconds)
    _validate_closes(lower_close_times, "lower")
    _validate_closes(higher_close_times, "higher")

    aligned: list[datetime | None] = []
    higher_index = 0
    last_closed: datetime | None = None
    for lower_close in lower_close_times:
        while (
            higher_index < len(higher_close_times)
            and higher_close_times[higher_index] <= lower_close
        ):
            last_closed = higher_close_times[higher_index]
            higher_index += 1
        aligned.append(last_closed)
    return tuple(aligned)
