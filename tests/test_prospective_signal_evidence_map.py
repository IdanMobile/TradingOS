from pathlib import Path

import yaml


def test_prospective_signal_evidence_map_preserves_sample_and_authority_boundaries() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = yaml.safe_load(
        (root / "research/PROSPECTIVE_SIGNAL_EVIDENCE_PRODUCER_MAP_V1.yaml").read_text()
    )

    assert payload["execution_authority"] == "NONE"
    assert payload["paper_orders"] == payload["live_orders"] == "DISABLED"
    boundaries = payload["semantic_boundaries"]
    assert boundaries["observation_windows_are_trials"] is False
    assert boundaries["observation_windows_are_samples"] is True
    assert boundaries["signal_is_strategy_version"] is False
    assert boundaries["signal_can_create_order"] is False
    blockers = {row["code"]: row for row in payload["blockers"]}
    assert blockers["WARMUP_SAMPLE_INCOMPLETE"]["release_condition"].startswith("8640")
    assert blockers["CAMPAIGN_TRIAL_POPULATION_UNDECLARED"]["current_evidence"].endswith(
        "zero declared trials"
    )
    assert blockers["VALIDATED_ALPHA_STRATEGY_MISSING"]["earliest"].endswith(
        "never implied by signal validation"
    )
    assert all(row["producer"] and row["verifier"] for row in blockers.values())
