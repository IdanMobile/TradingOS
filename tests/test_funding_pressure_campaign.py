import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_funding_pressure_campaign import (  # noqa: E402
    CAMPAIGN,
    SelectionBarrier,
    _post_selection_reference,
    preflight,
)


def test_funding_campaign_is_frozen_safe_and_complete() -> None:
    assert yaml.safe_load(CAMPAIGN.read_text())["schema"].endswith("campaign-v2")
    campaign = preflight(require_clean=False)["campaign"]
    assert campaign["status"] == "PREREGISTERED_NOT_RUN"
    assert campaign["safety"] == {
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "orders": "DISABLED",
        "network": "PROHIBITED",
        "credentials_required": False,
        "sealed_v2_holdout_access": "PROHIBITED",
        "rejected_calendar_reserve_access": "PROHIBITED",
    }
    assert len(campaign["trial_roster"]) == 12
    assert campaign["method"]["raw_statistical_trial_count"] == 12
    assert len(campaign["method"]["cost_scenarios"]) == 6
    assert set(campaign["hard_gates"]) == {
        f"G{index}_{name}"
        for index, name in [
            (1, "DATA_PROVENANCE"),
            (2, "CANONICAL_IDENTITY"),
            (3, "CAUSAL_GOLDENS"),
            (4, "INDEPENDENT_REPRODUCTION"),
            (5, "AFTER_COST_ECONOMICS"),
            (6, "CHRONOLOGICAL_OOS"),
            (7, "SAMPLE_AND_CLOCK_ROBUSTNESS"),
            (8, "REGIME_AND_TAIL"),
            (9, "BENCHMARK_AND_OPPORTUNITY"),
            (10, "MULTIPLE_TESTING"),
            (11, "INDEPENDENT_RISK_SUPERVISOR"),
        ]
    }


def test_funding_campaign_preflight_verifies_without_scoring() -> None:
    result = preflight(require_clean=False)
    assert result["data_verification"]["status"] == "PASS"
    assert result["data_verification"]["network_allowed"] is False


def test_phase_two_fails_before_selection_artifact_exists() -> None:
    with pytest.raises(RuntimeError, match="selection artifact required"):
        _post_selection_reference(SelectionBarrier(), (), ())


def test_selection_barrier_rejects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "selection.json"
    path.write_text(json.dumps({"selected_trial": {"polarity": "CONTINUATION"}}))
    barrier = SelectionBarrier(path, "0" * 64)
    with pytest.raises(RuntimeError, match="hash mismatch"):
        barrier.require()
