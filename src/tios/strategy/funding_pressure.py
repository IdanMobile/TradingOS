"""Canonical point-in-time semantics for funding-pressure Spot eligibility."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import pairwise

POLARITIES = ("CONTINUATION", "CONTRARIAN")


class FundingPressureError(ValueError):
    """Funding feature or Spot projection violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class FundingObservation:
    calc_time: datetime
    interval_hours: int
    rate: Decimal


@dataclass(frozen=True, slots=True)
class EligibilityChange:
    observed_at: datetime
    long_eligible: bool
    trailing_mean: Decimal


@dataclass(frozen=True, slots=True)
class SpotAction:
    open_time: datetime
    side: str
    observed_at: datetime


def eligibility_changes(
    observations: tuple[FundingObservation, ...],
    *,
    polarity: str,
    lookback: int,
    threshold: Decimal,
) -> tuple[EligibilityChange, ...]:
    """Emit only eligibility state changes after the complete rolling warm-up."""
    if polarity not in POLARITIES:
        raise FundingPressureError(f"polarity must be one of {POLARITIES}")
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback <= 0:
        raise FundingPressureError("lookback must be a positive integer")
    if not threshold.is_finite() or threshold < 0:
        raise FundingPressureError("threshold must be finite and non-negative")
    if any(
        item.calc_time.tzinfo is None or item.calc_time.utcoffset() != timedelta(0)
        for item in observations
    ):
        raise FundingPressureError("funding calc_time values must be UTC-aware")
    if any(item.interval_hours <= 0 or not item.rate.is_finite() for item in observations):
        raise FundingPressureError("funding intervals and rates must be valid")
    if any(left.calc_time >= right.calc_time for left, right in pairwise(observations)):
        raise FundingPressureError("funding observations must be unique and strictly ordered")

    changes: list[EligibilityChange] = []
    previous = False
    for index in range(lookback - 1, len(observations)):
        window = observations[index + 1 - lookback : index + 1]
        average = sum((item.rate for item in window), Decimal(0)) / Decimal(lookback)
        eligible = average > threshold if polarity == "CONTINUATION" else average < -threshold
        if eligible != previous:
            changes.append(EligibilityChange(observations[index].calc_time, eligible, average))
            previous = eligible
    return tuple(changes)


def project_to_spot_opens(
    changes: tuple[EligibilityChange, ...], spot_opens: tuple[datetime, ...]
) -> tuple[SpotAction, ...]:
    """Project state changes onto their expected strictly-later hourly Spot opens."""
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in spot_opens):
        raise FundingPressureError("Spot opens must be UTC-aware")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise FundingPressureError("Spot opens must be unique and strictly ordered")
    available = set(spot_opens)
    actions: list[SpotAction] = []
    held = False
    for change in changes:
        expected = change.observed_at.replace(minute=0, second=0, microsecond=0) + timedelta(
            hours=1
        )
        if expected <= change.observed_at:
            raise FundingPressureError("projected fill must be strictly later than observation")
        if expected not in available:
            continue
        if change.long_eligible != held:
            actions.append(
                SpotAction(expected, "BUY" if change.long_eligible else "SELL", change.observed_at)
            )
            held = change.long_eligible
    return tuple(actions)


def observation_from_milliseconds(
    calc_time_ms: int, interval_hours: int, rate: Decimal
) -> FundingObservation:
    """Construct an exact UTC observation without apparent-hour rounding."""
    return FundingObservation(
        datetime.fromtimestamp(calc_time_ms / 1000, UTC), interval_hours, rate
    )
