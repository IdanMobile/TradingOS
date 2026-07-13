from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from tios.strategy.transaction_activity import (
    ActivityObservation,
    TransactionActivityError,
    activity_shocks,
    observation_from_unix_seconds,
    project_activity_pulses,
)
from tios.strategy.validator import validate

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "strategies/research/btc-tx-activity/canonical_strategy_spec.yaml"


def _observations(counts: tuple[int, ...]) -> tuple[ActivityObservation, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return tuple(
        ActivityObservation(start + timedelta(days=i), count) for i, count in enumerate(counts)
    )


def test_spec_is_complete_and_has_no_execution_authority() -> None:
    payload = yaml.safe_load(SPEC.read_text())
    assert validate(payload).verdict == "VALID"
    assert payload["risk"]["execution_authority"] == "NONE"


def test_high_and_low_use_strict_population_zscore() -> None:
    high = activity_shocks(_observations((100, 100, 100, 400)), side="HIGH", window=3)
    assert high == ()  # zero prior variance is no signal
    high = activity_shocks(_observations((100, 110, 90, 400)), side="HIGH", window=3)
    low = activity_shocks(_observations((100, 110, 90, 20)), side="LOW", window=3)
    assert len(high) == len(low) == 1
    assert high[0].z_score > 1 and low[0].z_score < -1


def test_source_gap_resets_complete_window() -> None:
    values = list(_observations((100, 110, 90, 400, 500)))
    values[2] = ActivityObservation(values[2].source_day + timedelta(days=1), 90)
    values.pop(3)
    assert activity_shocks(tuple(values), side="HIGH", window=3) == ()


def test_pulse_uses_two_day_lag_does_not_extend_and_exits_after_24h() -> None:
    observations = _observations((100, 110, 90, 400, 500))
    start = datetime(2026, 1, 6, tzinfo=UTC)
    opens = tuple(start + timedelta(hours=i) for i in range(50))
    actions = project_activity_pulses(observations, opens, side="HIGH", window=3, holding_days=1)
    assert [(a.open_time, a.side) for a in actions] == [
        (datetime(2026, 1, 6, 1, tzinfo=UTC), "BUY"),
        (datetime(2026, 1, 7, 1, tzinfo=UTC), "SELL"),
    ]


def test_missing_expected_fill_expires_and_bad_input_fails_closed() -> None:
    observations = _observations((100, 110, 90, 400))
    assert (
        project_activity_pulses(
            observations,
            (datetime(2026, 1, 6, 2, tzinfo=UTC),),
            side="HIGH",
            window=3,
            holding_days=1,
        )
        == ()
    )
    with pytest.raises(TransactionActivityError, match="UTC-aware midnights"):
        activity_shocks((ActivityObservation(datetime(2026, 1, 1), 1),), side="HIGH", window=3)
    with pytest.raises(TransactionActivityError, match="integer-valued"):
        observation_from_unix_seconds(1767225600, 1.5)
