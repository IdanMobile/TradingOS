"""External replay candidates are canonical but not execution authority."""

from __future__ import annotations

from pathlib import Path

import yaml

from tios.strategy.validator import validate_yaml

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "strategies" / "external" / "3commas-dca-config"


def test_3commas_dca_external_spec_validates_with_declared_ambiguities() -> None:
    report = validate_yaml((CANDIDATE / "canonical_strategy_spec.yaml").read_text())
    assert report.verdict == "VALID_WITH_AMBIGUITIES"
    assert not report.errors
    assert any("no native multi-fill DCA primitive" in item for item in report.ambiguities)


def test_3commas_dca_external_candidate_is_not_execution_authority() -> None:
    candidate = yaml.safe_load((CANDIDATE / "replay_candidate.yaml").read_text())
    assert candidate["status"] == "LOCAL_REPLAY_RETAINED"
    assert candidate["validation_state"] == "UNVALIDATED"
    assert candidate["promotion_eligible"] is False
    assert candidate["execution_authority"] == "NONE"
    assert "platform_bot_execution" in candidate["prohibited"]
    assert "order_routing" in candidate["prohibited"]


def test_3commas_dca_external_source_record_inherits_no_profit_claim() -> None:
    source = yaml.safe_load((CANDIDATE / "source_record.yaml").read_text())
    license_record = yaml.safe_load((CANDIDATE / "license_record.yaml").read_text())
    assert source["profit_claims_inherited"] is False
    assert source["approval_eligible"] is False
    assert source["execution_authority"] == "NONE"
    assert license_record["reuse_allowed"] == "adapted_metadata_only"
    assert "credential_request" in license_record["prohibited"]
