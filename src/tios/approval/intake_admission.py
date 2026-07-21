"""Typed, fail-closed intake-decision assessment scaffold.

This module defines only a signed data contract and semantic assessment.  It deliberately
contains no signer, key handling, cryptographic implementation, external history, trusted
clock, evidence resolver, or execution authority.  A caller-supplied
``IndependentIntakeVerifier`` is insufficient for either admission or terminal rejection;
every trust input remains gated on the external activation controls documented by the plan.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, Self

from tios.research_assets.admission import (
    CandidateIntakeError,
    CandidateIntakeLedger,
    CandidateLifecycle,
    IntakeVerdict,
    ReviewDomain,
)

SCHEMA_VERSION = 1
DOMAIN_SEPARATOR = "TIOS/INTAKE-ADMISSION/v1"
SIGNING_PREFIX = b"TIOS/INTAKE-ADMISSION/v1\0"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Z0-9]+(?:[-_.][A-Z0-9]+)*\Z")
_DECISION_ID = re.compile(r"IAD-[0-9a-f]{32}\Z")
_OUTCOME_KEYS = frozenset(
    {
        "alpha",
        "drawdown",
        "equity_curve",
        "loss",
        "metric",
        "outcome_data",
        "performance",
        "pnl",
        "profit",
        "returns",
        "score",
        "sharpe",
        "sortino",
        "trade_count",
        "win_rate",
    }
)


class IntakeAdmissionError(RuntimeError):
    """A malformed or unverifiable admission artifact failed closed."""


class IntakeVerificationError(IntakeAdmissionError):
    """An external verifier could not establish independent reviewer trust."""


class IntakeDecisionOutcome(StrEnum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"


class IntakeAdmissionState(StrEnum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    VERIFIED_PENDING_EXTERNAL_ACTIVATION = "VERIFIED_PENDING_EXTERNAL_ACTIVATION"
    VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION = (
        "VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION"
    )
    REJECTED = "REJECTED"


class ReviewerRole(StrEnum):
    INDEPENDENT_INTAKE_ADMISSION_REVIEWER = "INDEPENDENT_INTAKE_ADMISSION_REVIEWER"


class ReviewResolutionOutcome(StrEnum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"


def _text(field: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise IntakeAdmissionError(f"{field} must be a non-empty trimmed string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise IntakeAdmissionError(f"{field} must not contain control characters")
    return value


def _token(field: str, value: object) -> str:
    text = _text(field, value)
    if not _TOKEN.fullmatch(text):
        raise IntakeAdmissionError(f"{field} must be a canonical token")
    return text


def _sha(field: str, value: object) -> str:
    text = _text(field, value)
    if not _SHA256.fullmatch(text):
        raise IntakeAdmissionError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _time(field: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise IntakeAdmissionError(f"{field} must be timezone-aware")
    normalized = value.astimezone(UTC)
    if normalized.microsecond:
        raise IntakeAdmissionError(f"{field} must have whole-second precision")
    return normalized


def _time_text(value: datetime) -> str:
    return _time("timestamp", value).isoformat().replace("+00:00", "Z")


def _parse_time(field: str, value: object) -> datetime:
    text = _text(field, value)
    if not text.endswith("Z"):
        raise IntakeAdmissionError(f"{field} must use canonical UTC Z form")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise IntakeAdmissionError(f"{field} is not a valid timestamp") from exc
    if _time_text(parsed) != text:
        raise IntakeAdmissionError(f"{field} is not canonical")
    return parsed


def _exact(raw: Mapping[str, object], fields: set[str], label: str) -> None:
    missing, extra = fields - raw.keys(), raw.keys() - fields
    if missing or extra:
        raise IntakeAdmissionError(
            f"{label} fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise IntakeAdmissionError(f"{field} must be a mapping")
    return value


def _string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise IntakeAdmissionError(f"{field} must be a list")
    return tuple(_text(field, item) for item in value)


def _enum(enum_type: type[StrEnum], field: str, value: object) -> StrEnum:
    try:
        return enum_type(_text(field, value))
    except ValueError as exc:
        raise IntakeAdmissionError(f"invalid {field}") from exc


def _reject_floats_and_outcomes(value: object) -> None:
    if isinstance(value, float):
        raise IntakeAdmissionError("floating-point values are prohibited")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in _OUTCOME_KEYS:
                raise IntakeAdmissionError("performance outcome fields are prohibited")
            _reject_floats_and_outcomes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_floats_and_outcomes(child)


def _canonical(value: object) -> bytes:
    _reject_floats_and_outcomes(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IntakeAdmissionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True, slots=True)
class ReviewResolution:
    """Reviewer claims about evidence; digests are not integrity-verified by this module."""

    domain: ReviewDomain
    outcome: ReviewResolutionOutcome
    evidence_digests: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.domain, ReviewDomain) or not isinstance(
            self.outcome, ReviewResolutionOutcome
        ):
            raise IntakeAdmissionError("invalid review resolution enum")
        if self.evidence_digests != tuple(sorted(set(self.evidence_digests))):
            raise IntakeAdmissionError("evidence_digests must be unique and sorted")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise IntakeAdmissionError("reason_codes must be unique and sorted")
        for digest in self.evidence_digests:
            _sha("evidence_digest", digest)
        for reason in self.reason_codes:
            _token("reason_code", reason)
        if not self.evidence_digests or not self.reason_codes:
            raise IntakeAdmissionError("each resolution requires evidence and reason codes")

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": self.domain.value,
            "outcome": self.outcome.value,
            "evidence_digests": list(self.evidence_digests),
            "reason_codes": list(self.reason_codes),
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        _exact(raw, {"domain", "outcome", "evidence_digests", "reason_codes"}, "resolution")
        return cls(
            ReviewDomain(_enum(ReviewDomain, "domain", raw["domain"])),
            ReviewResolutionOutcome(_enum(ReviewResolutionOutcome, "outcome", raw["outcome"])),
            _string_list(raw["evidence_digests"], "evidence_digests"),
            _string_list(raw["reason_codes"], "reason_codes"),
        )


@dataclass(frozen=True, slots=True)
class IntakeDecisionStatement:
    decision_id: str
    dossier_id: str
    dossier_digest: str
    catalog_sha256: str | None
    assessment_sha256: str | None
    predecessor_entry_hash: str
    predecessor_state: IntakeAdmissionState
    outcome: IntakeDecisionOutcome
    reviewer_id: str
    asserted_role: ReviewerRole
    credential_id: str
    trust_snapshot_id: str
    trust_snapshot_digest: str
    trust_snapshot_observed_at: datetime
    decision_at: datetime
    expires_at: datetime
    resolutions: tuple[ReviewResolution, ...]
    rejection_reasons: tuple[str, ...]
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        if not _DECISION_ID.fullmatch(self.decision_id):
            raise IntakeAdmissionError("invalid decision_id")
        _text("dossier_id", self.dossier_id)
        _sha("dossier_digest", self.dossier_digest)
        if self.catalog_sha256 is not None:
            _sha("catalog_sha256", self.catalog_sha256)
        if self.assessment_sha256 is not None:
            _sha("assessment_sha256", self.assessment_sha256)
        if not self.predecessor_entry_hash.startswith("LE-"):
            raise IntakeAdmissionError("invalid predecessor_entry_hash")
        _sha("predecessor_entry_hash", self.predecessor_entry_hash[3:])
        if self.predecessor_state is not IntakeAdmissionState.REVIEW_REQUIRED:
            raise IntakeAdmissionError("predecessor_state must be REVIEW_REQUIRED")
        if not isinstance(self.outcome, IntakeDecisionOutcome):
            raise IntakeAdmissionError("invalid outcome")
        _token("reviewer_id", self.reviewer_id)
        if self.asserted_role is not ReviewerRole.INDEPENDENT_INTAKE_ADMISSION_REVIEWER:
            raise IntakeAdmissionError("wrong reviewer role")
        _token("credential_id", self.credential_id)
        _token("trust_snapshot_id", self.trust_snapshot_id)
        _sha("trust_snapshot_digest", self.trust_snapshot_digest)
        snapshot_at = _time("trust_snapshot_observed_at", self.trust_snapshot_observed_at)
        decided_at = _time("decision_at", self.decision_at)
        expires_at = _time("expires_at", self.expires_at)
        if snapshot_at > decided_at or expires_at <= decided_at:
            raise IntakeAdmissionError("decision/snapshot/expiry chronology is invalid")
        domains = tuple(item.domain for item in self.resolutions)
        if domains != tuple(sorted(set(domains), key=lambda item: item.value)):
            raise IntakeAdmissionError("resolutions must have unique, sorted domains")
        if self.rejection_reasons != tuple(sorted(set(self.rejection_reasons))):
            raise IntakeAdmissionError("rejection_reasons must be unique and sorted")
        for reason in self.rejection_reasons:
            _token("rejection_reason", reason)
        if self.outcome is IntakeDecisionOutcome.REJECT and not self.rejection_reasons:
            raise IntakeAdmissionError("REJECT requires rejection reasons")
        if self.outcome is IntakeDecisionOutcome.ADMIT and self.rejection_reasons:
            raise IntakeAdmissionError("ADMIT cannot contain rejection reasons")
        if self.execution_authority != "NONE":
            raise IntakeAdmissionError("execution_authority must be NONE")
        expected = f"IAD-{hashlib.sha256(_canonical(self.payload_without_id())).hexdigest()[:32]}"
        if self.decision_id != expected:
            raise IntakeAdmissionError("decision_id mismatch")

    def payload_without_id(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "domain_separator": DOMAIN_SEPARATOR,
            "dossier_id": self.dossier_id,
            "dossier_digest": self.dossier_digest,
            "catalog_sha256": self.catalog_sha256,
            "assessment_sha256": self.assessment_sha256,
            "predecessor_entry_hash": self.predecessor_entry_hash,
            "predecessor_state": self.predecessor_state.value,
            "outcome": self.outcome.value,
            "reviewer_id": self.reviewer_id,
            "asserted_role": self.asserted_role.value,
            "credential_id": self.credential_id,
            "trust_snapshot_id": self.trust_snapshot_id,
            "trust_snapshot_digest": self.trust_snapshot_digest,
            "trust_snapshot_observed_at": _time_text(self.trust_snapshot_observed_at),
            "decision_at": _time_text(self.decision_at),
            "expires_at": _time_text(self.expires_at),
            "resolutions": [item.to_dict() for item in self.resolutions],
            "rejection_reasons": list(self.rejection_reasons),
            "execution_authority": "NONE",
        }

    def to_dict(self) -> dict[str, object]:
        return {"decision_id": self.decision_id, **self.payload_without_id()}

    def signing_bytes(self) -> bytes:
        return SIGNING_PREFIX + _canonical(self.to_dict())

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "schema_version",
            "domain_separator",
            "decision_id",
            "dossier_id",
            "dossier_digest",
            "catalog_sha256",
            "assessment_sha256",
            "predecessor_entry_hash",
            "predecessor_state",
            "outcome",
            "reviewer_id",
            "asserted_role",
            "credential_id",
            "trust_snapshot_id",
            "trust_snapshot_digest",
            "trust_snapshot_observed_at",
            "decision_at",
            "expires_at",
            "resolutions",
            "rejection_reasons",
            "execution_authority",
        }
        _exact(raw, fields, "intake decision statement")
        if raw["schema_version"] != SCHEMA_VERSION or isinstance(raw["schema_version"], bool):
            raise IntakeAdmissionError("invalid schema_version")
        if raw["domain_separator"] != DOMAIN_SEPARATOR:
            raise IntakeAdmissionError("invalid domain_separator")
        resolutions = raw["resolutions"]
        if not isinstance(resolutions, list):
            raise IntakeAdmissionError("resolutions must be a list")
        return cls(
            _text("decision_id", raw["decision_id"]),
            _text("dossier_id", raw["dossier_id"]),
            _sha("dossier_digest", raw["dossier_digest"]),
            None
            if raw["catalog_sha256"] is None
            else _sha("catalog_sha256", raw["catalog_sha256"]),
            None
            if raw["assessment_sha256"] is None
            else _sha("assessment_sha256", raw["assessment_sha256"]),
            _text("predecessor_entry_hash", raw["predecessor_entry_hash"]),
            IntakeAdmissionState(
                _enum(IntakeAdmissionState, "predecessor_state", raw["predecessor_state"])
            ),
            IntakeDecisionOutcome(_enum(IntakeDecisionOutcome, "outcome", raw["outcome"])),
            _token("reviewer_id", raw["reviewer_id"]),
            ReviewerRole(_enum(ReviewerRole, "asserted_role", raw["asserted_role"])),
            _token("credential_id", raw["credential_id"]),
            _token("trust_snapshot_id", raw["trust_snapshot_id"]),
            _sha("trust_snapshot_digest", raw["trust_snapshot_digest"]),
            _parse_time("trust_snapshot_observed_at", raw["trust_snapshot_observed_at"]),
            _parse_time("decision_at", raw["decision_at"]),
            _parse_time("expires_at", raw["expires_at"]),
            tuple(
                ReviewResolution.from_mapping(_mapping(item, "resolution")) for item in resolutions
            ),
            _string_list(raw["rejection_reasons"], "rejection_reasons"),
            _text("execution_authority", raw["execution_authority"]),
        )


def build_intake_decision(
    *,
    dossier_id: str,
    dossier_digest: str,
    catalog_sha256: str | None,
    assessment_sha256: str | None,
    predecessor_entry_hash: str,
    predecessor_state: IntakeAdmissionState,
    outcome: IntakeDecisionOutcome,
    reviewer_id: str,
    asserted_role: ReviewerRole,
    credential_id: str,
    trust_snapshot_id: str,
    trust_snapshot_digest: str,
    trust_snapshot_observed_at: datetime,
    decision_at: datetime,
    expires_at: datetime,
    resolutions: tuple[ReviewResolution, ...],
    rejection_reasons: tuple[str, ...],
    execution_authority: str = "NONE",
) -> IntakeDecisionStatement:
    """Build a content-addressed statement; this does not sign or approve it."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "domain_separator": DOMAIN_SEPARATOR,
        "dossier_id": dossier_id,
        "dossier_digest": dossier_digest,
        "catalog_sha256": catalog_sha256,
        "assessment_sha256": assessment_sha256,
        "predecessor_entry_hash": predecessor_entry_hash,
        "predecessor_state": predecessor_state.value,
        "outcome": outcome.value,
        "reviewer_id": reviewer_id,
        "asserted_role": asserted_role.value,
        "credential_id": credential_id,
        "trust_snapshot_id": trust_snapshot_id,
        "trust_snapshot_digest": trust_snapshot_digest,
        "trust_snapshot_observed_at": _time_text(trust_snapshot_observed_at),
        "decision_at": _time_text(decision_at),
        "expires_at": _time_text(expires_at),
        "resolutions": [item.to_dict() for item in resolutions],
        "rejection_reasons": list(rejection_reasons),
        "execution_authority": execution_authority,
    }
    decision_id = f"IAD-{hashlib.sha256(_canonical(payload)).hexdigest()[:32]}"
    return IntakeDecisionStatement(
        decision_id,
        dossier_id,
        dossier_digest,
        catalog_sha256,
        assessment_sha256,
        predecessor_entry_hash,
        predecessor_state,
        outcome,
        reviewer_id,
        asserted_role,
        credential_id,
        trust_snapshot_id,
        trust_snapshot_digest,
        trust_snapshot_observed_at,
        decision_at,
        expires_at,
        resolutions,
        rejection_reasons,
        execution_authority,
    )


