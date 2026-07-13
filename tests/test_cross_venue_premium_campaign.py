"""Freeze and selection-barrier checks for D-075."""

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_cross_venue_btc_premium_campaign import (  # noqa: E402
    CAMPAIGN,
    OUTPUT_ROOT,
    _post_selection_reference,
    preflight,
)
from run_funding_pressure_campaign import SelectionBarrier  # noqa: E402


def test_cross_venue_campaign_contract_is_frozen_safe_and_complete() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    assert len(campaign["trial_roster"]) == 12
    assert campaign["safety"]["execution_authority"] == "NONE"
    assert campaign["safety"]["network"] == "PROHIBITED"
    assert campaign["selection"]["immutable_hashed_selection_required_before_phase_two"] is True
    assert campaign["gates"]["required_positive_periods_of_6"] == 5
    if OUTPUT_ROOT.exists():
        assert len(list(OUTPUT_ROOT.glob("campaign_result_*.json"))) == 1


def test_cross_venue_preflight_verifies_pins_and_data() -> None:
    if OUTPUT_ROOT.exists():
        assert len(list(OUTPUT_ROOT.glob("campaign_result_*.json"))) == 1
    else:
        assert preflight(require_clean=False)["data_verification"]["status"] == "PASS"


def test_cross_venue_reserve_cannot_run_without_hashed_selection() -> None:
    with pytest.raises(RuntimeError, match="selection artifact required"):
        _post_selection_reference(SelectionBarrier(), (), ())
