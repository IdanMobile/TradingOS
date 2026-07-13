"""The canonical V2 campaign is frozen, bounded, and fail-closed."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / "research/CANONICAL_BASELINE_G10_CAMPAIGN_V2.yaml"


def _campaign() -> dict[str, object]:
    value = yaml.safe_load(CAMPAIGN.read_text())
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v2_scope_and_safety_boundary_are_frozen() -> None:
    campaign = _campaign()
    assert campaign["status"] in {"PREREGISTERED_NOT_RUN", "COMPLETED"}
    assert campaign["execution_authority"] == "NONE"
    assert campaign["network_during_campaign"] == "PROHIBITED"
    assert campaign["credentials_required"] is False
    assert campaign["venue_connection"] == "NONE"
    assert campaign["orders"] == "DISABLED"
    assert campaign["promotion_eligible"] is campaign["winner_selected"] is False
    exposure = campaign["pre_freeze_exposure"]
    assert exposure["status"] == "IMPLEMENTATION_SMOKE_ACCESSED_FULL_HISTORICAL_DATA"
    assert exposure["retained_campaign_evidence"] == "NONE"
    assert "not an unseen" in exposure["effect"]
    roster = campaign["candidate_roster"]
    assert [item["raw_trial_count"] for item in roster] == [35, 16, 16]
    assert (
        sum(item["raw_trial_count"] for item in roster)
        == campaign["method"]["raw_trial_count"]
        == 67
    )
    assert campaign["search_lineage"]["upstream_family_admission_complete"] is False


def test_v2_freezes_canonical_execution_semantics() -> None:
    model = _campaign()["scope"]["execution_model"]
    assert model == {
        "decision_time": "BAR_CLOSE_T",
        "fill_time": "EXACTLY_ADJACENT_BAR_OPEN_T_PLUS_1",
        "adjacency_required": "5m",
        "pending_signal_across_gap": "EXPIRE",
        "held_position_across_gap": "CARRY_WITHOUT_SYNTHETIC_FILL",
        "indicator_after_gap": "RESET_AND_REQUIRE_FULL_CONTIGUOUS_WARMUP",
        "b2_entry": "PERSISTENT_FAST_SMA_ABOVE_SLOW_SMA_WHEN_FLAT",
        "b2_exit": "FAST_SMA_BELOW_SLOW_SMA_WHEN_HELD",
        "b3_std": "POPULATION_DDOF_0",
        "b3_entry": "CLOSE_STRICTLY_BELOW_LOWER_BAND",
        "b3_exit": "CLOSE_AT_OR_ABOVE_MIDDLE_BAND",
        "b4_entry": "CLOSE_ABOVE_PRIOR_HIGH_EXCLUDING_CURRENT_BAR",
        "b4_exit": "CLOSE_BELOW_EXIT_SMA",
        "simultaneous_raw_entry_and_exit": "FLAT_ENTERS_HELD_EXITS",
        "final_bar_signal": "NO_FILL",
        "final_open_position": "MARK_TO_FINAL_CLOSE_NO_FORCED_LIQUIDATION",
        "direction": "LONG_ONLY",
        "sizing": "FULL_AVAILABLE_CASH",
        "initial_cash": 1000.0,
    }
    assert _campaign()["scope"]["semantic_conformance"] == (
        "CANONICAL_RULES_NEXT_ADJACENT_OPEN_FLOAT64"
    )


def test_v2_cost_surface_and_primary_selection_cell_are_frozen() -> None:
    cost = _campaign()["method"]["cost_model"]
    scenarios = {
        item["id"]: (item["fee_rate_per_side"], item["slippage_bps_per_side"])
        for item in cost["scenarios"]
    }
    assert cost["selection_scenario"] == cost["primary_economic_scenario"] == "F1/S1"
    assert scenarios == {
        "F0/S0": (0.0, 0),
        "F1/S1": (0.001, 1),
        "F1/S2": (0.001, 5),
        "F1/S3": (0.001, 10),
        "F2/S2": (0.0015, 5),
        "F2/S3": (0.0015, 10),
    }


def test_v2_walk_forward_is_historical_and_prospective_holdout_is_future() -> None:
    method = _campaign()["method"]
    walk = method["walk_forward"]
    assert walk["evidence_label"] == "HISTORICAL_PSEUDO_OOS"
    assert walk["boundary_gap_bars"] == 1
    assert walk["test_position_start"] == "FLAT"
    assert [fold["id"] for fold in walk["folds"]] == [
        "WF-2022",
        "WF-2023",
        "WF-2024",
        "WF-2025",
        "WF-2026-H1",
    ]
    for fold in walk["folds"]:
        assert fold["selection_end_utc"] < fold["gap_utc"] < fold["test_start_utc"]
        assert fold["test_start_utc"] <= fold["test_end_utc"]
    holdout = method["prospective_holdout"]
    assert holdout["status"] == "SEALED_WAITING_FOR_FUTURE_DATA"
    assert holdout["observation_start_utc"] > holdout["freeze_date_utc"]
    assert holdout["evaluation_not_before_utc"] > holdout["observation_start_utc"]
    assert holdout["minimum_observation_days"] >= 184
    assert holdout["current_campaign_consumes_holdout"] is False


def test_v2_retains_structural_zero_trade_trials_fail_closed() -> None:
    b3 = _campaign()["candidate_roster"][1]
    assert b3["family"] == "b3"
    assert b3["structural_zero_trade_trials"] == [
        {"window": 3, "deviation": 1.5},
        {"window": 3, "deviation": 2.0},
        {"window": 5, "deviation": 2.0},
    ]
    assert "undefined" in b3["retention_policy"].lower()
    assert "silently removed" in b3["retention_policy"].lower()


def test_v2_pins_every_declared_input() -> None:
    campaign = _campaign()
    dataset = campaign["scope"]["dataset"]
    engine = campaign["scope"]["engine"]
    implementation = campaign["implementation"]
    declarations = [
        (dataset["file"], dataset["file_sha256"]),
        (dataset["source_manifest"], dataset["source_manifest_sha256"]),
        (dataset["restore_script"], dataset["restore_script_sha256"]),
        (engine["environment_manifest"], engine["environment_manifest_sha256"]),
        *[
            (item["canonical_spec"], item["canonical_spec_file_sha256"])
            for item in campaign["candidate_roster"]
        ],
        *[
            (implementation[key], implementation[f"{key}_sha256"])
            for key in (
                "extractor",
                "evaluator",
                "method_module",
                "provenance_validator",
                "campaign_runner",
                "method_sources",
            )
        ],
    ]
    assert all(Path(path).is_relative_to(Path(".")) for path, _ in declarations)
    assert all(_sha256(ROOT / path) == expected for path, expected in declarations)


def test_v2_tracked_contracts_have_no_machine_absolute_paths() -> None:
    for path in (
        CAMPAIGN,
        ROOT / "research/CANONICAL_BASELINE_METHOD_SOURCES_V2.yaml",
    ):
        assert "/Users/" not in path.read_text()
