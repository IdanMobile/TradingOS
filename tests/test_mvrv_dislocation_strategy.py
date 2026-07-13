from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from tios.strategy.mvrv_dislocation import (
    MvrvDislocationError,
    MvrvObservation,
    mvrv_shocks,
    observation_from_api,
    project_mvrv_pulses,
)
from tios.strategy.validator import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "strategies/research/btc-mvrv-dislocation/canonical_strategy_spec.yaml"


def _observations(values: tuple[str, ...]) -> tuple[MvrvObservation, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        MvrvObservation(start + timedelta(days=index), Decimal(value))
        for index, value in enumerate(values)
    )


def test_spec_is_complete_and_has_no_execution_authority() -> None:
    payload = yaml.safe_load(SPEC.read_text())
    assert validate(payload).verdict == "VALID"
    assert payload["risk"]["execution_authority"] == "NONE"


def test_high_low_and_zero_variance_semantics() -> None:
    assert mvrv_shocks(_observations(("1", "1", "1", "4")), side="HIGH", window=3) == ()
    assert len(mvrv_shocks(_observations(("1", "1.1", ".9", "4")), side="HIGH", window=3)) == 1
    assert len(mvrv_shocks(_observations(("1", "1.1", ".9", ".2")), side="LOW", window=3)) == 1


def test_two_day_lag_nonextension_and_one_day_exit() -> None:
    observations = _observations(("1", "1.1", ".9", "4", "5"))
    start = datetime(2026, 1, 6, tzinfo=UTC)
    opens = tuple(start + timedelta(hours=index) for index in range(50))
    actions = project_mvrv_pulses(observations, opens, side="HIGH", window=3, holding_days=1)
    assert [(item.open_time, item.side) for item in actions] == [
        (datetime(2026, 1, 6, 1, tzinfo=UTC), "BUY"),
        (datetime(2026, 1, 7, 1, tzinfo=UTC), "SELL"),
    ]


def test_bad_inputs_fail_closed_and_api_decimal_is_exact() -> None:
    with pytest.raises(MvrvDislocationError, match="UTC-aware midnights"):
        mvrv_shocks((MvrvObservation(datetime(2026, 1, 1), Decimal(1)),), side="HIGH", window=3)
    observation = observation_from_api("2026-01-01T00:00:00.000000000Z", "1.123456789012345678")
    assert observation.mvrv == Decimal("1.123456789012345678")
