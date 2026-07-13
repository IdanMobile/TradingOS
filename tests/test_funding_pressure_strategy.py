from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from tios.strategy.funding_pressure import (
    FundingObservation,
    FundingPressureError,
    eligibility_changes,
    observation_from_milliseconds,
    project_to_spot_opens,
)
from tios.strategy.validator import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "strategies/research/funding-pressure-spot/canonical_strategy_spec.yaml"


def _observation(hour: int, rate: str) -> FundingObservation:
    return FundingObservation(datetime(2026, 1, 1, hour, tzinfo=UTC), 8, Decimal(rate))


def test_funding_pressure_spec_is_complete_and_non_executable() -> None:
    payload = yaml.safe_load(SPEC.read_text())
    assert validate(payload).verdict == "VALID"
    assert payload["risk"]["execution_authority"] == "NONE"


def test_continuation_uses_complete_window_and_strict_threshold() -> None:
    observations = tuple(
        _observation(hour, rate)
        for hour, rate in enumerate(("0.0001", "0.0001", "0.0001", "-0.0004"))
    )
    changes = eligibility_changes(
        observations, polarity="CONTINUATION", lookback=3, threshold=Decimal("0.0001")
    )
    assert changes == ()


def test_contrarian_changes_state_and_preserves_exact_observation_time() -> None:
    observations = tuple(
        _observation(hour, rate)
        for hour, rate in enumerate(("-0.0002", "-0.0002", "-0.0002", "0.001"))
    )
    changes = eligibility_changes(
        observations, polarity="CONTRARIAN", lookback=3, threshold=Decimal("0.0001")
    )
    assert [(item.observed_at.hour, item.long_eligible) for item in changes] == [
        (2, True),
        (3, False),
    ]


def test_exact_millisecond_observation_fills_only_at_strictly_later_open() -> None:
    observation = observation_from_milliseconds(1767225600002, 8, Decimal("0.001"))
    changes = eligibility_changes(
        (observation,), polarity="CONTINUATION", lookback=1, threshold=Decimal(0)
    )
    opens = (
        datetime(2026, 1, 1, 0, tzinfo=UTC),
        datetime(2026, 1, 1, 1, tzinfo=UTC),
    )
    actions = project_to_spot_opens(changes, opens)
    assert actions[0].open_time == opens[1]
    assert actions[0].observed_at.microsecond == 2000


def test_missing_expected_open_expires_pending_change() -> None:
    changes = eligibility_changes(
        (_observation(0, "0.001"),),
        polarity="CONTINUATION",
        lookback=1,
        threshold=Decimal(0),
    )
    assert project_to_spot_opens(changes, (datetime(2026, 1, 1, 2, tzinfo=UTC),)) == ()


def test_invalid_order_and_parameters_fail_closed() -> None:
    with pytest.raises(FundingPressureError, match="strictly ordered"):
        eligibility_changes(
            (_observation(1, "0.1"), _observation(0, "0.1")),
            polarity="CONTINUATION",
            lookback=1,
            threshold=Decimal(0),
        )
    with pytest.raises(FundingPressureError, match="positive integer"):
        eligibility_changes(
            (_observation(0, "0.1"),),
            polarity="CONTINUATION",
            lookback=0,
            threshold=Decimal(0),
        )


def test_spot_opens_must_be_strictly_ordered() -> None:
    repeated = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(FundingPressureError, match="strictly ordered"):
        project_to_spot_opens((), (repeated, repeated + timedelta(0)))
