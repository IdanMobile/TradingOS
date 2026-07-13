"""The frozen G10 campaign has an executable, fail-closed evidence lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "research/BASELINE_G10_SEARCH_CAMPAIGN_V1.yaml"
sys.path.insert(0, str(ROOT / "scripts"))

from run_preregistered_g10_campaign import (  # noqa: E402
    _family_metadata,
    preflight,
    sha256,
    verify_campaign,
)

from tios.evidence import validate_substantive_research_metadata  # noqa: E402


def test_campaign_preflight_or_completed_evidence_verifies() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    if campaign["status"] == "PREREGISTERED_NOT_RUN":
        context = preflight(CAMPAIGN, require_clean=False)
        assert context["campaign_sha256"] == sha256(CAMPAIGN)
        assert context["campaign"]["method"]["raw_trial_count"] == 66
    else:
        assert campaign["status"] == "COMPLETED"
        assert verify_campaign(CAMPAIGN).is_file()


def test_each_family_can_emit_the_required_metadata_contract() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    context = {
        "campaign": campaign,
        "campaign_path": CAMPAIGN,
        "campaign_sha256": sha256(CAMPAIGN),
        "git_commit": "b" * 40,
        "git_dirty": False,
    }
    for family in ("b2", "b3", "b4"):
        metadata = _family_metadata(
            context=context,
            family=family,
            output_sha256="a" * 64,
            all_trials_ref=f"artifacts/validation/campaigns/test/{family}.json",
            generated_at="2026-07-13T12:00:00+00:00",
        )
        assert validate_substantive_research_metadata(metadata) is None
        assert metadata["strategy"]["implementation_conformance"] == (
            "LEGACY_ACCELERATOR_PROXY_NOT_CANONICAL"
        )
        assert metadata["execution_authority"] == "NONE"
