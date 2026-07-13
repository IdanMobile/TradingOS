"""Prospective association/overlay preregistration is complete and cannot self-promote."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_ASSOCIATION_OVERLAY_CAMPAIGN_V1.yaml"
VERIFIER = ROOT / "scripts/verify_prospective_association_campaign.py"


def test_campaign_freezes_population_statistics_and_strategy_boundary() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())

    assert campaign["status"] == "FROZEN_UNRUN_WAITING_MINIMA"
    assert campaign["execution_authority"] == "NONE"
    assert campaign["warmup_analysis"] == "PROHIBITED"
    assert campaign["sealed_v2_holdout_access"] == "PROHIBITED"
    trials = campaign["declared_trial_population"]
    assert trials["terminal_trial_count"] == 3
    assert trials["selection_trial_count"] == 1
    assert [row["trial_id"] for row in trials["trials"]] == [
        "ASSOC-1H",
        "ASSOC-6H",
        "ASSOC-24H",
    ]
    assert campaign["statistics"]["primary_test"]["trial_id"] == "ASSOC-6H"
    assert campaign["statistics"]["secondary_tests"]["rescue_primary"] is False
    assert campaign["statistics"]["multiple_testing"]["g10_status"] == (
        "CANNOT_PASS_STRATEGY_G10_ASSOCIATION_ONLY"
    )
    overlay = campaign["overlay_child_boundary"]
    assert overlay["parent_can_evaluate_overlay"] is False
    assert overlay["current_status"] == "BLOCKED_VALIDATED_ALPHA_STRATEGY_MISSING"
    assert overlay["overlay_rule"]["existing_positions"].startswith("unchanged")
    assert "new exact human approval" in overlay["child_non_authority"]


def test_campaign_frozen_input_hashes_match_repository() -> None:
    campaign = yaml.safe_load(CAMPAIGN.read_text())
    for item in campaign["frozen_inputs"].values():
        path = ROOT / item["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


def test_preflight_waits_without_reading_warmup_outcomes() -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--root", str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    preflight = json.loads(result.stdout)
    assert preflight["status"] == "WAITING"
    assert preflight["declared_trial_count"] == 3
    assert preflight["metrics_computed"] is False
    assert preflight["label_files_read"] == 0
    assert preflight["warmup_outcomes_read"] is False
    assert preflight["execution_authority"] == "NONE"
    assert preflight["order_creation"] is False
    assert "WARMUP_SAMPLE_INCOMPLETE" in preflight["blockers"]
    assert "VALIDATED_ALPHA_STRATEGY_MISSING" in preflight["blockers"]
