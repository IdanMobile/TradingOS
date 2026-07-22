"""Fail-closed pre-review promotion packages.

This module only assembles retained validation evidence and asks independent
reviewers to assess it.  It cannot approve a strategy, create a stage-gate
decision, dereference evidence, run a campaign, or grant execution authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

from tios.validation.eligibility import (
    DIMENSION_STATUSES,
    REQUIRED_DIMENSIONS,
    REQUIRED_GATES,
    REQUIRED_REVIEWS,
    MetricEvidence,
    PromotionEvidence,
    ScorecardEvidence,
    StrategyEligibility,
    evaluate_strategy_eligibility,
)
from tios.validation.trial_budget import (
    LEDGER_DIRNAME,
    LEDGER_FILENAME,
    REGISTRY_FILENAME,
    BudgetVerdict,
    verify_declared_trials,
)

GATE_STATUSES = frozenset({"PASS", "FAIL", "NOT_RUN"})
PACKAGE_STATUSES = frozenset({"NOT_ELIGIBLE", "ASSEMBLED_PENDING_EVIDENCE_RESOLUTION"})
REQUEST_STATUSES = frozenset({"BLOCKED_EVIDENCE_RESOLUTION"})
_GATE_ORDER = tuple(f"G{number}" for number in range(1, 12))
_REVIEW_ORDER = ("STATISTICAL", "RISK", "SUPERVISOR", "SECURITY")
_REVIEW_ONLY_BLOCKERS = frozenset(
    {"INDEPENDENT_REVIEWS_NOT_ALL_PASS", "INDEPENDENT_REVIEW_EVIDENCE_INCOMPLETE"}
)
_EVIDENCE_RESOLUTION_BLOCKER = "EVIDENCE_REFS_UNRESOLVED"
_METRIC_NAME = re.compile(r"[A-Z][A-Z0-9_:-]*")
_MAPPING_PROXY_TYPE: type[Any] = type(MappingProxyType({}))


class PromotionPackageError(ValueError):
    """Raised when promotion-package input is ambiguous or unsafe."""


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise PromotionPackageError(f"{name} must be non-empty canonical text")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha256(name: str, value: object) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise PromotionPackageError(f"{name} must be a lowercase SHA-256 digest")


def _canonical_strings(name: str, values: tuple[str, ...], *, allow_empty: bool) -> None:
    if not isinstance(values, tuple):
        raise PromotionPackageError(f"{name} must be a tuple")
    if not allow_empty and not values:
        raise PromotionPackageError(f"{name} must not be empty")
    if any(
        not isinstance(item, str) or not item.strip() or item != item.strip() for item in values
    ):
        raise PromotionPackageError(f"{name} contains invalid text")
    if values != tuple(sorted(set(values))):
        raise PromotionPackageError(f"{name} must be unique and canonically sorted")
    if len({value.casefold() for value in values}) != len(values):
        raise PromotionPackageError(f"{name} contains case aliases")


@dataclass(frozen=True, slots=True)
class GateEvidenceRecord:
    """One caller-supplied gate outcome; absence is normalized to ``NOT_RUN``."""

    gate: str
    status: str
    hard_fail: bool
    evidence_refs: tuple[str, ...]
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.gate not in REQUIRED_GATES:
            raise PromotionPackageError(f"unknown gate: {self.gate!r}")
        if self.status not in GATE_STATUSES:
            raise PromotionPackageError(f"invalid status for {self.gate}: {self.status!r}")
        if not isinstance(self.hard_fail, bool):
            raise PromotionPackageError("hard_fail must be bool")
        _canonical_strings("evidence_refs", self.evidence_refs, allow_empty=True)
        _canonical_strings("blockers", self.blockers, allow_empty=True)
        if self.status == "PASS" and not self.evidence_refs:
            raise PromotionPackageError(f"{self.gate} PASS requires evidence")
        if self.status != "PASS" and not self.blockers:
            raise PromotionPackageError(f"{self.gate} {self.status} requires blockers")
        if self.status == "PASS" and (self.blockers or self.hard_fail):
            raise PromotionPackageError(f"{self.gate} PASS cannot retain blockers or hard-fail")
        if self.hard_fail and self.status != "FAIL":
            raise PromotionPackageError(f"{self.gate} hard-fail requires FAIL status")

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "hard_fail": self.hard_fail,
            "evidence_refs": list(self.evidence_refs),
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True, slots=True)
class TrialLedgerCheckpoint:
    """Byte-exact checkpoint of both append-only trial-budget ledgers."""

    registrations_sha256: str
    registrations_size: int
    trials_sha256: str
    trials_size: int
    checkpoint_digest: str

    def __post_init__(self) -> None:
        _sha256("registrations_sha256", self.registrations_sha256)
        _sha256("trials_sha256", self.trials_sha256)
        _sha256("checkpoint_digest", self.checkpoint_digest)
        if (
            not isinstance(self.registrations_size, int)
            or isinstance(self.registrations_size, bool)
            or self.registrations_size < 0
            or not isinstance(self.trials_size, int)
            or isinstance(self.trials_size, bool)
            or self.trials_size < 0
        ):
            raise PromotionPackageError("trial-ledger checkpoint sizes must be non-negative ints")
        if self.checkpoint_digest != _digest(self.material_payload()):
            raise PromotionPackageError("trial-ledger checkpoint digest mismatch")

    def material_payload(self) -> dict[str, Any]:
        return {
            "registrations_sha256": self.registrations_sha256,
            "registrations_size": self.registrations_size,
            "trials_sha256": self.trials_sha256,
            "trials_size": self.trials_size,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.material_payload(), "checkpoint_digest": self.checkpoint_digest}


@dataclass(frozen=True, slots=True)
class PromotionPackageRevalidation:
    """Current-ledger comparison required before any future review consumption."""

    valid: bool
    retained_checkpoint_digest: str
    current_checkpoint_digest: str
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.valid, bool):
            raise PromotionPackageError("revalidation valid flag must be bool")
        _sha256("retained_checkpoint_digest", self.retained_checkpoint_digest)
        _sha256("current_checkpoint_digest", self.current_checkpoint_digest)
        _canonical_strings("revalidation blockers", self.blockers, allow_empty=self.valid)
        if self.valid == bool(self.blockers):
            raise PromotionPackageError("revalidation validity conflicts with blockers")


@dataclass(frozen=True, slots=True)
class IndependentReviewRequest:
    """A non-actionable placeholder until typed retained-evidence resolution exists."""

    request_id: str
    review_role: str
    subject_digest: str
    status: str
    blockers: tuple[str, ...]
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _text("request_id", self.request_id)
        if self.review_role not in REQUIRED_REVIEWS:
            raise PromotionPackageError(f"unknown independent review role: {self.review_role!r}")
        _sha256("subject_digest", self.subject_digest)
        if self.status not in REQUEST_STATUSES:
            raise PromotionPackageError(f"invalid review request status: {self.status!r}")
        _canonical_strings("blockers", self.blockers, allow_empty=True)
        if self.status != "BLOCKED_EVIDENCE_RESOLUTION":
            raise PromotionPackageError("review requests must remain evidence-resolution blocked")
        if self.blockers != (_EVIDENCE_RESOLUTION_BLOCKER,):
            raise PromotionPackageError(
                "review request must retain the evidence-resolution blocker"
            )
        if self.execution_authority != "NONE":
            raise PromotionPackageError("review requests cannot carry execution authority")

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "review_role": self.review_role,
            "subject_digest": self.subject_digest,
            "status": self.status,
            "blockers": list(self.blockers),
            "execution_authority": self.execution_authority,
        }


@dataclass(frozen=True, slots=True)
class PromotionPackage:
    """An immutable assessment blocked pending typed evidence resolution.

    Gate and scorecard references are caller claims.  A future boundary must
    resolve them to retained typed evidence before these blocked requests can be
    made actionable.  Trial-ledger revalidation is separately required at that
    future consumption point.
    """

    package_id: str
    package_digest: str
    evidence_digest: str
    strategy_version_ref: str
    gates: tuple[GateEvidenceRecord, ...]
    metrics: tuple[MetricEvidence, ...]
    scorecard: ScorecardEvidence
    budget_verdict: BudgetVerdict
    trial_ledger_checkpoint: TrialLedgerCheckpoint
    eligibility: StrategyEligibility
    review_requests: tuple[IndependentReviewRequest, ...]
    validation_status: str
    live_orders_enabled: bool
    status: str
    blockers: tuple[str, ...]
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        if not isinstance(self.scorecard, ScorecardEvidence):
            raise PromotionPackageError("scorecard must be ScorecardEvidence")
        if not isinstance(self.gates, tuple) or any(
            not isinstance(gate, GateEvidenceRecord) for gate in self.gates
        ):
            raise PromotionPackageError("gates must be a tuple of GateEvidenceRecord")
        if not isinstance(self.metrics, tuple) or any(
            not isinstance(metric, MetricEvidence) for metric in self.metrics
        ):
            raise PromotionPackageError("metrics must be a tuple of MetricEvidence")
        if not isinstance(self.budget_verdict, BudgetVerdict):
            raise PromotionPackageError("budget_verdict must be BudgetVerdict")
        if not isinstance(self.trial_ledger_checkpoint, TrialLedgerCheckpoint):
            raise PromotionPackageError("trial_ledger_checkpoint must be TrialLedgerCheckpoint")
        if not isinstance(self.eligibility, StrategyEligibility):
            raise PromotionPackageError("eligibility must be StrategyEligibility")
        if not isinstance(self.review_requests, tuple) or any(
            not isinstance(request, IndependentReviewRequest) for request in self.review_requests
        ):
            raise PromotionPackageError(
                "review_requests must be a tuple of IndependentReviewRequest"
            )
        object.__setattr__(
            self,
            "budget_verdict",
            _normalize_budget_verdict(self.budget_verdict),
        )
        if _text("strategy_version_ref", self.strategy_version_ref) != self.strategy_version_ref:
            raise PromotionPackageError("strategy_version_ref is not canonical")
        if _text("validation_status", self.validation_status) != self.validation_status:
            raise PromotionPackageError("validation_status is not canonical")
        _sha256("package_digest", self.package_digest)
        _sha256("evidence_digest", self.evidence_digest)
        if self.package_id != f"PP-{self.package_digest[:32]}":
            raise PromotionPackageError("package_id does not match package_digest")
        if self.scorecard.strategy_version_ref != self.strategy_version_ref:
            raise PromotionPackageError("scorecard strategy does not match package strategy")
        if _normalize_gates(self.gates) != self.gates:
            raise PromotionPackageError("promotion package gates are not canonical exact G1-G11")
        if _normalize_metrics(self.metrics) != self.metrics:
            raise PromotionPackageError("promotion package metrics are not canonical")
        if not isinstance(self.scorecard.dimension_statuses, _MAPPING_PROXY_TYPE) or not isinstance(
            self.scorecard.dimension_blockers, _MAPPING_PROXY_TYPE
        ):
            raise PromotionPackageError(
                "retained scorecard mappings must be immutable mappingproxy"
            )
        if any(
            not isinstance(value, tuple) for value in self.scorecard.dimension_blockers.values()
        ):
            raise PromotionPackageError("retained scorecard blocker values must be exact tuples")
        normalized_scorecard = _normalize_scorecard(self.scorecard)
        if normalized_scorecard != self.scorecard:
            raise PromotionPackageError("promotion package scorecard is not canonical/frozen")
        object.__setattr__(self, "scorecard", normalized_scorecard)
        if not isinstance(self.live_orders_enabled, bool):
            raise PromotionPackageError("live_orders_enabled must be bool")
        if self.status not in PACKAGE_STATUSES:
            raise PromotionPackageError(f"invalid promotion package status: {self.status!r}")
        _canonical_strings("blockers", self.blockers, allow_empty=False)
        if self.eligibility.promotion_eligible:
            raise PromotionPackageError("pre-review package cannot represent promotion eligibility")
        if self.execution_authority != "NONE":
            raise PromotionPackageError("promotion packages cannot carry execution authority")
        expected_eligibility = evaluate_strategy_eligibility(
            self.metrics,
            self.scorecard,
            _pre_review_evidence(
                gates=self.gates,
                validation_status=self.validation_status,
                live_orders_enabled=self.live_orders_enabled,
            ),
            self.budget_verdict,
        )
        if self.eligibility != expected_eligibility:
            raise PromotionPackageError("eligibility does not match retained pre-review evidence")
        expected_blockers, expected_status = _derive_package_state(
            gates=self.gates,
            scorecard=self.scorecard,
            budget=self.budget_verdict,
            eligibility=self.eligibility,
        )
        if self.blockers != expected_blockers or self.status != expected_status:
            raise PromotionPackageError("package blockers/status are not exactly derived")
        expected_evidence_digest = _digest(
            _evidence_payload(
                strategy_version_ref=self.strategy_version_ref,
                gates=self.gates,
                metrics=self.metrics,
                scorecard=self.scorecard,
                budget=self.budget_verdict,
                trial_ledger_checkpoint=self.trial_ledger_checkpoint,
                eligibility=self.eligibility,
                validation_status=self.validation_status,
                live_orders_enabled=self.live_orders_enabled,
            )
        )
        if self.evidence_digest != expected_evidence_digest:
            raise PromotionPackageError("evidence_digest does not match retained evidence")
        expected_package_digest = _digest(
            _package_digest_payload(
                evidence_digest=self.evidence_digest,
                strategy_version_ref=self.strategy_version_ref,
                gates=self.gates,
                metrics=self.metrics,
                scorecard=self.scorecard,
                budget_verdict=self.budget_verdict,
                trial_ledger_checkpoint=self.trial_ledger_checkpoint,
                eligibility=self.eligibility,
                validation_status=self.validation_status,
                live_orders_enabled=self.live_orders_enabled,
                status=self.status,
                blockers=self.blockers,
            )
        )
        if self.package_digest != expected_package_digest:
            raise PromotionPackageError("package_digest does not match package content")
        if self.review_requests != _review_requests(self.package_digest):
            raise PromotionPackageError(
                "review requests are not exact package-derived placeholders"
            )

    def content_payload(self) -> dict[str, Any]:
        return _package_content_payload(
            evidence_digest=self.evidence_digest,
            strategy_version_ref=self.strategy_version_ref,
            gates=self.gates,
            metrics=self.metrics,
            scorecard=self.scorecard,
            budget_verdict=self.budget_verdict,
            trial_ledger_checkpoint=self.trial_ledger_checkpoint,
            eligibility=self.eligibility,
            review_requests=self.review_requests,
            validation_status=self.validation_status,
            live_orders_enabled=self.live_orders_enabled,
            status=self.status,
            blockers=self.blockers,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "package_digest": self.package_digest,
            **self.content_payload(),
        }


def _package_content_payload(
    *,
    evidence_digest: str,
    strategy_version_ref: str,
    gates: tuple[GateEvidenceRecord, ...],
    metrics: tuple[MetricEvidence, ...],
    scorecard: ScorecardEvidence,
    budget_verdict: BudgetVerdict,
    trial_ledger_checkpoint: TrialLedgerCheckpoint,
    eligibility: StrategyEligibility,
    review_requests: tuple[IndependentReviewRequest, ...],
    validation_status: str,
    live_orders_enabled: bool,
    status: str,
    blockers: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "evidence_digest": evidence_digest,
        "strategy_version_ref": strategy_version_ref,
        "gates": [gate.as_dict() for gate in gates],
        "metrics": [asdict(metric) for metric in metrics],
        "scorecard": _scorecard_payload(scorecard),
        "budget_verdict": budget_verdict.as_dict(),
        "trial_ledger_checkpoint": trial_ledger_checkpoint.as_dict(),
        "eligibility": eligibility.as_dict(),
        "review_requests": [request.as_dict() for request in review_requests],
        "validation_status": validation_status,
        "live_orders_enabled": live_orders_enabled,
        "status": status,
        "blockers": list(blockers),
        "execution_authority": "NONE",
    }


def _package_digest_payload(
    *,
    evidence_digest: str,
    strategy_version_ref: str,
    gates: tuple[GateEvidenceRecord, ...],
    metrics: tuple[MetricEvidence, ...],
    scorecard: ScorecardEvidence,
    budget_verdict: BudgetVerdict,
    trial_ledger_checkpoint: TrialLedgerCheckpoint,
    eligibility: StrategyEligibility,
    validation_status: str,
    live_orders_enabled: bool,
    status: str,
    blockers: tuple[str, ...],
) -> dict[str, Any]:
    """Digest material excluding requests, which are derived from this digest."""
    return {
        "evidence_digest": evidence_digest,
        "strategy_version_ref": strategy_version_ref,
        "gates": [gate.as_dict() for gate in gates],
        "metrics": [asdict(metric) for metric in metrics],
        "scorecard": _scorecard_payload(scorecard),
        "budget_verdict": budget_verdict.as_dict(),
        "trial_ledger_checkpoint": trial_ledger_checkpoint.as_dict(),
        "eligibility": eligibility.as_dict(),
        "validation_status": validation_status,
        "live_orders_enabled": live_orders_enabled,
        "status": status,
        "blockers": list(blockers),
        "execution_authority": "NONE",
    }


def _normalize_gates(records: Iterable[GateEvidenceRecord]) -> tuple[GateEvidenceRecord, ...]:
    by_gate: dict[str, GateEvidenceRecord] = {}
    for record in records:
        if not isinstance(record, GateEvidenceRecord):
            raise PromotionPackageError("gate evidence must contain GateEvidenceRecord values")
        if record.gate in by_gate:
            raise PromotionPackageError(f"duplicate gate evidence: {record.gate}")
        by_gate[record.gate] = record
    return tuple(
        by_gate.get(
            gate,
            GateEvidenceRecord(gate, "NOT_RUN", False, (), ("MISSING_GATE_EVIDENCE",)),
        )
        for gate in _GATE_ORDER
    )


def _normalize_metrics(metrics: tuple[MetricEvidence, ...]) -> tuple[MetricEvidence, ...]:
    if not isinstance(metrics, tuple) or not metrics:
        raise PromotionPackageError("metrics must be a non-empty tuple")
    normalized: list[MetricEvidence] = []
    aliases: set[str] = set()
    for metric in metrics:
        if not isinstance(metric, MetricEvidence):
            raise PromotionPackageError("metrics must contain MetricEvidence values")
        name = _text("metric name", metric.name)
        if not _METRIC_NAME.fullmatch(name):
            raise PromotionPackageError("metric names must be canonical uppercase identifiers")
        alias = re.sub(r"[^A-Z0-9]", "", name)
        if alias in aliases:
            raise PromotionPackageError("metric names contain a duplicate or alias")
        aliases.add(alias)
        _canonical_strings("metric evidence_refs", metric.evidence_refs, allow_empty=True)
        normalized.append(metric)
    return tuple(sorted(normalized, key=lambda metric: metric.name))


def _normalize_budget_verdict(verdict: BudgetVerdict) -> BudgetVerdict:
    if not isinstance(verdict, BudgetVerdict):
        raise PromotionPackageError("budget_verdict must be BudgetVerdict")
    if not isinstance(verdict.verified, bool):
        raise PromotionPackageError("budget verdict verified must be an exact bool")
    registration_ref = _text("budget registration_ref", verdict.registration_ref)
    for name, value in (
        ("declared_trial_count", verdict.declared_trial_count),
        ("ledger_trial_count", verdict.ledger_trial_count),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise PromotionPackageError(f"budget {name} must be a non-negative exact int")
    raw_blockers = verdict.blockers
    if isinstance(raw_blockers, (str, bytes)) or not isinstance(raw_blockers, Sequence):
        raise PromotionPackageError("budget blockers must be a non-string sequence")
    supplied_blockers = tuple(raw_blockers)
    if any(
        not isinstance(blocker, str) or not blocker.strip() or blocker != blocker.strip()
        for blocker in supplied_blockers
    ):
        raise PromotionPackageError("budget blockers contain invalid canonical text")
    if len(set(supplied_blockers)) != len(supplied_blockers) or len(
        {blocker.casefold() for blocker in supplied_blockers}
    ) != len(supplied_blockers):
        raise PromotionPackageError("budget blockers contain duplicates or aliases")
    blockers = tuple(sorted(supplied_blockers))
    if verdict.verified != (not blockers):
        raise PromotionPackageError("budget verified flag conflicts with blockers")
    declared = verdict.declared_trial_count
    ledger = verdict.ledger_trial_count
    if verdict.verified and declared != ledger:
        raise PromotionPackageError("verified budget counts must match")
    if declared < ledger and "DECLARED_TRIAL_COUNT_UNDERSTATES_LEDGER" not in blockers:
        raise PromotionPackageError("understated budget count requires its canonical blocker")
    if declared > ledger and "DECLARED_TRIAL_COUNT_EXCEEDS_LEDGER" not in blockers:
        raise PromotionPackageError("excess budget count requires its canonical blocker")
    if "DECLARED_TRIAL_COUNT_UNDERSTATES_LEDGER" in blockers and declared >= ledger:
        raise PromotionPackageError("understated budget blocker conflicts with counts")
    if "DECLARED_TRIAL_COUNT_EXCEEDS_LEDGER" in blockers and declared <= ledger:
        raise PromotionPackageError("excess budget blocker conflicts with counts")
    return BudgetVerdict(
        verified=verdict.verified,
        registration_ref=registration_ref,
        declared_trial_count=declared,
        ledger_trial_count=ledger,
        blockers=blockers,
    )


def _normalize_scorecard(scorecard: ScorecardEvidence) -> ScorecardEvidence:
    if not isinstance(scorecard, ScorecardEvidence):
        raise PromotionPackageError("scorecard must be ScorecardEvidence")
    if not isinstance(scorecard.dimension_statuses, Mapping) or not isinstance(
        scorecard.dimension_blockers, Mapping
    ):
        raise PromotionPackageError("scorecard dimensions and blockers must be mappings")
    if any(not isinstance(key, str) for key in scorecard.dimension_statuses) or any(
        not isinstance(key, str) for key in scorecard.dimension_blockers
    ):
        raise PromotionPackageError("scorecard dimension keys must be strings")
    identity_refs = (
        ("strategy_version_ref", scorecard.strategy_version_ref),
        ("context_ref", scorecard.context_ref),
        ("dataset_ref", scorecard.dataset_ref),
        ("preregistration_ref", scorecard.preregistration_ref),
        ("benchmark_ref", scorecard.benchmark_ref),
        ("after_cost_return_ref", scorecard.after_cost_return_ref),
        ("environment_ref", scorecard.environment_ref),
        ("engine_version", scorecard.engine_version),
    )
    for field, value in identity_refs:
        _text(field, value)
    identity_aliases = [value.casefold() for _, value in identity_refs]
    if len(identity_aliases) != len(set(identity_aliases)):
        raise PromotionPackageError("scorecard identity refs contain duplicates or aliases")
    _canonical_strings("causal_evidence_refs", scorecard.causal_evidence_refs, allow_empty=True)
    unknown = set(scorecard.dimension_statuses) - REQUIRED_DIMENSIONS
    unknown_blockers = set(scorecard.dimension_blockers) - REQUIRED_DIMENSIONS
    if unknown or unknown_blockers:
        raise PromotionPackageError(
            f"unknown scorecard dimensions: {sorted(unknown | unknown_blockers)}"
        )
    statuses: dict[str, str] = {}
    blockers: dict[str, tuple[str, ...]] = {}
    for dimension in sorted(REQUIRED_DIMENSIONS):
        status = scorecard.dimension_statuses.get(dimension, "NOT_RUN")
        if not isinstance(status, str):
            raise PromotionPackageError(f"status for dimension {dimension} must be text")
        if status not in DIMENSION_STATUSES:
            raise PromotionPackageError(f"invalid status for dimension {dimension}: {status!r}")
        statuses[dimension] = status
        raw_reasons = scorecard.dimension_blockers.get(dimension, ())
        if not isinstance(raw_reasons, tuple):
            raise PromotionPackageError(f"dimension_blockers[{dimension}] must be an exact tuple")
        reasons = raw_reasons
        if status != "PASS" and not reasons:
            reasons = ("MISSING_DIMENSION_EVIDENCE",)
        if status == "PASS" and reasons:
            raise PromotionPackageError(f"PASS dimension {dimension} cannot retain blockers")
        _canonical_strings(f"dimension_blockers[{dimension}]", reasons, allow_empty=True)
        if reasons:
            blockers[dimension] = reasons
    return replace(
        scorecard,
        dimension_statuses=MappingProxyType(statuses),
        dimension_blockers=MappingProxyType(blockers),
    )


def _scorecard_payload(scorecard: ScorecardEvidence) -> dict[str, Any]:
    return {
        "strategy_version_ref": scorecard.strategy_version_ref,
        "context_ref": scorecard.context_ref,
        "dataset_ref": scorecard.dataset_ref,
        "preregistration_ref": scorecard.preregistration_ref,
        "declared_trial_count": scorecard.declared_trial_count,
        "terminal_trial_count": scorecard.terminal_trial_count,
        "causal_evidence_refs": list(scorecard.causal_evidence_refs),
        "benchmark_ref": scorecard.benchmark_ref,
        "after_cost_return_ref": scorecard.after_cost_return_ref,
        "environment_ref": scorecard.environment_ref,
        "engine_version": scorecard.engine_version,
        "dimension_statuses": dict(scorecard.dimension_statuses),
        "dimension_blockers": {
            key: list(value) for key, value in scorecard.dimension_blockers.items()
        },
    }


def _evidence_payload(
    *,
    strategy_version_ref: str,
    gates: tuple[GateEvidenceRecord, ...],
    metrics: tuple[MetricEvidence, ...],
    scorecard: ScorecardEvidence,
    budget: BudgetVerdict,
    trial_ledger_checkpoint: TrialLedgerCheckpoint,
    eligibility: StrategyEligibility,
    validation_status: str,
    live_orders_enabled: bool,
) -> dict[str, Any]:
    return {
        "strategy_version_ref": strategy_version_ref,
        "gates": [gate.as_dict() for gate in gates],
        "metrics": [asdict(metric) for metric in metrics],
        "scorecard": _scorecard_payload(scorecard),
        "budget_verdict": budget.as_dict(),
        "trial_ledger_checkpoint": trial_ledger_checkpoint.as_dict(),
        "eligibility": eligibility.as_dict(),
        "validation_status": validation_status,
        "live_orders_enabled": live_orders_enabled,
        "execution_authority": "NONE",
    }


def _pre_review_evidence(
    *,
    gates: tuple[GateEvidenceRecord, ...],
    validation_status: str,
    live_orders_enabled: bool,
) -> PromotionEvidence:
    return PromotionEvidence(
        validation_status=validation_status,
        hard_fail=any(gate.hard_fail for gate in gates),
        gate_statuses=MappingProxyType({gate.gate: gate.status for gate in gates}),
        gate_evidence_refs=MappingProxyType({gate.gate: gate.evidence_refs for gate in gates}),
        review_statuses=MappingProxyType({role: "NOT_RUN" for role in _REVIEW_ORDER}),
        review_evidence_refs=MappingProxyType({role: () for role in _REVIEW_ORDER}),
        live_orders_enabled=live_orders_enabled,
    )


def _derive_package_state(
    *,
    gates: tuple[GateEvidenceRecord, ...],
    scorecard: ScorecardEvidence,
    budget: BudgetVerdict,
    eligibility: StrategyEligibility,
) -> tuple[tuple[str, ...], str]:
    blockers = set(eligibility.scorecard_blockers)
    blockers.update(set(eligibility.promotion_blockers) - _REVIEW_ONLY_BLOCKERS)
    blockers.update(blocker for metric in eligibility.metrics for blocker in metric.blockers)
    blockers.update(budget.blockers)
    for gate in gates:
        blockers.update(f"{gate.gate}:{blocker}" for blocker in gate.blockers)
    for dimension, status in scorecard.dimension_statuses.items():
        if status != "PASS":
            blockers.add(f"DIMENSION_{dimension}:{status}")
            blockers.update(
                f"DIMENSION_{dimension}:{reason}"
                for reason in scorecard.dimension_blockers.get(dimension, ())
            )
    otherwise_eligible = not blockers
    blockers.add(_EVIDENCE_RESOLUTION_BLOCKER)
    return (
        tuple(sorted(blockers)),
        "ASSEMBLED_PENDING_EVIDENCE_RESOLUTION" if otherwise_eligible else "NOT_ELIGIBLE",
    )


def _review_requests(package_digest: str) -> tuple[IndependentReviewRequest, ...]:
    _sha256("package_digest", package_digest)
    return tuple(
        IndependentReviewRequest(
            request_id=f"IRR-{role}-{package_digest}",
            review_role=role,
            subject_digest=package_digest,
            status="BLOCKED_EVIDENCE_RESOLUTION",
            blockers=(_EVIDENCE_RESOLUTION_BLOCKER,),
        )
        for role in _REVIEW_ORDER
    )


def _ledger_file_bytes(root: Path, filename: str) -> bytes:
    path = root / LEDGER_DIRNAME / filename
    try:
        return path.read_bytes() if path.is_file() else b""
    except OSError as exc:
        raise PromotionPackageError(f"cannot checkpoint trial ledger {filename}: {exc}") from exc


def _trial_ledger_checkpoint(root: Path) -> TrialLedgerCheckpoint:
    if not isinstance(root, Path):
        raise PromotionPackageError("ledger root must be a Path")
    registrations = _ledger_file_bytes(root, REGISTRY_FILENAME)
    trials = _ledger_file_bytes(root, LEDGER_FILENAME)
    registrations_sha256 = hashlib.sha256(registrations).hexdigest()
    registrations_size = len(registrations)
    trials_sha256 = hashlib.sha256(trials).hexdigest()
    trials_size = len(trials)
    material = {
        "registrations_sha256": registrations_sha256,
        "registrations_size": registrations_size,
        "trials_sha256": trials_sha256,
        "trials_size": trials_size,
    }
    return TrialLedgerCheckpoint(
        registrations_sha256=registrations_sha256,
        registrations_size=registrations_size,
        trials_sha256=trials_sha256,
        trials_size=trials_size,
        checkpoint_digest=_digest(material),
    )


def revalidate_promotion_package(
    ledger_root: Path, package: PromotionPackage
) -> PromotionPackageRevalidation:
    """Fail closed unless the package still matches the exact current trial ledger.

    A future retained-evidence resolver must call this immediately before it can
    consume a package.  A successful result does not resolve caller-claimed gate
    evidence and therefore does not make any review request actionable.
    """
    if not isinstance(package, PromotionPackage):
        raise PromotionPackageError("package must be PromotionPackage")
    checkpoint_before = _trial_ledger_checkpoint(ledger_root)
    current_budget = _normalize_budget_verdict(
        verify_declared_trials(
            ledger_root,
            package.scorecard.preregistration_ref,
            package.scorecard.declared_trial_count,
        )
    )
    current = _trial_ledger_checkpoint(ledger_root)
    blockers: set[str] = set()
    if checkpoint_before != current:
        blockers.add("TRIAL_LEDGER_CHANGED_DURING_REVALIDATION")
    if current != package.trial_ledger_checkpoint:
        blockers.add("TRIAL_LEDGER_CHECKPOINT_STALE")
    if current_budget != package.budget_verdict:
        blockers.add("TRIAL_BUDGET_VERDICT_STALE")
    canonical_blockers = tuple(sorted(blockers))
    return PromotionPackageRevalidation(
        valid=not canonical_blockers,
        retained_checkpoint_digest=package.trial_ledger_checkpoint.checkpoint_digest,
        current_checkpoint_digest=current.checkpoint_digest,
        blockers=canonical_blockers,
    )


def build_promotion_package(
    *,
    ledger_root: Path,
    metrics: tuple[MetricEvidence, ...],
    scorecard: ScorecardEvidence,
    gate_evidence: Iterable[GateEvidenceRecord],
    validation_status: str,
    live_orders_enabled: bool,
) -> PromotionPackage:
    """Assemble unresolved caller claims without making review actionable."""
    if not isinstance(scorecard, ScorecardEvidence):
        raise PromotionPackageError("scorecard must be ScorecardEvidence")
    strategy_ref = _text("strategy_version_ref", scorecard.strategy_version_ref)
    _text("validation_status", validation_status)
    if not isinstance(ledger_root, Path):
        raise PromotionPackageError("ledger_root must be a Path")
    if not isinstance(live_orders_enabled, bool):
        raise PromotionPackageError("live_orders_enabled must be bool")

    normalized_gates = _normalize_gates(gate_evidence)
    normalized_metrics = _normalize_metrics(metrics)
    normalized_scorecard = _normalize_scorecard(scorecard)
    checkpoint_before = _trial_ledger_checkpoint(ledger_root)
    budget = _normalize_budget_verdict(
        verify_declared_trials(
            ledger_root,
            normalized_scorecard.preregistration_ref,
            normalized_scorecard.declared_trial_count,
        )
    )
    checkpoint = _trial_ledger_checkpoint(ledger_root)
    if checkpoint != checkpoint_before:
        raise PromotionPackageError("trial ledger changed while package was assembled")
    promotion = _pre_review_evidence(
        gates=normalized_gates,
        validation_status=validation_status,
        live_orders_enabled=live_orders_enabled,
    )
    eligibility = evaluate_strategy_eligibility(
        normalized_metrics, normalized_scorecard, promotion, budget
    )
    package_blockers, status = _derive_package_state(
        gates=normalized_gates,
        scorecard=normalized_scorecard,
        budget=budget,
        eligibility=eligibility,
    )

    evidence_digest = _digest(
        _evidence_payload(
            strategy_version_ref=strategy_ref,
            gates=normalized_gates,
            metrics=normalized_metrics,
            scorecard=normalized_scorecard,
            budget=budget,
            trial_ledger_checkpoint=checkpoint,
            eligibility=eligibility,
            validation_status=validation_status,
            live_orders_enabled=live_orders_enabled,
        )
    )
    package_digest = _digest(
        _package_digest_payload(
            evidence_digest=evidence_digest,
            strategy_version_ref=strategy_ref,
            gates=normalized_gates,
            metrics=normalized_metrics,
            scorecard=normalized_scorecard,
            budget_verdict=budget,
            trial_ledger_checkpoint=checkpoint,
            eligibility=eligibility,
            validation_status=validation_status,
            live_orders_enabled=live_orders_enabled,
            status=status,
            blockers=package_blockers,
        )
    )
    requests = _review_requests(package_digest)
    return PromotionPackage(
        package_id=f"PP-{package_digest[:32]}",
        package_digest=package_digest,
        evidence_digest=evidence_digest,
        strategy_version_ref=strategy_ref,
        gates=normalized_gates,
        metrics=normalized_metrics,
        scorecard=normalized_scorecard,
        budget_verdict=budget,
        trial_ledger_checkpoint=checkpoint,
        eligibility=eligibility,
        review_requests=requests,
        validation_status=validation_status,
        live_orders_enabled=live_orders_enabled,
        status=status,
        blockers=package_blockers,
    )
