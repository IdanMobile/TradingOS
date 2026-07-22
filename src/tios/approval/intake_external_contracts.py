"""Strict data contracts for a future, externally owned intake trust boundary.

These contracts carry public trust metadata and content bindings only.  They do not
install a verifier, sign anything, activate intake, or grant execution authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar, Self, cast

from tios.approval.intake_admission import IntakeDecisionStatement

SCHEMA_VERSION = 1
MAX_DOCUMENT_BYTES = 1_048_576
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Z0-9]+(?:[-_.][A-Z0-9]+)*\Z")
_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{40,64}\Z")


class ExternalContractError(ValueError):
    """External trust material is malformed or non-canonical."""


class ReceiptStatus(StrEnum):
    VERIFIED_PENDING_EXTERNAL_ACTIVATION = "VERIFIED_PENDING_EXTERNAL_ACTIVATION"
    BLOCKED = "BLOCKED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"


def _reject_float(value: str) -> None:
    raise ExternalContractError(f"floating-point value prohibited: {value}")


def _reject_constant(value: str) -> None:
    raise ExternalContractError(f"non-finite number prohibited: {value}")


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ExternalContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _walk(value: object) -> None:
    if isinstance(value, float):
        raise ExternalContractError("floating-point values are prohibited")
    if isinstance(value, str):
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ExternalContractError("control characters are prohibited")
    elif isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ExternalContractError("JSON object keys must be strings")
            _walk(key)
            _walk(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _walk(child)
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise ExternalContractError("unsupported canonical JSON value")


def canonical_json(value: object) -> bytes:
    """Return the single accepted UTF-8 JSON representation."""
    _walk(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def parse_canonical_json(raw: bytes | str) -> Mapping[str, object]:
    if isinstance(raw, str):
        try:
            encoded = raw.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ExternalContractError("invalid Unicode") from exc
    else:
        encoded = raw
    if not encoded or len(encoded) > MAX_DOCUMENT_BYTES:
        raise ExternalContractError("document is empty or too large")
    try:
        text = encoded.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_unique,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalContractError("invalid UTF-8 JSON") from exc
    if not isinstance(value, Mapping):
        raise ExternalContractError("top-level JSON value must be an object")
    _walk(value)
    if canonical_json(value) != encoded:
        raise ExternalContractError("JSON bytes are not canonical")
    return value


def _exact(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(raw) != expected:
        raise ExternalContractError(
            f"{label} fields mismatch; missing={sorted(expected - set(raw))}, "
            f"extra={sorted(set(raw) - expected)}"
        )


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ExternalContractError(f"{name} must be a non-empty trimmed string")
    _walk(value)
    return value


def _token(name: str, value: object) -> str:
    result = _text(name, value)
    if not _TOKEN.fullmatch(result):
        raise ExternalContractError(f"{name} must be a canonical token")
    return result


def _sha(name: str, value: object) -> str:
    result = _text(name, value)
    if not _SHA.fullmatch(result):
        raise ExternalContractError(f"{name} must be a lowercase SHA-256")
    return result


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63:
        raise ExternalContractError(f"{name} must be a bounded non-negative integer")
    return value


def _time(name: str, value: object) -> str:
    text = _text(name, value)
    if not text.endswith("Z"):
        raise ExternalContractError(f"{name} must use UTC Z form")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ExternalContractError(f"{name} is invalid") from exc
    canonical = parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if parsed.microsecond or canonical != text:
        raise ExternalContractError(f"{name} is not canonical")
    return text


def _strings(name: str, value: object, validator: Callable[[str, object], str]) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExternalContractError(f"{name} must be a list")
    result = tuple(validator(name, item) for item in value)
    if result != tuple(sorted(set(result))):
        raise ExternalContractError(f"{name} must be sorted and unique")
    return result


class _Contract:
    DOMAIN: ClassVar[str]

    def to_dict(self) -> dict[str, object]:
        raise NotImplementedError

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    def domain_separated_bytes(self) -> bytes:
        return self.DOMAIN.encode("ascii") + b"\0" + self.canonical_bytes()

    def sha256(self) -> str:
        return hashlib.sha256(self.domain_separated_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class ReviewerCredential(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-REVIEWER-CREDENTIAL/v1"
    credential_id: str
    reviewer_id: str
    reviewer_role: str
    public_key_sha256: str
    ssh_fingerprint: str
    valid_from: str
    valid_until: str
    revoked_at: str | None
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("credential_id", self.credential_id)
        _token("reviewer_id", self.reviewer_id)
        if self.reviewer_role != "INDEPENDENT_INTAKE_ADMISSION_REVIEWER":
            raise ExternalContractError("wrong reviewer role")
        _sha("public_key_sha256", self.public_key_sha256)
        if not _FINGERPRINT.fullmatch(_text("ssh_fingerprint", self.ssh_fingerprint)):
            raise ExternalContractError("invalid SSH fingerprint")
        start, end = _time("valid_from", self.valid_from), _time("valid_until", self.valid_until)
        if start >= end:
            raise ExternalContractError("credential validity interval is invalid")
        if self.revoked_at is not None:
            _time("revoked_at", self.revoked_at)
        if self.execution_authority != "NONE":
            raise ExternalContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "credential_id": self.credential_id,
            "reviewer_id": self.reviewer_id,
            "reviewer_role": self.reviewer_role,
            "public_key_sha256": self.public_key_sha256,
            "ssh_fingerprint": self.ssh_fingerprint,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "revoked_at": self.revoked_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        keys = {
            "schema_version",
            "domain_separator",
            "credential_id",
            "reviewer_id",
            "reviewer_role",
            "public_key_sha256",
            "ssh_fingerprint",
            "valid_from",
            "valid_until",
            "revoked_at",
            "execution_authority",
        }
        _exact(raw, keys, "reviewer credential")
        _header(raw, cls.DOMAIN)
        revoked = raw["revoked_at"]
        if revoked is not None and not isinstance(revoked, str):
            raise ExternalContractError("revoked_at must be string or null")
        return cls(
            _text("credential_id", raw["credential_id"]),
            _text("reviewer_id", raw["reviewer_id"]),
            _text("reviewer_role", raw["reviewer_role"]),
            _text("public_key_sha256", raw["public_key_sha256"]),
            _text("ssh_fingerprint", raw["ssh_fingerprint"]),
            _text("valid_from", raw["valid_from"]),
            _text("valid_until", raw["valid_until"]),
            revoked,
            _text("execution_authority", raw["execution_authority"]),
        )


def _header(raw: Mapping[str, object], domain: str) -> None:
    if raw["schema_version"] != 1 or isinstance(raw["schema_version"], bool):
        raise ExternalContractError("invalid schema_version")
    if raw["domain_separator"] != domain:
        raise ExternalContractError("invalid domain_separator")


@dataclass(frozen=True, slots=True)
class TrustSnapshot(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-TRUST-SNAPSHOT/v1"
    snapshot_id: str
    observed_at: str
    valid_until: str
    credential_digests: tuple[str, ...]
    revocation_krl_sha256: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("snapshot_id", self.snapshot_id)
        if _time("observed_at", self.observed_at) >= _time("valid_until", self.valid_until):
            raise ExternalContractError("snapshot interval invalid")
        if (
            self.credential_digests != tuple(sorted(set(self.credential_digests)))
            or not self.credential_digests
        ):
            raise ExternalContractError("credential_digests must be non-empty, sorted and unique")
        for x in self.credential_digests:
            _sha("credential_digest", x)
        _sha("revocation_krl_sha256", self.revocation_krl_sha256)
        if self.execution_authority != "NONE":
            raise ExternalContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "snapshot_id": self.snapshot_id,
            "observed_at": self.observed_at,
            "valid_until": self.valid_until,
            "credential_digests": list(self.credential_digests),
            "revocation_krl_sha256": self.revocation_krl_sha256,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        _exact(
            raw,
            {
                "schema_version",
                "domain_separator",
                "snapshot_id",
                "observed_at",
                "valid_until",
                "credential_digests",
                "revocation_krl_sha256",
                "execution_authority",
            },
            "trust snapshot",
        )
        _header(raw, cls.DOMAIN)
        return cls(
            _text("snapshot_id", raw["snapshot_id"]),
            _text("observed_at", raw["observed_at"]),
            _text("valid_until", raw["valid_until"]),
            _strings("credential_digests", raw["credential_digests"], _sha),
            _text("revocation_krl_sha256", raw["revocation_krl_sha256"]),
            _text("execution_authority", raw["execution_authority"]),
        )


@dataclass(frozen=True, slots=True)
class ReviewEvidenceEnvelope(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-REVIEW-EVIDENCE/v1"
    evidence_id: str
    decision_signing_sha256: str
    dossier_digest: str
    review_domain: str
    resolution: str
    evidence_digests: tuple[str, ...]
    resolver_sha256: str
    observed_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("evidence_id", self.evidence_id)
        _sha("decision_signing_sha256", self.decision_signing_sha256)
        _sha("dossier_digest", self.dossier_digest)
        if self.review_domain not in {"ACCESS", "DATA", "OPERATOR"}:
            raise ExternalContractError("invalid review_domain")
        if self.resolution not in {"SATISFIED", "UNSATISFIED"}:
            raise ExternalContractError("invalid resolution")
        if (
            self.evidence_digests != tuple(sorted(set(self.evidence_digests)))
            or not self.evidence_digests
        ):
            raise ExternalContractError("evidence_digests must be non-empty, sorted and unique")
        for x in self.evidence_digests:
            _sha("evidence_digest", x)
        _sha("resolver_sha256", self.resolver_sha256)
        _time("observed_at", self.observed_at)
        if self.execution_authority != "NONE":
            raise ExternalContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "evidence_id": self.evidence_id,
            "decision_signing_sha256": self.decision_signing_sha256,
            "dossier_digest": self.dossier_digest,
            "review_domain": self.review_domain,
            "resolution": self.resolution,
            "evidence_digests": list(self.evidence_digests),
            "resolver_sha256": self.resolver_sha256,
            "observed_at": self.observed_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        keys = {
            "schema_version",
            "domain_separator",
            "evidence_id",
            "decision_signing_sha256",
            "dossier_digest",
            "review_domain",
            "resolution",
            "evidence_digests",
            "resolver_sha256",
            "observed_at",
            "execution_authority",
        }
        _exact(raw, keys, "review evidence")
        _header(raw, cls.DOMAIN)
        return cls(
            _text("evidence_id", raw["evidence_id"]),
            _text("decision_signing_sha256", raw["decision_signing_sha256"]),
            _text("dossier_digest", raw["dossier_digest"]),
            _text("review_domain", raw["review_domain"]),
            _text("resolution", raw["resolution"]),
            _strings("evidence_digests", raw["evidence_digests"], _sha),
            _text("resolver_sha256", raw["resolver_sha256"]),
            _text("observed_at", raw["observed_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


@dataclass(frozen=True, slots=True)
class HistoryEntry(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-HISTORY-ENTRY/v1"
    sequence: int
    previous_entry_sha256: str
    decision_signing_sha256: str
    attestation_sha256: str
    trust_snapshot_sha256: str
    evidence_envelope_sha256s: tuple[str, ...]
    recorded_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _integer("sequence", self.sequence)
        if self.sequence == 0:
            if self.previous_entry_sha256 != "0" * 64:
                raise ExternalContractError("genesis predecessor mismatch")
        else:
            _sha("previous_entry_sha256", self.previous_entry_sha256)
        for n, v in (
            ("decision_signing_sha256", self.decision_signing_sha256),
            ("attestation_sha256", self.attestation_sha256),
            ("trust_snapshot_sha256", self.trust_snapshot_sha256),
        ):
            _sha(n, v)
        if self.evidence_envelope_sha256s != tuple(sorted(set(self.evidence_envelope_sha256s))):
            raise ExternalContractError("evidence envelope digests must be sorted and unique")
        for x in self.evidence_envelope_sha256s:
            _sha("evidence_envelope_sha256", x)
        _time("recorded_at", self.recorded_at)
        if self.execution_authority != "NONE":
            raise ExternalContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "sequence": self.sequence,
            "previous_entry_sha256": self.previous_entry_sha256,
            "decision_signing_sha256": self.decision_signing_sha256,
            "attestation_sha256": self.attestation_sha256,
            "trust_snapshot_sha256": self.trust_snapshot_sha256,
            "evidence_envelope_sha256s": list(self.evidence_envelope_sha256s),
            "recorded_at": self.recorded_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        keys = {
            "schema_version",
            "domain_separator",
            "sequence",
            "previous_entry_sha256",
            "decision_signing_sha256",
            "attestation_sha256",
            "trust_snapshot_sha256",
            "evidence_envelope_sha256s",
            "recorded_at",
            "execution_authority",
        }
        _exact(raw, keys, "history entry")
        _header(raw, cls.DOMAIN)
        return cls(
            _integer("sequence", raw["sequence"]),
            _text("previous_entry_sha256", raw["previous_entry_sha256"]),
            _text("decision_signing_sha256", raw["decision_signing_sha256"]),
            _text("attestation_sha256", raw["attestation_sha256"]),
            _text("trust_snapshot_sha256", raw["trust_snapshot_sha256"]),
            _strings("evidence_envelope_sha256s", raw["evidence_envelope_sha256s"], _sha),
            _text("recorded_at", raw["recorded_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


@dataclass(frozen=True, slots=True)
class ExternalCheckpoint(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-EXTERNAL-CHECKPOINT/v1"
    sequence: int
    history_entry_sha256: str
    previous_checkpoint_sha256: str
    created_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _integer("sequence", self.sequence)
        _sha("history_entry_sha256", self.history_entry_sha256)
        _sha("previous_checkpoint_sha256", self.previous_checkpoint_sha256)
        _time("created_at", self.created_at)
        if self.execution_authority != "NONE":
            raise ExternalContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "sequence": self.sequence,
            "history_entry_sha256": self.history_entry_sha256,
            "previous_checkpoint_sha256": self.previous_checkpoint_sha256,
            "created_at": self.created_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        keys = {
            "schema_version",
            "domain_separator",
            "sequence",
            "history_entry_sha256",
            "previous_checkpoint_sha256",
            "created_at",
            "execution_authority",
        }
        _exact(raw, keys, "external checkpoint")
        _header(raw, cls.DOMAIN)
        return cls(
            _integer("sequence", raw["sequence"]),
            _text("history_entry_sha256", raw["history_entry_sha256"]),
            _text("previous_checkpoint_sha256", raw["previous_checkpoint_sha256"]),
            _text("created_at", raw["created_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


@dataclass(frozen=True, slots=True)
class ExternalAssessmentReceipt(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-EXTERNAL-ASSESSMENT-RECEIPT/v1"
    receipt_id: str
    decision_signing_sha256: str
    history_entry_sha256: str
    checkpoint_sha256: str
    trust_snapshot_sha256: str
    evidence_envelope_sha256s: tuple[str, ...]
    status: ReceiptStatus
    blockers: tuple[str, ...]
    issued_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("receipt_id", self.receipt_id)
        for n, v in (
            ("decision_signing_sha256", self.decision_signing_sha256),
            ("history_entry_sha256", self.history_entry_sha256),
            ("checkpoint_sha256", self.checkpoint_sha256),
            ("trust_snapshot_sha256", self.trust_snapshot_sha256),
        ):
            _sha(n, v)
        if self.evidence_envelope_sha256s != tuple(sorted(set(self.evidence_envelope_sha256s))):
            raise ExternalContractError("evidence envelope digests must be sorted and unique")
        for x in self.evidence_envelope_sha256s:
            _sha("evidence_envelope_sha256", x)
        if not isinstance(self.status, ReceiptStatus):
            raise ExternalContractError("invalid receipt status")
        if self.blockers != tuple(sorted(set(self.blockers))) or not self.blockers:
            raise ExternalContractError("blockers must be non-empty, sorted and unique")
        for x in self.blockers:
            _token("blocker", x)
        _time("issued_at", self.issued_at)
        if self.execution_authority != "NONE":
            raise ExternalContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "receipt_id": self.receipt_id,
            "decision_signing_sha256": self.decision_signing_sha256,
            "history_entry_sha256": self.history_entry_sha256,
            "checkpoint_sha256": self.checkpoint_sha256,
            "trust_snapshot_sha256": self.trust_snapshot_sha256,
            "evidence_envelope_sha256s": list(self.evidence_envelope_sha256s),
            "status": self.status.value,
            "blockers": list(self.blockers),
            "issued_at": self.issued_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        keys = {
            "schema_version",
            "domain_separator",
            "receipt_id",
            "decision_signing_sha256",
            "history_entry_sha256",
            "checkpoint_sha256",
            "trust_snapshot_sha256",
            "evidence_envelope_sha256s",
            "status",
            "blockers",
            "issued_at",
            "execution_authority",
        }
        _exact(raw, keys, "external assessment receipt")
        _header(raw, cls.DOMAIN)
        try:
            status = ReceiptStatus(_text("status", raw["status"]))
        except ValueError as exc:
            raise ExternalContractError("invalid receipt status") from exc
        return cls(
            _text("receipt_id", raw["receipt_id"]),
            _text("decision_signing_sha256", raw["decision_signing_sha256"]),
            _text("history_entry_sha256", raw["history_entry_sha256"]),
            _text("checkpoint_sha256", raw["checkpoint_sha256"]),
            _text("trust_snapshot_sha256", raw["trust_snapshot_sha256"]),
            _strings("evidence_envelope_sha256s", raw["evidence_envelope_sha256s"], _sha),
            status,
            _strings("blockers", raw["blockers"], _token),
            _text("issued_at", raw["issued_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


def parse_contract[T](raw: bytes | str, contract_type: type[T]) -> T:
    parser = getattr(contract_type, "from_mapping", None)
    if parser is None:
        raise ExternalContractError("unsupported contract type")
    return cast(T, parser(parse_canonical_json(raw)))


def decision_signing_sha256(statement: IntakeDecisionStatement) -> str:
    """Bind exactly to the existing decision module's domain-separated signing bytes."""
    if not isinstance(statement, IntakeDecisionStatement):
        raise ExternalContractError("wrong decision type")
    return hashlib.sha256(statement.signing_bytes()).hexdigest()
