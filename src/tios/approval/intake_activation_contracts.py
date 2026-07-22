"""Pending-only contracts for a future external intake activation authority.

The records in this module bind setup evidence.  They cannot admit a decision,
mutate authoritative state, or grant execution authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar, Self, cast

from tios.approval.intake_external_contracts import (
    ExternalContractError,
    canonical_json,
    parse_canonical_json,
)

MAX_DOCUMENT_BYTES = 1_048_576
MAX_TOKEN_BYTES = 128
ACTIVATION_STREAM_ID = "INTAKE-ACTIVATION-AUTHORITY"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Z0-9]+(?:[-_.][A-Z0-9]+)*\Z")


class ActivationContractError(ExternalContractError):
    """Activation material is malformed, ambiguous, or non-canonical."""


class ActivationStatus(StrEnum):
    ACTIVE_NO_DECISIONS = "ACTIVE_NO_DECISIONS"
    BLOCKED = "BLOCKED"


def _exact(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    if set(raw) != expected:
        raise ActivationContractError(
            f"{label} fields mismatch; missing={sorted(expected - set(raw))}, "
            f"extra={sorted(set(raw) - expected)}"
        )


def _header(raw: Mapping[str, object], domain: str) -> None:
    if raw["schema_version"] != 1 or isinstance(raw["schema_version"], bool):
        raise ActivationContractError("invalid schema_version")
    if raw["domain_separator"] != domain:
        raise ActivationContractError("invalid domain_separator")


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ActivationContractError(f"{name} must be a non-empty trimmed string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ActivationContractError(f"{name} contains a control character")
    return value


def _token(name: str, value: object) -> str:
    result = _text(name, value)
    if len(result.encode("utf-8")) > MAX_TOKEN_BYTES or not _TOKEN.fullmatch(result):
        raise ActivationContractError(f"{name} must be a canonical token")
    return result


def _sha(name: str, value: object) -> str:
    result = _text(name, value)
    if not _SHA256.fullmatch(result):
        raise ActivationContractError(f"{name} must be a lowercase SHA-256")
    return result


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63:
        raise ActivationContractError(f"{name} must be a bounded non-negative integer")
    return value


def _time(name: str, value: object) -> str:
    text = _text(name, value)
    if not text.endswith("Z"):
        raise ActivationContractError(f"{name} must use UTC Z form")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ActivationContractError(f"{name} is invalid") from exc
    canonical = parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if parsed.microsecond or canonical != text:
        raise ActivationContractError(f"{name} is not canonical")
    return text


def _tokens(name: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ActivationContractError(f"{name} must be a list")
    result = tuple(_token(name, item) for item in value)
    if result != tuple(sorted(set(result))):
        raise ActivationContractError(f"{name} must be sorted and unique")
    return result


class _Contract:
    DOMAIN: ClassVar[str]

    def to_dict(self) -> dict[str, object]:
        raise NotImplementedError

    def canonical_bytes(self) -> bytes:
        return canonical_json(self.to_dict())

    def signing_bytes(self) -> bytes:
        return self.DOMAIN.encode("ascii") + b"\0" + self.canonical_bytes()

    def sha256(self) -> str:
        return hashlib.sha256(self.signing_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class AuthorityGenesis(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-AUTHORITY-GENESIS/v1"
    genesis_id: str
    installed_helper_sha256: str
    source_bundle_sha256: str
    activation_policy_sha256: str
    allowed_signers_sha256: str
    revocation_krl_sha256: str
    trust_snapshot_sha256: str
    initialized_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("genesis_id", self.genesis_id)
        for name in (
            "installed_helper_sha256",
            "source_bundle_sha256",
            "activation_policy_sha256",
            "allowed_signers_sha256",
            "revocation_krl_sha256",
            "trust_snapshot_sha256",
        ):
            _sha(name, getattr(self, name))
        _time("initialized_at", self.initialized_at)
        if self.execution_authority != "NONE":
            raise ActivationContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "genesis_id": self.genesis_id,
            "installed_helper_sha256": self.installed_helper_sha256,
            "source_bundle_sha256": self.source_bundle_sha256,
            "activation_policy_sha256": self.activation_policy_sha256,
            "allowed_signers_sha256": self.allowed_signers_sha256,
            "revocation_krl_sha256": self.revocation_krl_sha256,
            "trust_snapshot_sha256": self.trust_snapshot_sha256,
            "initialized_at": self.initialized_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "schema_version",
            "domain_separator",
            "genesis_id",
            "installed_helper_sha256",
            "source_bundle_sha256",
            "activation_policy_sha256",
            "allowed_signers_sha256",
            "revocation_krl_sha256",
            "trust_snapshot_sha256",
            "initialized_at",
            "execution_authority",
        }
        _exact(raw, fields, "authority genesis")
        _header(raw, cls.DOMAIN)
        return cls(
            _text("genesis_id", raw["genesis_id"]),
            _text("installed_helper_sha256", raw["installed_helper_sha256"]),
            _text("source_bundle_sha256", raw["source_bundle_sha256"]),
            _text("activation_policy_sha256", raw["activation_policy_sha256"]),
            _text("allowed_signers_sha256", raw["allowed_signers_sha256"]),
            _text("revocation_krl_sha256", raw["revocation_krl_sha256"]),
            _text("trust_snapshot_sha256", raw["trust_snapshot_sha256"]),
            _text("initialized_at", raw["initialized_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


@dataclass(frozen=True, slots=True)
class _Evidence(_Contract):
    evidence_id: str
    subject_sha256: str
    artifact_sha256s: tuple[str, ...]
    reviewer_credential_sha256: str
    observed_at: str
    valid_until: str
    resolution: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("evidence_id", self.evidence_id)
        _sha("subject_sha256", self.subject_sha256)
        if not self.artifact_sha256s or self.artifact_sha256s != tuple(
            sorted(set(self.artifact_sha256s))
        ):
            raise ActivationContractError("artifact_sha256s must be non-empty, sorted and unique")
        for digest in self.artifact_sha256s:
            _sha("artifact_sha256", digest)
        _sha("reviewer_credential_sha256", self.reviewer_credential_sha256)
        if _time("observed_at", self.observed_at) >= _time("valid_until", self.valid_until):
            raise ActivationContractError("evidence validity interval is invalid")
        if self.resolution not in {"SATISFIED", "UNSATISFIED"}:
            raise ActivationContractError("invalid evidence resolution")
        if self.execution_authority != "NONE":
            raise ActivationContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "evidence_id": self.evidence_id,
            "subject_sha256": self.subject_sha256,
            "artifact_sha256s": list(self.artifact_sha256s),
            "reviewer_credential_sha256": self.reviewer_credential_sha256,
            "observed_at": self.observed_at,
            "valid_until": self.valid_until,
            "resolution": self.resolution,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "schema_version",
            "domain_separator",
            "evidence_id",
            "subject_sha256",
            "artifact_sha256s",
            "reviewer_credential_sha256",
            "observed_at",
            "valid_until",
            "resolution",
            "execution_authority",
        }
        _exact(raw, fields, "signed evidence")
        _header(raw, cls.DOMAIN)
        artifacts = raw["artifact_sha256s"]
        if not isinstance(artifacts, list):
            raise ActivationContractError("artifact_sha256s must be a list")
        return cls(
            _text("evidence_id", raw["evidence_id"]),
            _text("subject_sha256", raw["subject_sha256"]),
            tuple(_text("artifact_sha256", item) for item in artifacts),
            _text("reviewer_credential_sha256", raw["reviewer_credential_sha256"]),
            _text("observed_at", raw["observed_at"]),
            _text("valid_until", raw["valid_until"]),
            _text("resolution", raw["resolution"]),
            _text("execution_authority", raw["execution_authority"]),
        )


@dataclass(frozen=True, slots=True)
class AccessEvidence(_Evidence):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-ACTIVATION-ACCESS-EVIDENCE/v1"


@dataclass(frozen=True, slots=True)
class DataEvidence(_Evidence):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-ACTIVATION-DATA-EVIDENCE/v1"


@dataclass(frozen=True, slots=True)
class OperatorEvidence(_Evidence):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-ACTIVATION-OPERATOR-EVIDENCE/v1"


@dataclass(frozen=True, slots=True)
class MonotonicHead(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-MONOTONIC-HEAD/v1"
    stream_id: str
    sequence: int
    previous_head_sha256: str
    record_sha256: str
    observed_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("stream_id", self.stream_id)
        _integer("sequence", self.sequence)
        _sha("previous_head_sha256", self.previous_head_sha256)
        if self.sequence == 0 and self.previous_head_sha256 != "0" * 64:
            raise ActivationContractError("genesis head predecessor must be zero")
        _sha("record_sha256", self.record_sha256)
        _time("observed_at", self.observed_at)
        if self.execution_authority != "NONE":
            raise ActivationContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "previous_head_sha256": self.previous_head_sha256,
            "record_sha256": self.record_sha256,
            "observed_at": self.observed_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "schema_version",
            "domain_separator",
            "stream_id",
            "sequence",
            "previous_head_sha256",
            "record_sha256",
            "observed_at",
            "execution_authority",
        }
        _exact(raw, fields, "monotonic head")
        _header(raw, cls.DOMAIN)
        return cls(
            _text("stream_id", raw["stream_id"]),
            _integer("sequence", raw["sequence"]),
            _text("previous_head_sha256", raw["previous_head_sha256"]),
            _text("record_sha256", raw["record_sha256"]),
            _text("observed_at", raw["observed_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


def validate_head_advance(previous: MonotonicHead, candidate: MonotonicHead) -> None:
    """Fail closed unless *candidate* is the one valid next head."""
    if candidate.stream_id != previous.stream_id:
        raise ActivationContractError("monotonic head stream changed")
    if candidate.sequence != previous.sequence + 1:
        raise ActivationContractError("monotonic head sequence is not contiguous")
    if candidate.previous_head_sha256 != previous.sha256():
        raise ActivationContractError("monotonic head predecessor mismatch")
    if candidate.observed_at < previous.observed_at:
        raise ActivationContractError("trusted time rollback")


@dataclass(frozen=True, slots=True)
class ActivationStatusReceipt(_Contract):
    DOMAIN: ClassVar[str] = "TIOS/INTAKE-ACTIVATION-STATUS-RECEIPT/v1"
    receipt_id: str
    authority_genesis_sha256: str
    monotonic_head_sha256: str
    activation_policy_sha256: str
    trust_snapshot_sha256: str
    status: ActivationStatus
    blockers: tuple[str, ...]
    issued_at: str
    expires_at: str
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        _token("receipt_id", self.receipt_id)
        for name in (
            "authority_genesis_sha256",
            "monotonic_head_sha256",
            "activation_policy_sha256",
            "trust_snapshot_sha256",
        ):
            _sha(name, getattr(self, name))
        if not isinstance(self.status, ActivationStatus):
            raise ActivationContractError("invalid activation status")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ActivationContractError("blockers must be sorted and unique")
        for blocker in self.blockers:
            _token("blocker", blocker)
        if self.status is ActivationStatus.ACTIVE_NO_DECISIONS and self.blockers:
            raise ActivationContractError("active receipt cannot carry blockers")
        if self.status is ActivationStatus.BLOCKED and not self.blockers:
            raise ActivationContractError("blocked receipt requires blockers")
        if _time("issued_at", self.issued_at) >= _time("expires_at", self.expires_at):
            raise ActivationContractError("receipt validity interval is invalid")
        if self.execution_authority != "NONE":
            raise ActivationContractError("execution_authority must be NONE")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "domain_separator": self.DOMAIN,
            "receipt_id": self.receipt_id,
            "authority_genesis_sha256": self.authority_genesis_sha256,
            "monotonic_head_sha256": self.monotonic_head_sha256,
            "activation_policy_sha256": self.activation_policy_sha256,
            "trust_snapshot_sha256": self.trust_snapshot_sha256,
            "status": self.status.value,
            "blockers": list(self.blockers),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "execution_authority": "NONE",
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "schema_version",
            "domain_separator",
            "receipt_id",
            "authority_genesis_sha256",
            "monotonic_head_sha256",
            "activation_policy_sha256",
            "trust_snapshot_sha256",
            "status",
            "blockers",
            "issued_at",
            "expires_at",
            "execution_authority",
        }
        _exact(raw, fields, "activation status receipt")
        _header(raw, cls.DOMAIN)
        try:
            status = ActivationStatus(_text("status", raw["status"]))
        except ValueError as exc:
            raise ActivationContractError("invalid activation status") from exc
        return cls(
            _text("receipt_id", raw["receipt_id"]),
            _text("authority_genesis_sha256", raw["authority_genesis_sha256"]),
            _text("monotonic_head_sha256", raw["monotonic_head_sha256"]),
            _text("activation_policy_sha256", raw["activation_policy_sha256"]),
            _text("trust_snapshot_sha256", raw["trust_snapshot_sha256"]),
            status,
            _tokens("blockers", raw["blockers"]),
            _text("issued_at", raw["issued_at"]),
            _text("expires_at", raw["expires_at"]),
            _text("execution_authority", raw["execution_authority"]),
        )


def validate_activation_snapshot(
    receipt: ActivationStatusReceipt,
    genesis: AuthorityGenesis,
    head: MonotonicHead,
    *,
    policy_sha256: str,
    trust_snapshot_sha256: str,
    observed_at: str,
) -> None:
    """Validate all records required to interpret an active-no-decisions receipt.

    This is validation only.  It neither persists a head nor activates any consumer.
    """
    policy = _sha("policy_sha256", policy_sha256)
    trust = _sha("trust_snapshot_sha256", trust_snapshot_sha256)
    now = _time("observed_at", observed_at)
    if receipt.status is not ActivationStatus.ACTIVE_NO_DECISIONS:
        raise ActivationContractError("activation snapshot requires ACTIVE_NO_DECISIONS receipt")
    if receipt.authority_genesis_sha256 != genesis.sha256():
        raise ActivationContractError("receipt does not bind supplied authority genesis")
    if receipt.monotonic_head_sha256 != head.sha256():
        raise ActivationContractError("receipt does not bind supplied monotonic head")
    if head.stream_id != ACTIVATION_STREAM_ID:
        raise ActivationContractError("activation head stream identity mismatch")
    if head.sequence != 0 or head.record_sha256 != genesis.sha256():
        raise ActivationContractError("activation head is not the initialized genesis head")
    if receipt.activation_policy_sha256 != policy or genesis.activation_policy_sha256 != policy:
        raise ActivationContractError("activation policy binding mismatch")
    if receipt.trust_snapshot_sha256 != trust or genesis.trust_snapshot_sha256 != trust:
        raise ActivationContractError("trust snapshot binding mismatch")
    if not genesis.initialized_at <= head.observed_at <= receipt.issued_at <= now:
        raise ActivationContractError("activation time chain is incoherent or rolled back")
    if now >= receipt.expires_at:
        raise ActivationContractError("activation receipt expired")


def parse_activation_contract[T](raw: bytes | str, contract_type: type[T]) -> T:
    if isinstance(raw, bytes) and len(raw) > MAX_DOCUMENT_BYTES:
        raise ActivationContractError("document is too large")
    parser = getattr(contract_type, "from_mapping", None)
    if parser is None:
        raise ActivationContractError("unsupported activation contract type")
    try:
        mapping = parse_canonical_json(raw)
    except ExternalContractError as exc:
        raise ActivationContractError(str(exc)) from exc
    return cast(T, parser(mapping))
