from datetime import UTC, datetime, timedelta
from decimal import Decimal

from tios.validation import (
    CostObservation,
    LeakageEvidence,
    MultipleTestingEvidence,
    ReproducibilityEvidence,
    SemanticEvidence,
    TimestampEvidence,
    evaluate_cost_hard_fail,
    evaluate_g1,
    evaluate_g2,
    evaluate_g3,
    evaluate_g4,
    evaluate_g10_retention_evidence,
)

T0 = datetime(2025, 1, 1, tzinfo=UTC)


def g1_fixture(**overrides: object) -> ReproducibilityEvidence:
    values: dict[str, object] = {
        "code_commit": "abc123",
        "dataset_id": "DS-test",
        "dataset_hash": "hash",
        "engine": "synthetic",
        "engine_version": "1.0",
        "parameters": {"lookback": 20},
        "fees_slippage": {"scenario": "F1/S1"},
        "seed": 7,
        "first_fields": {"trades": 2, "return": Decimal("0.12")},
        "rerun_fields": {"trades": 2, "return": Decimal("0.12000001")},
        "tolerance": Decimal("0.000001"),
    }
    values.update(overrides)
    return ReproducibilityEvidence(**values)  # type: ignore[arg-type]


def test_g1_passes_deterministic_replay() -> None:
    assert evaluate_g1(g1_fixture()).status == "PASS"


def test_g1_fails_missing_provenance_and_replay_mismatch() -> None:
    result = evaluate_g1(
        g1_fixture(code_commit="", rerun_fields={"trades": 3, "return": Decimal("0.12")})
    )
    assert result.status == "FAIL"
    assert result.hard_fail
    assert "missing code_commit" in result.reasons
    assert "rerun mismatch: trades" in result.reasons


def test_g2_passes_and_reports_allowed_gap() -> None:
    result = evaluate_g2(TimestampEvidence((T0, T0 + timedelta(minutes=10)), interval_seconds=300))
    assert result.status == "PASS"
    assert result.details["missing_interval_count"] == 1


def test_g2_fails_duplicate_and_future_feature() -> None:
    result = evaluate_g2(
        TimestampEvidence((T0, T0), feature_decisions=((T0 + timedelta(minutes=1), T0),))
    )
    assert result.status == "FAIL"
    assert "duplicate timestamps detected" in result.reasons
    assert "feature availability occurs after decision time" in result.reasons


def test_g3_passes_matching_semantics() -> None:
    result = evaluate_g3(SemanticEvidence("h", "h", (T0,), (T0,), (T0,), (T0,), "close", "close"))
    assert result.status == "PASS"


def test_g3_fails_signal_and_same_bar_mismatch() -> None:
    result = evaluate_g3(SemanticEvidence("h", "h", (T0,), (), (T0,), (), "close", "open"))
    assert result.status == "FAIL"
    assert "signal timestamps differ" in result.reasons
    assert "same-bar assumptions differ" in result.reasons


def test_g4_passes_clean_temporal_check() -> None:
    result = evaluate_g4(LeakageEvidence(((T0, T0),), True, True))
    assert result.status == "PASS"
    assert not result.hard_fail


def test_g4_hard_fails_known_leakage_or_missing_check() -> None:
    result = evaluate_g4(LeakageEvidence(((T0 + timedelta(minutes=1), T0),), False, None))
    assert result.status == "FAIL"
    assert result.hard_fail


def test_cost_rule_passes_economic_profitability() -> None:
    result = evaluate_cost_hard_fail(Decimal("0.10"), (CostObservation("F1/S1", Decimal("0.02")),))
    assert result.status == "PASS"


def test_cost_rule_hard_fails_zero_cost_only_profit() -> None:
    result = evaluate_cost_hard_fail(
        Decimal("0.10"),
        (
            CostObservation("F0/S0", Decimal("0.10"), diagnostic_only=True),
            CostObservation("F1/S1", Decimal("-0.01")),
        ),
    )
    assert result.status == "FAIL"
    assert result.hard_fail


def test_g10_retention_evidence_passes_without_pbo_dsr_activation() -> None:
    result = evaluate_g10_retention_evidence(
        MultipleTestingEvidence(
            trial_count=66,
            expected_trial_count=66,
            all_trials_retained=True,
            selection_procedure="no winner selected; all B2/B3/B4 trials retained",
            winner_selected=False,
            method_reference_ids=("SRC-PBO-2016", "SRC-DSR-2014"),
        )
    )
    assert result.status == "PASS"
    assert result.gate == "G10_RETENTION"
    assert result.details["production_estimator_validated"] is False


def test_g10_retention_evidence_blocks_partial_or_premature_selection() -> None:
    result = evaluate_g10_retention_evidence(
        MultipleTestingEvidence(
            trial_count=65,
            expected_trial_count=66,
            all_trials_retained=False,
            selection_procedure="selected best return",
            winner_selected=True,
            method_reference_ids=("SRC-PBO-2016",),
        )
    )
    assert result.status == "FAIL"
    assert "retained trial count does not match expected count" in result.reasons
    assert "not all trials are retained" in result.reasons
    assert "winner selected before PBO/DSR estimator validation" in result.reasons
    assert "missing method references: SRC-DSR-2014" in result.reasons
