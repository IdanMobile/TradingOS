from dataclasses import replace

from tios.validation import (
    MetricEvidence,
    PromotionEvidence,
    ScorecardEvidence,
    evaluate_strategy_eligibility,
)
from tios.validation.eligibility import REQUIRED_DIMENSIONS, REQUIRED_GATES, REQUIRED_REVIEWS


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


def test_complete_evidence_is_scorecard_and_promotion_eligible() -> None:
    result = evaluate_strategy_eligibility(
        (
            MetricEvidence("DSR", True, True, 12, 12, ("evidence:dsr",)),
            MetricEvidence("PBO", True, True, 16, 16, ("evidence:pbo",)),
        ),
        _scorecard(),
        _promotion(),
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
        (MetricEvidence("PBO", False, False, 4, 8640, ()),), scorecard, promotion
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
    )

    assert not result.promotion_eligible
    assert "MANDATORY_GATES_NOT_ALL_PASS" in result.promotion_blockers
    assert "INDEPENDENT_REVIEWS_NOT_ALL_PASS" in result.promotion_blockers
