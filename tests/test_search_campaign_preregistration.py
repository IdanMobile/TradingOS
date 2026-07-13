"""The next bounded G10 reproduction is frozen before any campaign run."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "research/BASELINE_G10_SEARCH_CAMPAIGN_V1.yaml"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_campaign_scope_counts_and_safety_are_preregistered() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    assert campaign["status"] == "PREREGISTERED_NOT_RUN"
    assert campaign["execution_authority"] == "NONE"
    assert campaign["promotion_eligible"] is campaign["winner_selected"] is False
    roster = campaign["candidate_roster"]
    assert [item["raw_trial_count"] for item in roster] == [34, 16, 16]
    assert sum(item["raw_trial_count"] for item in roster) == campaign["method"]["raw_trial_count"]
    assert campaign["method"]["metric_applies_to"] == [
        "candidate_selection",
        "PBO_IS",
        "PBO_OOS",
        "DSR",
    ]
    assert campaign["required_output_contract"]["upstream_family_admission_complete"] is False


def test_campaign_pins_every_declared_file() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    declarations = [
        (campaign["scope"]["dataset"]["file"], campaign["scope"]["dataset"]["file_sha256"]),
        (
            campaign["scope"]["dataset"]["manifest"],
            campaign["scope"]["dataset"]["manifest_sha256"],
        ),
        (
            campaign["scope"]["engine"]["environment_manifest"],
            campaign["scope"]["engine"]["environment_manifest_sha256"],
        ),
        *[
            (item["canonical_spec"], item["canonical_spec_file_sha256"])
            for item in campaign["candidate_roster"]
        ],
        (
            campaign["implementation"]["extractor"],
            campaign["implementation"]["extractor_sha256"],
        ),
        (
            campaign["implementation"]["method_module"],
            campaign["implementation"]["method_module_sha256"],
        ),
    ]
    assert all(_sha256(ROOT / path) == expected for path, expected in declarations)
