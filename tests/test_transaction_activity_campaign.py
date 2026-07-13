import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_funding_pressure_campaign import SelectionBarrier  # noqa: E402
from run_transaction_activity_campaign import (  # noqa: E402
    OUTPUT_ROOT,
    _post_selection_reference,
    preflight,
)


def test_campaign_is_frozen_safe_complete_and_unrun() -> None:
    context = preflight(require_clean=False)
    campaign = context["campaign"]
    assert len(campaign["trial_roster"]) == 12
    assert campaign["safety"]["execution_authority"] == "NONE"
    assert campaign["safety"]["network"] == "PROHIBITED"
    assert campaign["selection"]["immutable_hashed_selection_required_before_phase_two"] is True
    assert not OUTPUT_ROOT.exists()


def test_reserve_cannot_run_without_hashed_selection() -> None:
    with pytest.raises(RuntimeError, match="selection artifact required"):
        _post_selection_reference(SelectionBarrier(), (), ())
