from dataclasses import replace

from tios.validation import (
    MetricEvidence,
    PromotionEvidence,
    ScorecardEvidence,
    evaluate_strategy_eligibility,
)
from tios.validation.eligibility import REQUIRED_DIMENSIONS, REQUIRED_GATES, REQUIRED_REVIEWS
from tios.validation.trial_budget import BudgetVerdict


def _scorecard(status: str = "PASS") -> ScorecardEvidence:
    statuses = {dimension: status for dimension in REQUIRED_DIMENSIONS}
    blockers = (
        {} if status == "PASS" else {dimension: ("evidence:blocker",) for dimension in statuses}
    )
    return ScorecardEvidence(
        strategy_version_ref="SV-1",
        context_ref="BTC-SPOT-1H",
        dataset_ref="DS-1",
        preregistration_ref="research:campaign",
        declared_trial_count=12,
        terminal_trial_count=12,
        causal_evidence_refs=("evidence:signals", "evidence:fills"),
        benchmark_ref="evidence:benchmark",
        after_cost_return_ref="evidence:returns",
        environment_ref="environment:lock",
        engine_version="engine:1.0",
        dimension_statuses=statuses,
        dimension_blockers=blockers,
    )


def _promotion() -> PromotionEvidence:
    return PromotionEvidence(
        validation_status="COMPLETE_APPROVABLE",
        hard_fail=False,
        gate_statuses={gate: "PASS" for gate in REQUIRED_GATES},
        gate_evidence_refs={gate: (f"evidence:{gate}",) for gate in REQUIRED_GATES},
        review_statuses={review: "PASS" for review in REQUIRED_REVIEWS},
        review_evidence_refs={review: (f"evidence:{review}",) for review in REQUIRED_REVIEWS},
        live_orders_enabled=False,
    )


def _verdict(declared: int = 12, ref: str = "research:campaign") -> BudgetVerdict:
    """A ledger-verified trial population matching the scorecard's declaration."""
    return BudgetVerdict(
        verified=True,
        registration_ref=ref,
        declared_trial_count=declared,
        ledger_trial_count=declared,
        blockers=(),
    )


def test_complete_evidence_is_scorecard_and_promotion_eligible() -> None:
    result = evaluate_strategy_eligibility(
        (
            MetricEvidence("DSR", True, True, 12, 12, ("evidence:dsr",)),
            MetricEvidence("PBO", True, True, 16, 16, ("evidence:pbo",)),
        ),
        _scorecard(),
        _promotion(),
        _verdict(),
    )

    assert all(metric.eligible for metric in result.metrics)
    assert result.scorecard_eligible
    assert result.promotion_eligible
    assert not result.scorecard_blockers
    assert not result.promotion_blockers


def test_warmup_signal_fails_closed_without_inventing_zero_scores() -> None:
    scorecard = _scorecard("NOT_RUN")
    scorecard = replace(
        scorecard,
        strategy_version_ref="",
        declared_trial_count=8640,
        terminal_trial_count=4,
        causal_evidence_refs=(),
    )
    promotion = _promotion()
    promotion = replace(
        promotion,
        validation_status="WARMUP_BLOCK",
        gate_statuses={gate: "NOT_RUN" for gate in REQUIRED_GATES},
        review_statuses={review: "NOT_RUN" for review in REQUIRED_REVIEWS},
    )
    result = evaluate_strategy_eligibility(
        (MetricEvidence("PBO", False, False, 4, 8640, ()),), scorecard, promotion, _verdict(8640)
    )

    assert not result.metrics[0].eligible
    assert "METRIC_SAMPLE_INSUFFICIENT" in result.metrics[0].blockers
    assert not result.scorecard_eligible
    assert not result.promotion_eligible
    assert "SCORECARD_INELIGIBLE" in result.promotion_blockers


def test_g10_and_all_independent_reviews_are_mandatory() -> None:
    promotion = _promotion()
    gates = dict(promotion.gate_statuses)
    gates.pop("G10")
    reviews = dict(promotion.review_statuses)
    reviews.pop("SECURITY")
    result = evaluate_strategy_eligibility(
        (MetricEvidence("Sharpe", True, True, 100, 30, ("evidence:sharpe",)),),
        _scorecard(),
        replace(promotion, gate_statuses=gates, review_statuses=reviews),
        _verdict(),
    )

    assert not result.promotion_eligible
    assert "MANDATORY_GATES_NOT_ALL_PASS" in result.promotion_blockers
    assert "INDEPENDENT_REVIEWS_NOT_ALL_PASS" in result.promotion_blockers


def test_unverified_trial_budget_blocks_otherwise_complete_evidence() -> None:
    """Omitting the ledger cross-check fails closed rather than defaulting to a pass."""
    result = evaluate_strategy_eligibility(
        (MetricEvidence("DSR", True, True, 12, 12, ("evidence:dsr",)),),
        _scorecard(),
        _promotion(),
    )

    assert not result.scorecard_eligible
    assert not result.promotion_eligible
    assert "TRIAL_BUDGET_NOT_VERIFIED" in result.scorecard_blockers


def test_failed_budget_verification_blocks_promotion() -> None:
    """A search wider than declared cannot be promoted, however clean the rest looks."""
    understated = BudgetVerdict(
        verified=False,
        registration_ref="research:campaign",
        declared_trial_count=12,
        ledger_trial_count=3000,
        blockers=("DECLARED_TRIAL_COUNT_UNDERSTATES_LEDGER",),
    )
    result = evaluate_strategy_eligibility(
        (MetricEvidence("DSR", True, True, 12, 12, ("evidence:dsr",)),),
        _scorecard(),
        _promotion(),
        understated,
    )

    assert not result.promotion_eligible
    assert "TRIAL_BUDGET_VERIFICATION_FAILED" in result.scorecard_blockers


def test_verdict_for_a_different_campaign_is_rejected() -> None:
    """A verdict must belong to the scorecard's own pre-registration."""
    result = evaluate_strategy_eligibility(
        (MetricEvidence("DSR", True, True, 12, 12, ("evidence:dsr",)),),
        _scorecard(),
        _promotion(),
        _verdict(ref="research:some-other-campaign"),
    )

    assert not result.promotion_eligible
    assert "TRIAL_BUDGET_REGISTRATION_MISMATCH" in result.scorecard_blockers
