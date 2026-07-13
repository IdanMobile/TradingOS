"""Canonical point-in-time semantics for D-075 cross-venue premium pulses."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_HOUR = timedelta(hours=1)
PULSE = timedelta(hours=6)
INTERPRETATIONS = ("CONTINUATION_POSITIVE", "REVERSAL_NEGATIVE")
BASELINES = (168, 720, 2160)
THRESHOLDS = (Decimal("1.0"), Decimal("2.0"))


class CrossVenuePremiumError(ValueError):
    """A source row or Spot projection violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class PremiumObservation:
    open_time: datetime
    close_time: datetime
    log_premium: Decimal

    @property
    def valid(self) -> bool:
        return self.log_premium.is_finite() and self.close_time >= self.open_time


@dataclass(frozen=True, slots=True)
class PremiumShock:
    source_open: datetime
    available_at: datetime
    z_score: Decimal


@dataclass(frozen=True, slots=True)
class SpotAction:
    open_time: datetime
    side: str
    source_open: datetime | None
    reason: str


def premium_shocks(
    observations: tuple[PremiumObservation, ...],
    *,
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
) -> tuple[PremiumShock, ...]:
    """Return strict extremes using only prior consecutive completed hours."""
    _validate_observations(observations)
    _validate_trial(interpretation, baseline_hours, threshold)
    shocks: list[PremiumShock] = []
    for index in range(baseline_hours, len(observations)):
        sample = observations[index - baseline_hours : index + 1]
        if any(not item.valid for item in sample) or any(
            right.open_time - left.open_time != ONE_HOUR for left, right in pairwise(sample)
        ):
            continue
        baseline = [item.log_premium for item in sample[:-1]]
        mean = sum(baseline, Decimal(0)) / Decimal(baseline_hours)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(
            baseline_hours
        )
        if variance == 0:
            continue
        z_score = (sample[-1].log_premium - mean) / variance.sqrt()
        eligible = (
            z_score > threshold
            if interpretation == "CONTINUATION_POSITIVE"
            else z_score < -threshold
        )
        if eligible:
            shocks.append(PremiumShock(sample[-1].open_time, sample[-1].close_time, z_score))
    return tuple(shocks)


def project_premium_pulses(
    observations: tuple[PremiumObservation, ...],
    spot_opens: tuple[datetime, ...],
    *,
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
    delay_bars: int = 0,
) -> tuple[SpotAction, ...]:
    """Project completed-hour extremes into non-stacking six-hour Spot pulses."""
    _validate_observations(observations)
    _validate_spot_opens(spot_opens)
    _validate_trial(interpretation, baseline_hours, threshold)
    if delay_bars not in {0, 1}:
        raise CrossVenuePremiumError("delay_bars must be 0 or 1")
    candidates: dict[datetime, datetime] = {}
    for shock in premium_shocks(
        observations,
        interpretation=interpretation,
        baseline_hours=baseline_hours,
        threshold=threshold,
    ):
        if shock.available_at < spot_opens[0]:
            continue
        mapped = bisect_right(spot_opens, shock.available_at) + delay_bars
        if mapped < len(spot_opens):
            candidates[spot_opens[mapped]] = shock.source_open

    interruptions: set[datetime] = set()
    for index, item in enumerate(observations):
        discontinuity = index > 0 and item.open_time - observations[index - 1].open_time != ONE_HOUR
        if item.valid and not discontinuity:
            continue
        boundary = max(item.open_time, item.close_time)
        mapped = bisect_right(spot_opens, boundary)
        if mapped < len(spot_opens):
            interruptions.add(spot_opens[mapped])

    actions: list[SpotAction] = []
    held = False
    scheduled_exit: datetime | None = None
    source_open: datetime | None = None
    for index, opened in enumerate(spot_opens):
        was_held = held
        gap = index > 0 and opened - spot_opens[index - 1] != ONE_HOUR
        interrupted = gap or opened in interruptions
        due = scheduled_exit is not None and opened >= scheduled_exit
        if held and (interrupted or due):
            actions.append(
                SpotAction(
                    opened,
                    "SELL",
                    source_open,
                    "SOURCE_GAP" if interrupted else "PULSE_END",
                )
            )
            held = False
            scheduled_exit = None
            source_open = None
        if interrupted or held or was_held:
            continue
        candidate = candidates.get(opened)
        if candidate is not None:
            actions.append(SpotAction(opened, "BUY", candidate, "CROSS_VENUE_PREMIUM_EXTREME"))
            held = True
            source_open = candidate
            scheduled_exit = opened + PULSE
    return tuple(actions)


def _validate_trial(interpretation: str, baseline_hours: int, threshold: Decimal) -> None:
    if interpretation not in INTERPRETATIONS:
        raise CrossVenuePremiumError(f"interpretation must be one of {INTERPRETATIONS}")
    if baseline_hours not in BASELINES or threshold not in THRESHOLDS:
        raise CrossVenuePremiumError("baseline_hours or threshold is outside the frozen roster")


def _validate_observations(observations: tuple[PremiumObservation, ...]) -> None:
    for item in observations:
        if any(
            value.tzinfo is None or value.utcoffset() != timedelta(0)
            for value in (item.open_time, item.close_time)
        ):
            raise CrossVenuePremiumError("source timestamps must be UTC-aware")
    if any(left.open_time >= right.open_time for left, right in pairwise(observations)):
        raise CrossVenuePremiumError("source opens must be unique and strictly ordered")


def _validate_spot_opens(spot_opens: tuple[datetime, ...]) -> None:
    if not spot_opens:
        raise CrossVenuePremiumError("Spot opens must not be empty")
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in spot_opens):
        raise CrossVenuePremiumError("Spot opens must be UTC-aware")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise CrossVenuePremiumError("Spot opens must be unique and strictly ordered")
