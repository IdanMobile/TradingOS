"""Fail-closed metric, scorecard, and strategy-promotion eligibility."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

REQUIRED_DIMENSIONS = frozenset(
    {
        "data_integrity_and_freshness",
        "economic_performance_after_declared_costs",
        "drawdown_and_loss_severity",
        "parameter_neighborhood_robustness",
        "temporal_walk_forward_stability",
        "regime_stability",
        "baseline_superiority",
        "multiple_testing_selection_bias_control",
        "cross_engine_reproduction",
        "operational_and_evidence_completeness",
    }
)
REQUIRED_GATES = frozenset(f"G{number}" for number in range(1, 12))
REQUIRED_REVIEWS = frozenset({"STATISTICAL", "RISK", "SUPERVISOR", "SECURITY"})
DIMENSION_STATUSES = frozenset({"PASS", "FAIL", "WARN", "NOT_RUN"})


@dataclass(frozen=True)
class MetricEvidence:
    name: str
    inputs_complete: bool
    conventions_complete: bool
    observations: int
    minimum_observations: int
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class MetricEligibility:
    name: str
    eligible: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ScorecardEvidence:
    strategy_version_ref: str
    context_ref: str
    dataset_ref: str
    preregistration_ref: str
    declared_trial_count: int
    terminal_trial_count: int
    causal_evidence_refs: tuple[str, ...]
    benchmark_ref: str
    after_cost_return_ref: str
    environment_ref: str
    engine_version: str
    dimension_statuses: Mapping[str, str]
    dimension_blockers: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class PromotionEvidence:
    validation_status: str
    hard_fail: bool
    gate_statuses: Mapping[str, str]
    gate_evidence_refs: Mapping[str, tuple[str, ...]]
    review_statuses: Mapping[str, str]
    review_evidence_refs: Mapping[str, tuple[str, ...]]
    live_orders_enabled: bool


@dataclass(frozen=True)
class StrategyEligibility:
    metrics: tuple[MetricEligibility, ...]
    scorecard_eligible: bool
    promotion_eligible: bool
    scorecard_blockers: tuple[str, ...]
    promotion_blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": [
                {**asdict(metric), "blockers": list(metric.blockers)} for metric in self.metrics
            ],
            "scorecard_eligible": self.scorecard_eligible,
            "promotion_eligible": self.promotion_eligible,
            "scorecard_blockers": list(self.scorecard_blockers),
            "promotion_blockers": list(self.promotion_blockers),
        }


def evaluate_metric_eligibility(evidence: MetricEvidence) -> MetricEligibility:
    blockers: list[str] = []
    if not evidence.name:
        blockers.append("METRIC_NAME_MISSING")
    if evidence.inputs_complete is not True:
        blockers.append("METRIC_INPUTS_INCOMPLETE")
    if evidence.conventions_complete is not True:
        blockers.append("METRIC_CONVENTIONS_INCOMPLETE")
    valid_counts = (
        isinstance(evidence.observations, int)
        and not isinstance(evidence.observations, bool)
        and isinstance(evidence.minimum_observations, int)
        and not isinstance(evidence.minimum_observations, bool)
        and evidence.minimum_observations > 0
        and evidence.observations >= evidence.minimum_observations
    )
    if not valid_counts:
        blockers.append("METRIC_SAMPLE_INSUFFICIENT")
    if not _refs_complete(evidence.evidence_refs):
        blockers.append("METRIC_EVIDENCE_MISSING")
    return MetricEligibility(evidence.name, not blockers, tuple(blockers))


def evaluate_strategy_eligibility(
    metrics: tuple[MetricEvidence, ...],
    scorecard: ScorecardEvidence,
    promotion: PromotionEvidence,
    budget_verdict: Any | None = None,
) -> StrategyEligibility:
    """Evaluate metric, scorecard, and promotion eligibility.

    `budget_verdict` is a `trial_budget.BudgetVerdict` cross-checking the scorecard's
    self-reported trial count against the persistent ledger. It is required: a scorecard
    whose search width was never verified cannot support a multiple-testing claim, so
    omitting it is a blocker rather than a default-pass. Callers verify and pass the
    verdict so this module stays pure.
    """
    metric_results = tuple(evaluate_metric_eligibility(metric) for metric in metrics)
    scorecard_blockers = _scorecard_blockers(scorecard)
    scorecard_blockers.extend(_budget_blockers(scorecard, budget_verdict))
    promotion_blockers = _promotion_blockers(scorecard, promotion)
    if scorecard_blockers:
        promotion_blockers.insert(0, "SCORECARD_INELIGIBLE")
    return StrategyEligibility(
        metrics=metric_results,
        scorecard_eligible=not scorecard_blockers,
        promotion_eligible=not scorecard_blockers and not promotion_blockers,
        scorecard_blockers=tuple(scorecard_blockers),
        promotion_blockers=tuple(promotion_blockers),
    )


def _scorecard_blockers(evidence: ScorecardEvidence) -> list[str]:
    blockers: list[str] = []
    identity_refs = (
        evidence.strategy_version_ref,
        evidence.context_ref,
        evidence.dataset_ref,
        evidence.preregistration_ref,
        evidence.benchmark_ref,
        evidence.after_cost_return_ref,
        evidence.environment_ref,
        evidence.engine_version,
    )
    if not all(isinstance(ref, str) and ref.strip() for ref in identity_refs):
        blockers.append("SCORECARD_IDENTITY_OR_PROVENANCE_INCOMPLETE")
    valid_trials = (
        isinstance(evidence.declared_trial_count, int)
        and not isinstance(evidence.declared_trial_count, bool)
        and evidence.declared_trial_count > 0
        and isinstance(evidence.terminal_trial_count, int)
        and not isinstance(evidence.terminal_trial_count, bool)
        and evidence.terminal_trial_count == evidence.declared_trial_count
    )
    if not valid_trials:
        blockers.append("TRIAL_POPULATION_INCOMPLETE")
    if not _refs_complete(evidence.causal_evidence_refs):
        blockers.append("CAUSAL_EVIDENCE_MISSING")
    if set(evidence.dimension_statuses) != REQUIRED_DIMENSIONS or any(
        status not in DIMENSION_STATUSES for status in evidence.dimension_statuses.values()
    ):
        blockers.append("SCORECARD_DIMENSIONS_INVALID")
    else:
        unavailable = {
            dimension
            for dimension, status in evidence.dimension_statuses.items()
            if status != "PASS"
        }
        declared = {
            dimension
            for dimension, reasons in evidence.dimension_blockers.items()
            if _refs_complete(reasons)
        }
        if unavailable - declared:
            blockers.append("UNAVAILABLE_DIMENSION_BLOCKERS_MISSING")
    return blockers


def _budget_blockers(scorecard: ScorecardEvidence, verdict: Any | None) -> list[str]:
    """Cross-check the declared trial population against the persistent ledger.

    Without this, `declared_trial_count == terminal_trial_count` only proves a scorecard
    agrees with itself. A search of three thousand parameter sets can declare three and
    satisfy every other check, leaving PBO and DSR deflating against a number that bears
    no relation to how much searching actually happened.
    """
    if verdict is None:
        return ["TRIAL_BUDGET_NOT_VERIFIED"]

    blockers: list[str] = []
    if not getattr(verdict, "verified", False):
        blockers.append("TRIAL_BUDGET_VERIFICATION_FAILED")
    if getattr(verdict, "registration_ref", "") != scorecard.preregistration_ref:
        blockers.append("TRIAL_BUDGET_REGISTRATION_MISMATCH")
    return blockers


def _promotion_blockers(scorecard: ScorecardEvidence, evidence: PromotionEvidence) -> list[str]:
    blockers: list[str] = []
    if evidence.validation_status != "COMPLETE_APPROVABLE":
        blockers.append("VALIDATION_NOT_COMPLETE_APPROVABLE")
    if evidence.hard_fail is not False:
        blockers.append("VALIDATION_HARD_FAIL")
    if set(evidence.gate_statuses) != REQUIRED_GATES or any(
        status != "PASS" for status in evidence.gate_statuses.values()
    ):
        blockers.append("MANDATORY_GATES_NOT_ALL_PASS")
    if set(evidence.gate_evidence_refs) != REQUIRED_GATES or any(
        not _refs_complete(refs) for refs in evidence.gate_evidence_refs.values()
    ):
        blockers.append("MANDATORY_GATE_EVIDENCE_INCOMPLETE")
    if any(status != "PASS" for status in scorecard.dimension_statuses.values()):
        blockers.append("SCORECARD_DIMENSIONS_NOT_ALL_PASS")
    if set(evidence.review_statuses) != REQUIRED_REVIEWS or any(
        status != "PASS" for status in evidence.review_statuses.values()
    ):
        blockers.append("INDEPENDENT_REVIEWS_NOT_ALL_PASS")
    if set(evidence.review_evidence_refs) != REQUIRED_REVIEWS or any(
        not _refs_complete(refs) for refs in evidence.review_evidence_refs.values()
    ):
        blockers.append("INDEPENDENT_REVIEW_EVIDENCE_INCOMPLETE")
    if evidence.live_orders_enabled is not False:
        blockers.append("LIVE_ORDER_CAPABILITY_PRESENT")
    return blockers


def _refs_complete(refs: tuple[str, ...]) -> bool:
    return (
        isinstance(refs, tuple)
        and bool(refs)
        and all(isinstance(ref, str) and ref.strip() for ref in refs)
    )
