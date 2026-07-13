"""Canonical point-in-time semantics for CFTC Bitcoin-positioning pulses."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_HOUR = timedelta(hours=1)
ONE_WEEK = timedelta(days=7)
INTERPRETATIONS = ("ALIGNED_HIGH", "CONTRARIAN_LOW")
THRESHOLDS = (Decimal("0.5"), Decimal("1.0"))


class CftcPositioningError(ValueError):
    """Positioning feature or Spot projection violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class PositioningObservation:
    report_date: datetime
    available_at: datetime
    net_share: Decimal


@dataclass(frozen=True, slots=True)
class PositioningShock:
    report_date: datetime
    available_at: datetime
    z_score: Decimal


@dataclass(frozen=True, slots=True)
class SpotAction:
    open_time: datetime
    side: str
    report_date: datetime | None
    reason: str


def positioning_shocks(
    observations: tuple[PositioningObservation, ...],
    *,
    interpretation: str,
    baseline_weeks: int,
    threshold: Decimal,
) -> tuple[PositioningShock, ...]:
    """Return strict positioning extremes using only prior consecutive reports."""
    _validate_observations(observations)
    if interpretation not in INTERPRETATIONS:
        raise CftcPositioningError(f"interpretation must be one of {INTERPRETATIONS}")
    if baseline_weeks not in {13, 26, 52} or threshold not in THRESHOLDS:
        raise CftcPositioningError("baseline_weeks or threshold is outside the frozen roster")
    shocks: list[PositioningShock] = []
    for index in range(baseline_weeks, len(observations)):
        sample = observations[index - baseline_weeks : index + 1]
        if any(not _consecutive(left, right) for left, right in pairwise(sample)):
            continue
        baseline = [item.net_share for item in sample[:-1]]
        mean = sum(baseline, Decimal(0)) / Decimal(baseline_weeks)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(
            baseline_weeks
        )
        if variance == 0:
            continue
        z_score = (sample[-1].net_share - mean) / variance.sqrt()
        eligible = z_score > threshold if interpretation == "ALIGNED_HIGH" else z_score < -threshold
        if eligible:
            shocks.append(
                PositioningShock(sample[-1].report_date, sample[-1].available_at, z_score)
            )
    return tuple(shocks)


def project_positioning_pulses(
    observations: tuple[PositioningObservation, ...],
    spot_opens: tuple[datetime, ...],
    *,
    interpretation: str,
    baseline_weeks: int,
    threshold: Decimal,
    delay_bars: int = 0,
) -> tuple[SpotAction, ...]:
    """Project report-time extremes into non-stacking seven-day Spot pulses."""
    _validate_observations(observations)
    _validate_spot_opens(spot_opens)
    if delay_bars not in {0, 1}:
        raise CftcPositioningError("delay_bars must be 0 or 1")
    candidates: dict[datetime, datetime] = {}
    for shock in positioning_shocks(
        observations,
        interpretation=interpretation,
        baseline_weeks=baseline_weeks,
        threshold=threshold,
    ):
        if shock.available_at < spot_opens[0]:
            continue
        index = bisect_right(spot_opens, shock.available_at) + delay_bars
        if index < len(spot_opens):
            # If catch-up reports map to one open, only the newest report governs.
            candidates[spot_opens[index]] = shock.report_date
    source_gap_opens = {
        spot_opens[index]
        for left, right in pairwise(observations)
        if not _consecutive(left, right)
        and right.available_at >= spot_opens[0]
        and (index := bisect_right(spot_opens, right.available_at)) < len(spot_opens)
    }
    actions: list[SpotAction] = []
    held = False
    scheduled_exit: datetime | None = None
    report_date: datetime | None = None
    for index, opened in enumerate(spot_opens):
        was_held = held
        spot_gap = index > 0 and opened - spot_opens[index - 1] != ONE_HOUR
        source_gap = opened in source_gap_opens
        due = scheduled_exit is not None and opened >= scheduled_exit
        if held and (spot_gap or source_gap or due):
            reason = "SPOT_GAP" if spot_gap else "SOURCE_GAP" if source_gap else "PULSE_END"
            actions.append(SpotAction(opened, "SELL", report_date, reason))
            held = False
            scheduled_exit = None
            report_date = None
        if spot_gap or source_gap or held or was_held:
            continue
        candidate = candidates.get(opened)
        if candidate is not None:
            actions.append(SpotAction(opened, "BUY", candidate, "CFTC_POSITIONING_EXTREME"))
            held = True
            report_date = candidate
            scheduled_exit = opened + ONE_WEEK
    return tuple(actions)


def _consecutive(left: PositioningObservation, right: PositioningObservation) -> bool:
    return timedelta(days=6) <= right.report_date - left.report_date <= timedelta(days=8)


def _validate_observations(observations: tuple[PositioningObservation, ...]) -> None:
    for item in observations:
        if any(
            value.tzinfo is None or value.utcoffset() != timedelta(0)
            for value in (item.report_date, item.available_at)
        ):
            raise CftcPositioningError("report and availability timestamps must be UTC-aware")
        if (
            item.report_date.time() != datetime.min.time()
            or item.available_at.time() != datetime.min.time()
        ):
            raise CftcPositioningError("report and availability timestamps must be UTC midnights")
        if not item.net_share.is_finite() or not Decimal(-1) <= item.net_share <= Decimal(1):
            raise CftcPositioningError("net position share must be finite and within [-1, 1]")
        if item.available_at <= item.report_date:
            raise CftcPositioningError("availability must be strictly after report date")
    if any(left.report_date >= right.report_date for left, right in pairwise(observations)):
        raise CftcPositioningError("report dates must be unique and strictly ordered")
    if any(left.available_at > right.available_at for left, right in pairwise(observations)):
        raise CftcPositioningError("availability timestamps must be nondecreasing")


def _validate_spot_opens(spot_opens: tuple[datetime, ...]) -> None:
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in spot_opens):
        raise CftcPositioningError("Spot opens must be UTC-aware")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise CftcPositioningError("Spot opens must be unique and strictly ordered")
