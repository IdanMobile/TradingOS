import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_funding_pressure_campaign import SelectionBarrier  # noqa: E402
from run_mvrv_campaign import CAMPAIGN, OUTPUT_ROOT, _post_selection_reference  # noqa: E402


def test_campaign_contract_is_frozen_safe_complete_and_unrun() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    assert len(campaign["trial_roster"]) == 12
    assert campaign["safety"]["execution_authority"] == "NONE"
    assert campaign["safety"]["network"] == "PROHIBITED"
    assert campaign["selection"]["immutable_hashed_selection_required_before_phase_two"] is True
    assert not OUTPUT_ROOT.exists()


def test_reserve_cannot_run_without_hashed_selection() -> None:
    with pytest.raises(RuntimeError, match="selection artifact required"):
        _post_selection_reference(SelectionBarrier(), (), ())
