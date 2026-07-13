"""Governed lifecycle checks for the canonical V2 campaign."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "research/CANONICAL_BASELINE_G10_CAMPAIGN_V2.yaml"
sys.path.insert(0, str(ROOT / "scripts"))

from run_canonical_baseline_campaign import (  # noqa: E402
    _metadata,
    preflight,
    sha256,
    verify_campaign,
)

from tios.evidence import validate_substantive_research_metadata  # noqa: E402


def test_v2_preflight_or_completed_evidence_verifies() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    if campaign["status"] == "PREREGISTERED_NOT_RUN":
        context = preflight(CAMPAIGN, require_clean=False)
        assert context["campaign_sha256"] == sha256(CAMPAIGN)
        assert context["campaign"]["method"]["raw_trial_count"] == 67
        assert context["campaign"]["pre_freeze_exposure"]["status"].startswith(
            "IMPLEMENTATION_SMOKE"
        )
    else:
        assert campaign["status"] == "COMPLETED"
        assert verify_campaign(CAMPAIGN).is_file()


def test_each_v2_family_can_emit_required_metadata() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    context = {
        "campaign": campaign,
        "campaign_path": CAMPAIGN,
        "campaign_sha256": sha256(CAMPAIGN),
        "git_commit": "b" * 40,
        "git_dirty": False,
    }
    for family in ("b2", "b3", "b4"):
        metadata = _metadata(
            context=context,
            family=family,
            output_sha256="a" * 64,
            all_trials_ref=f"artifacts/validation/campaigns/test/{family}.json",
            generated_at="2026-07-13T12:00:00+00:00",
        )
        assert validate_substantive_research_metadata(metadata) is None
        assert metadata["strategy"]["implementation_conformance"] == (
            "CANONICAL_RULES_NEXT_ADJACENT_OPEN_FLOAT64"
        )
        assert metadata["execution_authority"] == "NONE"
        assert metadata["promotion_eligible"] is False


def test_campaign_runner_has_no_network_or_order_path() -> None:
    source = (ROOT / "scripts/run_canonical_baseline_campaign.py").read_text()
    assert '"--fetch"' not in source
    assert "urlopen" not in source
    assert "api_key" not in source.lower()
    assert "create_order" not in source
