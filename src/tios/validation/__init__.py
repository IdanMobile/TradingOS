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
    "RiskPreconditionResult",
    "evaluate_risk_preconditions",
]
