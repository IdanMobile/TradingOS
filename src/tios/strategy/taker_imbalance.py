"""Canonical point-in-time semantics for BTC Spot taker-imbalance pulses."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_HOUR = timedelta(hours=1)
PULSE = timedelta(hours=6)
INTERPRETATIONS = ("CONTINUATION_HIGH", "REVERSAL_LOW")
BASELINES = (24, 168, 720)
THRESHOLDS = (Decimal("1.0"), Decimal("2.0"))


class TakerImbalanceError(ValueError):
    """A source row or Spot projection violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class TakerObservation:
    open_time: datetime
    close_time: datetime
    quote_volume: Decimal
    taker_buy_quote_volume: Decimal

    @property
    def valid(self) -> bool:
        return (
            self.quote_volume > 0
            and Decimal(0) <= self.taker_buy_quote_volume <= self.quote_volume
            and self.close_time >= self.open_time
        )

    @property
    def imbalance(self) -> Decimal:
        if not self.valid:
            raise TakerImbalanceError("invalid row has no taker-imbalance feature")
        return Decimal(2) * self.taker_buy_quote_volume / self.quote_volume - Decimal(1)


@dataclass(frozen=True, slots=True)
class TakerShock:
    source_open: datetime
    available_at: datetime
    z_score: Decimal


@dataclass(frozen=True, slots=True)
class SpotAction:
    open_time: datetime
    side: str
    source_open: datetime | None
    reason: str


def taker_shocks(
    observations: tuple[TakerObservation, ...],
    *,
    interpretation: str,
    baseline_hours: int,
    threshold: Decimal,
) -> tuple[TakerShock, ...]:
    """Return strict extremes using only prior consecutive completed hours."""
    _validate_observations(observations)
    _validate_trial(interpretation, baseline_hours, threshold)
    shocks: list[TakerShock] = []
    for index in range(baseline_hours, len(observations)):
        sample = observations[index - baseline_hours : index + 1]
        if any(not item.valid for item in sample) or any(
            right.open_time - left.open_time != ONE_HOUR for left, right in pairwise(sample)
        ):
            continue
        baseline = [item.imbalance for item in sample[:-1]]
        mean = sum(baseline, Decimal(0)) / Decimal(baseline_hours)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(
            baseline_hours
        )
        if variance == 0:
            continue
        z_score = (sample[-1].imbalance - mean) / variance.sqrt()
        eligible = (
            z_score > threshold if interpretation == "CONTINUATION_HIGH" else z_score < -threshold
        )
        if eligible:
            shocks.append(TakerShock(sample[-1].open_time, sample[-1].close_time, z_score))
    return tuple(shocks)


def project_taker_pulses(
    observations: tuple[TakerObservation, ...],
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
        raise TakerImbalanceError("delay_bars must be 0 or 1")
    candidates: dict[datetime, datetime] = {}
    for shock in taker_shocks(
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
        boundary = item.close_time if item.close_time >= item.open_time else item.open_time
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
            reason = "SOURCE_GAP" if interrupted else "PULSE_END"
            actions.append(SpotAction(opened, "SELL", source_open, reason))
            held = False
            scheduled_exit = None
            source_open = None
        if interrupted or held or was_held:
            continue
        candidate = candidates.get(opened)
        if candidate is not None:
            actions.append(SpotAction(opened, "BUY", candidate, "TAKER_IMBALANCE_EXTREME"))
            held = True
            source_open = candidate
            scheduled_exit = opened + PULSE
    return tuple(actions)


def _validate_trial(interpretation: str, baseline_hours: int, threshold: Decimal) -> None:
    if interpretation not in INTERPRETATIONS:
        raise TakerImbalanceError(f"interpretation must be one of {INTERPRETATIONS}")
    if baseline_hours not in BASELINES or threshold not in THRESHOLDS:
        raise TakerImbalanceError("baseline_hours or threshold is outside the frozen roster")


def _validate_observations(observations: tuple[TakerObservation, ...]) -> None:
    for item in observations:
        if any(
            value.tzinfo is None or value.utcoffset() != timedelta(0)
            for value in (item.open_time, item.close_time)
        ):
            raise TakerImbalanceError("source timestamps must be UTC-aware")
        if any(
            not value.is_finite() or value < 0
            for value in (item.quote_volume, item.taker_buy_quote_volume)
        ):
            raise TakerImbalanceError("volumes must be finite and non-negative")
    if any(left.open_time >= right.open_time for left, right in pairwise(observations)):
        raise TakerImbalanceError("source opens must be unique and strictly ordered")


def _validate_spot_opens(spot_opens: tuple[datetime, ...]) -> None:
    if not spot_opens:
        raise TakerImbalanceError("Spot opens must not be empty")
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in spot_opens):
        raise TakerImbalanceError("Spot opens must be UTC-aware")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise TakerImbalanceError("Spot opens must be unique and strictly ordered")