@dataclass(frozen=True, slots=True)
class DetachedAttestation:
    algorithm: str
    credential_id: str
    signature_base64: str
    signed_payload_digest: str

    def __post_init__(self) -> None:
        algorithm = _token("algorithm", self.algorithm)
        if algorithm in {"NONE", "FAKE", "TEST"} or algorithm.startswith(("FAKE-", "TEST-")):
            raise IntakeAdmissionError("sentinel attestation algorithms are prohibited")
        _token("credential_id", self.credential_id)
        _sha("signed_payload_digest", self.signed_payload_digest)
        signature = _text("signature_base64", self.signature_base64)
        try:
            decoded = base64.b64decode(signature, validate=True)
        except ValueError as exc:
            raise IntakeAdmissionError("signature_base64 is invalid") from exc
        if not decoded or base64.b64encode(decoded).decode("ascii") != signature:
            raise IntakeAdmissionError("signature_base64 must be canonical and non-empty")

    def to_dict(self) -> dict[str, str]:
        return {
            "algorithm": self.algorithm,
            "credential_id": self.credential_id,
            "signature_base64": self.signature_base64,
            "signed_payload_digest": self.signed_payload_digest,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        _exact(
            raw,
            {"algorithm", "credential_id", "signature_base64", "signed_payload_digest"},
            "attestation",
        )
        return cls(
            *(
                _text(field, raw[field])
                for field in (
                    "algorithm",
                    "credential_id",
                    "signature_base64",
                    "signed_payload_digest",
                )
            )
        )


@dataclass(frozen=True, slots=True)
class SignedIntakeDecision:
    statement: IntakeDecisionStatement
    attestation: DetachedAttestation

    def __post_init__(self) -> None:
        if self.attestation.credential_id != self.statement.credential_id:
            raise IntakeAdmissionError("attestation credential does not match statement")
        digest = hashlib.sha256(self.statement.signing_bytes()).hexdigest()
        if self.attestation.signed_payload_digest != digest:
            raise IntakeAdmissionError("signed payload digest mismatch")

    def to_dict(self) -> dict[str, object]:
        return {"statement": self.statement.to_dict(), "attestation": self.attestation.to_dict()}


def parse_signed_intake_decision(
    payload: bytes | str | Mapping[str, object],
) -> SignedIntakeDecision:
    if isinstance(payload, bytes):
        try:
            text = payload.decode("utf-8")
            raw: object = json.loads(text, object_pairs_hook=_unique_json_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise IntakeAdmissionError("signed decision is not canonical JSON") from exc
    elif isinstance(payload, str):
        text = payload
        try:
            raw = json.loads(text, object_pairs_hook=_unique_json_object)
        except json.JSONDecodeError as exc:
            raise IntakeAdmissionError("signed decision is not JSON") from exc
    else:
        text = None
        raw = payload
    mapping = _mapping(raw, "signed decision")
    _reject_floats_and_outcomes(mapping)
    if text is not None and text.encode("utf-8") != _canonical(mapping):
        raise IntakeAdmissionError("signed decision artifact must use exact canonical JSON")
    _exact(mapping, {"statement", "attestation"}, "signed decision")
    return SignedIntakeDecision(
        IntakeDecisionStatement.from_mapping(_mapping(mapping["statement"], "statement")),
        DetachedAttestation.from_mapping(_mapping(mapping["attestation"], "attestation")),
    )


@dataclass(frozen=True, slots=True)
class VerifiedReviewer:
    reviewer_id: str
    credential_id: str
    trusted_roles: tuple[ReviewerRole, ...]
    credential_valid_from: datetime
    credential_expires_at: datetime
    credential_revoked_at: datetime | None
    trust_snapshot_id: str
    trust_snapshot_digest: str
    trust_snapshot_observed_at: datetime
    trust_snapshot_valid_until: datetime

    def __post_init__(self) -> None:
        _token("reviewer_id", self.reviewer_id)
        _token("credential_id", self.credential_id)
        if self.trusted_roles != tuple(
            sorted(set(self.trusted_roles), key=lambda item: item.value)
        ):
            raise IntakeAdmissionError("trusted_roles must be unique and sorted")
        if any(not isinstance(role, ReviewerRole) for role in self.trusted_roles):
            raise IntakeAdmissionError("invalid trusted role")
        valid_from = _time("credential_valid_from", self.credential_valid_from)
        expires_at = _time("credential_expires_at", self.credential_expires_at)
        if expires_at <= valid_from:
            raise IntakeAdmissionError("credential validity interval is invalid")
        if self.credential_revoked_at is not None:
            revoked_at = _time("credential_revoked_at", self.credential_revoked_at)
            if revoked_at < valid_from:
                raise IntakeAdmissionError("credential revocation predates credential validity")
        _token("trust_snapshot_id", self.trust_snapshot_id)
        _sha("trust_snapshot_digest", self.trust_snapshot_digest)
        observed = _time("trust_snapshot_observed_at", self.trust_snapshot_observed_at)
        if observed < valid_from:
            raise IntakeAdmissionError("trust snapshot predates credential validity")
        if _time("trust_snapshot_valid_until", self.trust_snapshot_valid_until) <= observed:
            raise IntakeAdmissionError("trust snapshot validity interval is invalid")


class IndependentIntakeVerifier(Protocol):
    def verify(self, signing_bytes: bytes, attestation: DetachedAttestation) -> VerifiedReviewer:
        """Semantically assert reviewer trust or raise IntakeVerificationError.

        No production implementation is composed by this module.
        """
        ...


EXTERNAL_ACTIVATION_BLOCKERS = frozenset(
    {
        "AUTHORITATIVE_EXTERNAL_DECISION_HISTORY_UNAVAILABLE",
        "AUTHORITATIVE_EXTERNAL_CHECKPOINT_UNAVAILABLE",
        "FIXED_PRODUCTION_VERIFIER_COMPOSITION_UNAVAILABLE",
        "REVIEW_EVIDENCE_DIGESTS_ARE_UNTRUSTED_CLAIMS",
        "TRUSTED_CURRENT_TIME_AND_REVOCATION_SNAPSHOT_UNAVAILABLE",
        "TYPED_REVIEW_EVIDENCE_RESOLVER_UNAVAILABLE",
    }
)


@dataclass(frozen=True, slots=True, init=False)
class IntakeAdmissionStatus:
    dossier_id: str
    state: IntakeAdmissionState
    decision_id: str | None
    blockers: tuple[str, ...]
    execution_authority: str = "NONE"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise IntakeAdmissionError(
            "intake assessment statuses can only be produced by semantic assessment"
        )

    @classmethod
    def _create(
        cls,
        dossier_id: str,
        state: IntakeAdmissionState,
        decision_id: str | None,
        blockers: tuple[str, ...],
    ) -> Self:
        instance = object.__new__(cls)
        object.__setattr__(instance, "dossier_id", dossier_id)
        object.__setattr__(instance, "state", state)
        object.__setattr__(instance, "decision_id", decision_id)
        object.__setattr__(instance, "blockers", blockers)
        object.__setattr__(instance, "execution_authority", "NONE")
        instance.__post_init__()
        return instance

    def __post_init__(self) -> None:
        _text("dossier_id", self.dossier_id)
        if self.execution_authority != "NONE":
            raise IntakeAdmissionError("execution_authority must be NONE")
        if self.decision_id is not None and not _DECISION_ID.fullmatch(self.decision_id):
            raise IntakeAdmissionError("invalid status decision_id")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise IntakeAdmissionError("status blockers must be unique and sorted")
        if self.state is IntakeAdmissionState.REVIEW_REQUIRED:
            if self.decision_id is not None or not self.blockers:
                raise IntakeAdmissionError("review-required status needs blockers and no decision")
        elif self.state in {
            IntakeAdmissionState.VERIFIED_PENDING_EXTERNAL_ACTIVATION,
            IntakeAdmissionState.VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION,
        }:
            if self.decision_id is None or not EXTERNAL_ACTIVATION_BLOCKERS.issubset(self.blockers):
                raise IntakeAdmissionError(
                    "pending activation requires a decision and every external blocker"
                )
        elif self.state is IntakeAdmissionState.REJECTED:
            if self.blockers:
                raise IntakeAdmissionError("rejected status cannot retain blockers")
        else:
            raise IntakeAdmissionError("invalid status state")


def _blocked(dossier_id: str, *blockers: str) -> IntakeAdmissionStatus:
    return IntakeAdmissionStatus._create(
        dossier_id, IntakeAdmissionState.REVIEW_REQUIRED, None, tuple(sorted(set(blockers)))
    )


def assess_intake_decision(
    intake_ledger: CandidateIntakeLedger,
    dossier_id: str,
    decisions: Sequence[SignedIntakeDecision],
    *,
    evaluated_at: datetime,
    verifier: IndependentIntakeVerifier | None = None,
) -> IntakeAdmissionStatus:
    """Assess caller-supplied decision semantics without creating admission authority.

    ``evaluated_at``, ``decisions``, and ``verifier`` are caller inputs.  They can show that a
    statement is internally consistent at a historical instant, but cannot establish current
    authority, complete external history, or production verifier composition.
    """
    now = _time("evaluated_at", evaluated_at)
    try:
        matching_statuses = [
            status
            for status in intake_ledger.list_statuses()
            if status.dossier.dossier_id == dossier_id
        ]
    except CandidateIntakeError as exc:
        raise IntakeAdmissionError("authoritative intake ledger verification failed") from exc
    if len(matching_statuses) != 1:
        return _blocked(dossier_id, "AUTHORITATIVE_DOSSIER_NOT_UNIQUE")
    intake = matching_statuses[0]
    if intake.verdict is IntakeVerdict.REJECT or intake.lifecycle is CandidateLifecycle.REJECTED:
        return IntakeAdmissionStatus._create(dossier_id, IntakeAdmissionState.REJECTED, None, ())
    if any(not isinstance(item, SignedIntakeDecision) for item in decisions):
        return _blocked(dossier_id, "MALFORMED_CALLER_DECISION_INPUT")
    candidates = [item for item in decisions if item.statement.dossier_id == dossier_id]
    if len(candidates) != 1:
        return _blocked(
            dossier_id,
            "SIGNED_DECISION_ABSENT" if not candidates else "DUPLICATE_OR_COMPETING_DECISIONS",
        )
    signed = candidates[0]
    statement = signed.statement
    dossier = intake.dossier
    bindings = (
        statement.dossier_digest == dossier.dossier_digest,
        statement.predecessor_entry_hash == intake.entry_hash,
        statement.predecessor_state is IntakeAdmissionState.REVIEW_REQUIRED,
        statement.catalog_sha256
        == (dossier.closed_family_catalog.sha256 if dossier.closed_family_catalog else None),
        statement.assessment_sha256
        == (dossier.family_assessment.sha256 if dossier.family_assessment else None),
    )
    if not all(bindings):
        return _blocked(dossier_id, "AUTHORITATIVE_BINDING_MISMATCH")
    expected_domains = tuple(sorted(intake.pending_reviews, key=lambda item: item.value))
    actual_domains = tuple(item.domain for item in statement.resolutions)
    if actual_domains != expected_domains:
        return _blocked(dossier_id, "PENDING_REVIEW_DOMAIN_MISMATCH")
    if statement.decision_at > now:
        return _blocked(dossier_id, "DECISION_FROM_FUTURE")
    if statement.expires_at <= now:
        return _blocked(dossier_id, "DECISION_EXPIRED")
    if verifier is None:
        return _blocked(dossier_id, "INDEPENDENT_VERIFIER_UNAVAILABLE")
    try:
        reviewer = verifier.verify(statement.signing_bytes(), signed.attestation)
        if not isinstance(reviewer, VerifiedReviewer):
            raise IntakeVerificationError("verifier returned a malformed reviewer")
    # The verifier is an external trust boundary.  A buggy adapter must fail closed just
    # as a typed verification rejection does; process-control exceptions still propagate.
    except Exception:  # noqa: BLE001
        return _blocked(dossier_id, "ATTESTATION_NOT_VERIFIED")
    required_role = ReviewerRole.INDEPENDENT_INTAKE_ADMISSION_REVIEWER
    trust_matches = (
        reviewer.reviewer_id == statement.reviewer_id,
        reviewer.credential_id == statement.credential_id,
        required_role in reviewer.trusted_roles,
        reviewer.trust_snapshot_id == statement.trust_snapshot_id,
        reviewer.trust_snapshot_digest == statement.trust_snapshot_digest,
        reviewer.trust_snapshot_observed_at == statement.trust_snapshot_observed_at,
        reviewer.trust_snapshot_observed_at <= now < reviewer.trust_snapshot_valid_until,
        reviewer.credential_valid_from <= statement.decision_at,
        now < reviewer.credential_expires_at,
        reviewer.credential_revoked_at is None,
    )
    if not all(trust_matches):
        return _blocked(dossier_id, "REVIEWER_TRUST_INVALID_OR_STALE")
    if statement.outcome is IntakeDecisionOutcome.REJECT:
        return IntakeAdmissionStatus._create(
            dossier_id,
            IntakeAdmissionState.VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION,
            statement.decision_id,
            tuple(sorted(EXTERNAL_ACTIVATION_BLOCKERS)),
        )
    if dossier.closed_family_catalog is None or dossier.family_assessment is None:
        return _blocked(dossier_id, "CATALOG_OR_ASSESSMENT_NOT_BOUND")
    if any(
        resolution.outcome is not ReviewResolutionOutcome.SATISFIED
        for resolution in statement.resolutions
    ):
        return _blocked(dossier_id, "PENDING_REVIEW_UNSATISFIED")
    return IntakeAdmissionStatus._create(
        dossier_id,
        IntakeAdmissionState.VERIFIED_PENDING_EXTERNAL_ACTIVATION,
        statement.decision_id,
        tuple(sorted(EXTERNAL_ACTIVATION_BLOCKERS)),
    )
