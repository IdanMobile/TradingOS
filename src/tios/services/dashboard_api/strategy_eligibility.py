"""Read-only eligibility projection for the active prospective signal."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from tios.validation.eligibility import (
    REQUIRED_DIMENSIONS,
    REQUIRED_GATES,
    REQUIRED_REVIEWS,
    MetricEvidence,
    PromotionEvidence,
    ScorecardEvidence,
    evaluate_strategy_eligibility,
)

SIGNAL_ID = "PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1"
CONTRACT_ID = "STRATEGY-ELIGIBILITY-CONTRACT-V1"
WARMUP_TARGET = 8_640


def build_strategy_eligibility_projection(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Derive current eligibility without computing or imputing a performance score."""
    runtime = observation.get("runtime")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    finalized = _nonnegative_int(runtime.get("finalized_window_count"))
    target = _positive_int(runtime.get("requested_checkpoint_count")) or WARMUP_TARGET
    evidence = observation.get("evidence")
    evidence = evidence if isinstance(evidence, Mapping) else {}
    latest = evidence.get("latest")
    latest = latest if isinstance(latest, list) else []
    checkpoint_refs = tuple(
        ref
        for row in latest
        if isinstance(row, Mapping)
        and isinstance((ref := row.get("artifact_ref")), str)
        and ref.strip()
    )
    dimensions = {dimension: "NOT_RUN" for dimension in REQUIRED_DIMENSIONS}
    decision = evaluate_strategy_eligibility(
        (
            MetricEvidence(
                name="PROSPECTIVE_REVIEW_METRICS",
                inputs_complete=False,
                conventions_complete=True,
                observations=finalized,
                minimum_observations=target,
                evidence_refs=checkpoint_refs,
            ),
        ),
        ScorecardEvidence(
            strategy_version_ref="",
            context_ref="BTCUSDT-SPOT-1H-PROSPECTIVE",
            dataset_ref="",
            preregistration_ref="research/PROSPECTIVE_BTC_LIQUIDATION_STRESS_SIGNAL_V1.yaml",
            declared_trial_count=target,
            terminal_trial_count=finalized,
            causal_evidence_refs=checkpoint_refs,
            benchmark_ref="",
            after_cost_return_ref="",
            environment_ref="PUBLIC_READ_ONLY_PROSPECTIVE",
            engine_version="checkpoint-observer-v5",
            dimension_statuses=dimensions,
            dimension_blockers={
                dimension: ("PROSPECTIVE_WARMUP_BLOCK",) for dimension in REQUIRED_DIMENSIONS
            },
        ),
        PromotionEvidence(
            validation_status="WARMUP_BLOCK",
            hard_fail=False,
            gate_statuses={gate: "NOT_RUN" for gate in REQUIRED_GATES},
            gate_evidence_refs={gate: () for gate in REQUIRED_GATES},
            review_statuses={review: "NOT_RUN" for review in REQUIRED_REVIEWS},
            review_evidence_refs={review: () for review in REQUIRED_REVIEWS},
            live_orders_enabled=(
                not isinstance(observation.get("capabilities"), Mapping)
                or observation["capabilities"].get("live_orders") != "DISABLED"
            ),
        ),
    )
    payload = decision.as_dict()
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "subject_ref": SIGNAL_ID,
        "state": "NOT_ELIGIBLE",
        "metric_eligible": decision.metrics[0].eligible,
        **payload,
        "execution_authority": "NONE",
        "interpretation": "MANAGED_EVIDENCE_COLLECTION_NOT_VALIDATED_ALPHA",
    }


def _nonnegative_int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None
