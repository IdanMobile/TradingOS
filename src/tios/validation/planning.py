"""Small deterministic planners for the validation blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from tios.core_types.engine import MANDATORY_GRID


@dataclass(frozen=True)
class ChronologicalSplit:
    development_start: datetime
    development_end: datetime
    validation_start: datetime
    validation_end: datetime
    holdout_start: datetime
    holdout_end: datetime


def chronological_split(
    coverage_start: datetime,
    coverage_end: datetime,
    development_fraction: Decimal = Decimal("0.6"),
    validation_fraction: Decimal = Decimal("0.2"),
) -> ChronologicalSplit:
    """Materialize dates before optimization; no random shuffle is possible."""
    if coverage_start.tzinfo is None or coverage_end.tzinfo is None:
        raise ValueError("coverage dates must be timezone-aware")
    if not (Decimal(0) < development_fraction < Decimal(1)):
        raise ValueError("development_fraction must be between 0 and 1")
    if not (Decimal(0) < validation_fraction < Decimal(1)):
        raise ValueError("validation_fraction must be between 0 and 1")
    if development_fraction + validation_fraction >= 1:
        raise ValueError("development and validation fractions must leave a holdout")
    duration = coverage_end - coverage_start
    dev_end = coverage_start + duration * float(development_fraction)
    val_start = dev_end + timedelta(microseconds=1)
    val_end = coverage_start + duration * float(development_fraction + validation_fraction)
    holdout_start = val_end + timedelta(microseconds=1)
    return ChronologicalSplit(
        coverage_start.astimezone(UTC),
        dev_end.astimezone(UTC),
        val_start.astimezone(UTC),
        val_end.astimezone(UTC),
        holdout_start.astimezone(UTC),
        coverage_end.astimezone(UTC),
    )


def walk_forward_windows(
    start: datetime, end: datetime, train_days: int, test_days: int, step_days: int
) -> tuple[dict[str, datetime], ...]:
    if min(train_days, test_days, step_days) <= 0:
        raise ValueError("walk-forward window sizes must be positive")
    windows = []
    cursor = start
    while cursor + timedelta(days=train_days + test_days) <= end:
        train_end = cursor + timedelta(days=train_days)
        windows.append(
            {
                "train_start": cursor,
                "train_end": train_end,
                "test_start": train_end,
                "test_end": train_end + timedelta(days=test_days),
            }
        )
        cursor += timedelta(days=step_days)
    return tuple(windows)


def parameter_neighborhood(
    params: dict[str, Decimal], radius: Decimal = Decimal("1")
) -> tuple[dict[str, Decimal], ...]:
    if radius < 0:
        raise ValueError("radius must be non-negative")
    return tuple(
        {**params, key: value + delta}
        for key, value in params.items()
        for delta in (-radius, Decimal(0), radius)
    )


def compare_to_baselines(candidate: Decimal, baselines: dict[str, Decimal]) -> dict[str, Any]:
    return {
        "candidate": str(candidate),
        "baselines": {name: str(value) for name, value in baselines.items()},
        "beats_all": all(candidate > value for value in baselines.values()),
    }


def mandatory_grid_ids() -> tuple[str, ...]:
    return tuple(scenario.scenario_id for scenario in MANDATORY_GRID)
