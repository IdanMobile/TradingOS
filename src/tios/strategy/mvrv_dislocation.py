"""Canonical point-in-time semantics for Bitcoin MVRV dislocation pulses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import pairwise

ONE_DAY = timedelta(days=1)
ONE_HOUR = timedelta(hours=1)
SIDES = ("HIGH", "LOW")


class MvrvDislocationError(ValueError):
    """MVRV feature or Spot projection violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class MvrvObservation:
    source_day: datetime
    mvrv: Decimal


@dataclass(frozen=True, slots=True)
class MvrvShock:
    source_day: datetime
    z_score: Decimal


@dataclass(frozen=True, slots=True)
class SpotAction:
    open_time: datetime
    side: str
    source_day: datetime | None
    reason: str


def mvrv_shocks(
    observations: tuple[MvrvObservation, ...], *, side: str, window: int
) -> tuple[MvrvShock, ...]:
    """Return strict log-MVRV dislocations using only consecutive prior daily values."""
    _validate_observations(observations)
    if side not in SIDES:
        raise MvrvDislocationError(f"side must be one of {SIDES}")
    if isinstance(window, bool) or not isinstance(window, int) or window <= 1:
        raise MvrvDislocationError("window must be an integer greater than one")
    logs = [item.mvrv.ln() for item in observations]
    shocks: list[MvrvShock] = []
    for index in range(window, len(observations)):
        sample = observations[index - window : index + 1]
        if any(right.source_day - left.source_day != ONE_DAY for left, right in pairwise(sample)):
            continue
        if len({item.mvrv for item in sample[:-1]}) == 1:
            continue
        baseline = logs[index - window : index]
        mean = sum(baseline, Decimal(0)) / Decimal(window)
        variance = sum(((value - mean) ** 2 for value in baseline), Decimal(0)) / Decimal(window)
        if variance == 0:
            continue
        z_score = (logs[index] - mean) / variance.sqrt()
        if (side == "HIGH" and z_score > 1) or (side == "LOW" and z_score < -1):
            shocks.append(MvrvShock(observations[index].source_day, z_score))
    return tuple(shocks)


def project_mvrv_pulses(
    observations: tuple[MvrvObservation, ...],
    spot_opens: tuple[datetime, ...],
    *,
    side: str,
    window: int,
    holding_days: int,
    delay_bars: int = 0,
) -> tuple[SpotAction, ...]:
    """Project delayed dislocations into non-stacking long/cash Spot actions."""
    _validate_observations(observations)
    _validate_spot_opens(spot_opens)
    if holding_days not in {1, 7} or delay_bars not in {0, 1}:
        raise MvrvDislocationError("holding_days must be 1 or 7 and delay_bars 0 or 1")
    candidates = {
        shock.source_day + timedelta(days=2, hours=1 + delay_bars): shock.source_day
        for shock in mvrv_shocks(observations, side=side, window=window)
    }
    source_gap_exits = {
        left.source_day + timedelta(days=3, hours=1)
        for left, right in pairwise(observations)
        if right.source_day - left.source_day != ONE_DAY
    }
    actions: list[SpotAction] = []
    held = False
    scheduled_exit: datetime | None = None
    source_day: datetime | None = None
    for index, opened in enumerate(spot_opens):
        was_held = held
        spot_gap = index > 0 and opened - spot_opens[index - 1] != ONE_HOUR
        source_gap = opened in source_gap_exits
        due = scheduled_exit is not None and opened >= scheduled_exit
        if held and (spot_gap or source_gap or due):
            reason = "SPOT_GAP" if spot_gap else "SOURCE_GAP" if source_gap else "PULSE_END"
            actions.append(SpotAction(opened, "SELL", source_day, reason))
            held = False
            scheduled_exit = None
            source_day = None
        if spot_gap or source_gap or held or was_held:
            continue
        candidate = candidates.get(opened)
        if candidate is not None:
            actions.append(SpotAction(opened, "BUY", candidate, "MVRV_DISLOCATION"))
            held = True
            source_day = candidate
            scheduled_exit = opened + timedelta(days=holding_days)
    return tuple(actions)


def _validate_observations(observations: tuple[MvrvObservation, ...]) -> None:
    for item in observations:
        if (
            item.source_day.tzinfo is None
            or item.source_day.utcoffset() != timedelta(0)
            or item.source_day.time() != datetime.min.time()
        ):
            raise MvrvDislocationError("source days must be UTC-aware midnights")
        if not item.mvrv.is_finite() or item.mvrv <= 0:
            raise MvrvDislocationError("MVRV values must be positive and finite")
    if any(left.source_day >= right.source_day for left, right in pairwise(observations)):
        raise MvrvDislocationError("source days must be unique and strictly ordered")


def _validate_spot_opens(spot_opens: tuple[datetime, ...]) -> None:
    if any(value.tzinfo is None or value.utcoffset() != timedelta(0) for value in spot_opens):
        raise MvrvDislocationError("Spot opens must be UTC-aware")
    if any(left >= right for left, right in pairwise(spot_opens)):
        raise MvrvDislocationError("Spot opens must be unique and strictly ordered")


def observation_from_api(time: str, value: str) -> MvrvObservation:
    """Parse exact API decimals without binary-float conversion."""
    source_day = datetime.fromisoformat(time.replace("Z", "+00:00"))
    return MvrvObservation(source_day, Decimal(value))
