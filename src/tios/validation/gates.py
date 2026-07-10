"""Pure validation foundations for the first four backtest gates.

This module deliberately evaluates evidence supplied by callers; it does not
run engines or inspect files. G5's economic hard-fail rule is included as a
small reusable predicate. G10 only validates retained multiple-testing evidence;
PBO/DSR estimator activation still needs known-answer method validation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str
    hard_fail: bool = False
    reasons: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "hard_fail": self.hard_fail,
            "reasons": list(self.reasons),
            "details": dict(self.details),
        }


def _result(
    gate: str,
    failures: list[str],
    details: Mapping[str, Any],
    *,
    hard_fail: bool = False,
) -> GateResult:
    return GateResult(
        gate=gate,
        status=FAIL if failures else PASS,
        hard_fail=hard_fail,
        reasons=tuple(failures),
        details=details,
    )


@dataclass(frozen=True)
class ReproducibilityEvidence:
    code_commit: str
    dataset_id: str
    dataset_hash: str
    engine: str
    engine_version: str
    parameters: Mapping[str, Any]
    fees_slippage: Mapping[str, Any]
    seed: int | None
    first_fields: Mapping[str, Any]
    rerun_fields: Mapping[str, Any]
    tolerance: Decimal = Decimal("0")


def evaluate_g1(evidence: ReproducibilityEvidence) -> GateResult:
    """Pass only when provenance is complete and rerun fields match."""
    failures: list[str] = []
    for name, value in (
        ("code_commit", evidence.code_commit),
        ("dataset_id", evidence.dataset_id),
        ("dataset_hash", evidence.dataset_hash),
        ("engine", evidence.engine),
        ("engine_version", evidence.engine_version),
    ):
        if not value:
            failures.append(f"missing {name}")
    if not isinstance(evidence.parameters, Mapping):
        failures.append("parameters must be a mapping")
    if not isinstance(evidence.fees_slippage, Mapping):
        failures.append("fees_slippage must be a mapping")
    if evidence.seed is None:
        failures.append("missing deterministic seed")
    if set(evidence.first_fields) != set(evidence.rerun_fields):
        failures.append("rerun fields differ")
    else:
        for key, first in evidence.first_fields.items():
            rerun = evidence.rerun_fields[key]
            try:
                equal = abs(Decimal(str(first)) - Decimal(str(rerun))) <= evidence.tolerance
            except (ArithmeticError, ValueError):
                equal = first == rerun
            if not equal:
                failures.append(f"rerun mismatch: {key}")
    return _result("G1", failures, {"tolerance": str(evidence.tolerance)}, hard_fail=bool(failures))


@dataclass(frozen=True)
class TimestampEvidence:
    timestamps: tuple[datetime, ...]
    feature_decisions: tuple[tuple[datetime, datetime], ...] = ()
    interval_seconds: int | None = None


def _utc_timestamp(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() == UTC.utcoffset(value)


def evaluate_g2(evidence: TimestampEvidence) -> GateResult:
    """Check UTC timestamps, ordering, duplicates, gaps, and feature timing."""
    failures: list[str] = []
    timestamps = evidence.timestamps
    if any(not _utc_timestamp(ts) for ts in timestamps):
        failures.append("timestamps must be timezone-aware UTC")
    duplicate_count = len(timestamps) - len(set(timestamps))
    if duplicate_count:
        failures.append("duplicate timestamps detected")
    if any(b <= a for a, b in zip(timestamps, timestamps[1:], strict=False)):
        failures.append("timestamps are not strictly increasing")
    if evidence.interval_seconds is not None and evidence.interval_seconds <= 0:
        failures.append("interval_seconds must be positive")
    gaps = []
    if evidence.interval_seconds:
        step = evidence.interval_seconds
        gaps = [
            int((b - a).total_seconds() / step) - 1
            for a, b in zip(timestamps, timestamps[1:], strict=False)
            if (b - a).total_seconds() > step and (b - a).total_seconds() % step == 0
        ]
    future_features = sum(
        available > decision for available, decision in evidence.feature_decisions
    )
    if future_features:
        failures.append("feature availability occurs after decision time")
    return _result(
        "G2",
        failures,
        {
            "rows": len(timestamps),
            "duplicate_count": duplicate_count,
            "missing_interval_count": len(gaps),
            "missing_intervals": gaps,
            "future_feature_count": future_features,
        },
    )


@dataclass(frozen=True)
class SemanticEvidence:
    canonical_spec_hash: str
    implementation_spec_hash: str
    expected_signal_timestamps: tuple[datetime, ...]
    actual_signal_timestamps: tuple[datetime, ...]
    expected_order_timestamps: tuple[datetime, ...]
    actual_order_timestamps: tuple[datetime, ...]
    expected_same_bar_assumption: str
    actual_same_bar_assumption: str


def evaluate_g3(evidence: SemanticEvidence) -> GateResult:
    failures = []
    if evidence.canonical_spec_hash != evidence.implementation_spec_hash:
        failures.append("canonical and implementation spec hashes differ")
    if evidence.expected_signal_timestamps != evidence.actual_signal_timestamps:
        failures.append("signal timestamps differ")
    if evidence.expected_order_timestamps != evidence.actual_order_timestamps:
        failures.append("order timestamps differ")
    if evidence.expected_same_bar_assumption != evidence.actual_same_bar_assumption:
        failures.append("same-bar assumptions differ")
    return _result("G3", failures, {})


@dataclass(frozen=True)
class LeakageEvidence:
    feature_decisions: tuple[tuple[datetime, datetime], ...]
    temporal_check_passed: bool
    lookahead_analysis_passed: bool | None = None


def evaluate_g4(evidence: LeakageEvidence) -> GateResult:
    failures = []
    material_leakage = any(
        available > decision for available, decision in evidence.feature_decisions
    )
    if not evidence.temporal_check_passed:
        failures.append("temporal leakage check failed")
    if material_leakage:
        failures.append("material future feature access detected")
    if evidence.lookahead_analysis_passed is False:
        failures.append("lookahead-analysis failed")
    if evidence.lookahead_analysis_passed is None:
        failures.append("lookahead check not run")
    return _result("G4", failures, {}, hard_fail=material_leakage)


@dataclass(frozen=True)
class CostObservation:
    scenario_id: str
    net_expectancy: Decimal
    diagnostic_only: bool = False


def evaluate_cost_hard_fail(
    gross_expectancy: Decimal, observations: tuple[CostObservation, ...]
) -> GateResult:
    """Reject economic evidence profitable only in the zero-cost diagnostic."""
    economic = tuple(o for o in observations if not o.diagnostic_only)
    only_zero_cost = gross_expectancy > 0 and (
        not economic or all(o.net_expectancy <= 0 for o in economic)
    )
    return _result(
        "G5_COST_HARD_FAIL_RULE",
        ["profitable only under zero costs"] if only_zero_cost else [],
        {"economic_scenarios": [o.scenario_id for o in economic]},
        hard_fail=only_zero_cost,
    )


@dataclass(frozen=True)
class MultipleTestingEvidence:
    trial_count: int
    expected_trial_count: int
    all_trials_retained: bool
    selection_procedure: str
    winner_selected: bool
    method_reference_ids: tuple[str, ...]
    validated_estimator_ids: tuple[str, ...] = ()


def evaluate_g10_retention_evidence(evidence: MultipleTestingEvidence) -> GateResult:
    """Check G10's local retention facts without claiming PBO/DSR is validated."""
    failures: list[str] = []
    if evidence.trial_count <= 0:
        failures.append("no retained trials")
    if evidence.trial_count != evidence.expected_trial_count:
        failures.append("retained trial count does not match expected count")
    if not evidence.all_trials_retained:
        failures.append("not all trials are retained")
    if not evidence.selection_procedure:
        failures.append("missing selection procedure")
    if evidence.winner_selected and not evidence.validated_estimator_ids:
        failures.append("winner selected before PBO/DSR estimator validation")
    required_refs = {"SRC-PBO-2016", "SRC-DSR-2014"}
    missing_refs = sorted(required_refs - set(evidence.method_reference_ids))
    if missing_refs:
        failures.append(f"missing method references: {', '.join(missing_refs)}")
    return _result(
        "G10_RETENTION",
        failures,
        {
            "trial_count": evidence.trial_count,
            "expected_trial_count": evidence.expected_trial_count,
            "all_trials_retained": evidence.all_trials_retained,
            "winner_selected": evidence.winner_selected,
            "method_reference_ids": list(evidence.method_reference_ids),
            "validated_estimator_ids": list(evidence.validated_estimator_ids),
            "production_estimator_validated": bool(evidence.validated_estimator_ids),
        },
    )
