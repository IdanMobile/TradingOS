"""Composable validation gate foundations."""

from tios.validation.gates import (
    CostObservation,
    GateResult,
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
from tios.validation.multiple_testing import (
    deflated_sharpe_ratio,
    expected_maximum_noise_sharpe,
    probability_of_backtest_overfitting,
    sharpe_variance_from_trials,
)
from tios.validation.risk import RiskPreconditionResult, evaluate_risk_preconditions

__all__ = [
    "CostObservation",
    "GateResult",
    "LeakageEvidence",
    "MultipleTestingEvidence",
    "ReproducibilityEvidence",
    "SemanticEvidence",
    "TimestampEvidence",
    "evaluate_cost_hard_fail",
    "evaluate_g1",
    "evaluate_g2",
    "evaluate_g3",
    "evaluate_g4",
    "evaluate_g10_retention_evidence",
    "deflated_sharpe_ratio",
    "expected_maximum_noise_sharpe",
    "probability_of_backtest_overfitting",
    "sharpe_variance_from_trials",
    "RiskPreconditionResult",
    "evaluate_risk_preconditions",
]
