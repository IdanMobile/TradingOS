from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from tios.strategy.cftc_positioning import (
    CftcPositioningError,
    PositioningObservation,
    positioning_shocks,
    project_positioning_pulses,
)
from tios.strategy.validator import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "strategies/research/cftc-btc-positioning/canonical_strategy_spec.yaml"


def _observations(current: str = "0.8") -> tuple[PositioningObservation, ...]:
    start = datetime(2025, 1, 7, tzinfo=UTC)
    values = ("-0.1", "0.1") * 6 + ("-0.1", current)
    return tuple(
        PositioningObservation(
            start + timedelta(days=7 * index),
            start + timedelta(days=7 * index + 8),
            Decimal(value),
        )
        for index, value in enumerate(values)
    )


def test_spec_is_complete_and_has_no_execution_authority() -> None:
    payload = yaml.safe_load(SPEC.read_text())
    assert validate(payload).verdict == "VALID"
    assert payload["risk"]["execution_authority"] == "NONE"


def test_high_low_and_zero_variance_semantics() -> None:
    high = positioning_shocks(
        _observations(),
        interpretation="ALIGNED_HIGH",
        baseline_weeks=13,
        threshold=Decimal("0.5"),
    )
    low = positioning_shocks(
        _observations("-0.8"),
        interpretation="CONTRARIAN_LOW",
        baseline_weeks=13,
        threshold=Decimal("0.5"),
    )
    assert len(high) == len(low) == 1


def test_strict_later_open_nonextension_and_seven_day_exit() -> None:
    observations = _observations()
    available = observations[-1].available_at
    opens = tuple(available + timedelta(hours=index) for index in range(170))
    actions = project_positioning_pulses(
        observations,
        opens,
        interpretation="ALIGNED_HIGH",
        baseline_weeks=13,
        threshold=Decimal("0.5"),
    )
    assert [(item.open_time, item.side) for item in actions] == [
        (available + timedelta(hours=1), "BUY"),
        (available + timedelta(hours=169), "SELL"),
    ]


def test_bad_inputs_fail_closed() -> None:
    bad = PositioningObservation(datetime(2025, 1, 1), datetime(2025, 1, 9), Decimal("0"))
    with pytest.raises(CftcPositioningError, match="UTC-aware"):
        positioning_shocks(
            (bad,),
            interpretation="ALIGNED_HIGH",
            baseline_weeks=13,
            threshold=Decimal("0.5"),
        )


def test_future_observation_cannot_change_prior_actions() -> None:
    observations = _observations()
    available = observations[-1].available_at
    opens = tuple(available + timedelta(hours=index) for index in range(170))
    kwargs = {
        "interpretation": "ALIGNED_HIGH",
        "baseline_weeks": 13,
        "threshold": Decimal("0.5"),
    }
    before = project_positioning_pulses(observations, opens, **kwargs)
    future = PositioningObservation(
        observations[-1].report_date + timedelta(days=7),
        observations[-1].available_at + timedelta(days=7),
        Decimal("-0.9"),
    )
    after = project_positioning_pulses(observations + (future,), opens, **kwargs)
    assert before == after
