"""Fail-closed research-candidate intake ledger.

This Phase-2 boundary can retain a dossier as ``REVIEW_REQUIRED`` or reject it.  It
cannot admit a candidate: the repository does not yet have a cryptographically or
externally trusted independent-review identity.  Phase 2b must integrate typed independent
decisions before any campaign consumer may interpret a dossier as admitted.

Every physical registration is hash-chained and all referenced metadata is reverified on
every read.  The chain detects middle deletion, replacement, and reordering.  It cannot
detect tail truncation or a complete unkeyed rewrite without an external checkpoint, so
this ledger is deliberately not an approval boundary.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Self

SCHEMA_VERSION = 1
LEDGER_PARTS = ("artifacts", "research", "admission", "ledger.jsonl")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Z0-9]+(?:[-_.][A-Z0-9]+)*\Z")
_DOSSIER_ID = re.compile(r"RC-[0-9a-f]{32}\Z")
_ENTRY_HASH = re.compile(r"LE-[0-9a-f]{64}\Z")
_FORBIDDEN_TERMS = (
    "holdout",
    "sealed",
    "outcome",
    "performance",
    "result",
    "sharpe",
    "pnl",
    "return",
    "profit",
    "drawdown",
    "score",
    "backtest",
    "evaluation",
    "metric",
)
_OUTCOME_FIELDS = frozenset(
    {
        "alpha",
        "drawdown",
        "equity_curve",
        "event_count",
        "loss",
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


class CandidateIntakeError(RuntimeError):
    """Raised when intake evidence or storage fails closed."""


class ReferencePurpose(StrEnum):
    DATA_PACKAGE = "DATA_PACKAGE"
    CLOSED_FAMILY_CATALOG = "CLOSED_FAMILY_CATALOG"
    FAMILY_ASSESSMENT = "FAMILY_ASSESSMENT"
    LAWFUL_EVIDENCE = "LAWFUL_EVIDENCE"


class LawfulEvidenceClass(StrEnum):
    NONE = "NONE"
    OFFICIAL_AUTHORITATIVE_SOURCE = "OFFICIAL_AUTHORITATIVE_SOURCE"
    LICENSED_AUTHORITATIVE_SOURCE = "LICENSED_AUTHORITATIVE_SOURCE"
    OPERATOR_SUPPLIED_SPEC_AND_UNSEEN_PIT_DATA = "OPERATOR_SUPPLIED_SPEC_AND_UNSEEN_PIT_DATA"
    PREREGISTERED_PROSPECTIVE_OBSERVATIONS = "PREREGISTERED_PROSPECTIVE_OBSERVATIONS"


class ReviewDomain(StrEnum):
    DATA = "DATA"
    ACCESS = "ACCESS"
    OPERATOR = "OPERATOR"


class IntakeVerdict(StrEnum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECT = "REJECT"


class CandidateLifecycle(StrEnum):
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


def _trimmed(name: str, value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise CandidateIntakeError(f"{name} must be a non-empty trimmed string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise CandidateIntakeError(f"{name} must not contain control characters")
    return value


def _sha256(name: str, value: object) -> str:
    text = _trimmed(name, value)
    if not _SHA256.fullmatch(text):
        raise CandidateIntakeError(f"{name} must be a lowercase SHA-256 digest")
    return text


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _digest(payload: object) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _exact(raw: Mapping[str, object], expected: set[str], label: str) -> None:
    missing, extra = expected - raw.keys(), raw.keys() - expected
    if missing or extra:
        raise CandidateIntakeError(
            f"{label} fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _schema(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value != SCHEMA_VERSION:
        raise CandidateIntakeError(f"schema_version must be integer {SCHEMA_VERSION}")


def _enum(enum_type: type[StrEnum], value: object, field: str) -> StrEnum:
    try:
        return enum_type(_trimmed(field, value))
    except ValueError as exc:
        raise CandidateIntakeError(f"invalid {field}: {value}") from exc


def _validate_path_parts(parts: tuple[str, ...], label: str) -> None:
    if any(term in part.casefold() for part in parts for term in _FORBIDDEN_TERMS):
        raise CandidateIntakeError(f"{label} uses a prohibited namespace")


def _relative_ref(ref: str, purpose: ReferencePurpose) -> tuple[str, ...]:
    text = _trimmed("ref", ref)
    if "\\" in text:
        raise CandidateIntakeError("ref must use POSIX separators")
    path = PurePosixPath(text)
    if text != path.as_posix():
        raise CandidateIntakeError("ref text must be exactly canonical POSIX form")
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise CandidateIntakeError("ref must be a normalized repository-relative path")
    parts = tuple(path.parts)
    if parts[0] != parts[0].casefold():
        raise CandidateIntakeError("ref namespace must be canonical lowercase")
    _validate_path_parts(parts, "ref")
    allowed = {
        ReferencePurpose.DATA_PACKAGE: (("research",),),
        ReferencePurpose.CLOSED_FAMILY_CATALOG: (("research",), ("docs", "supervisor")),
        ReferencePurpose.FAMILY_ASSESSMENT: (("research",), ("docs", "supervisor")),
        ReferencePurpose.LAWFUL_EVIDENCE: (
            ("research",),
            ("docs", "supervisor"),
            ("decisions",),
            ("artifacts", "research", "admission", "evidence"),
        ),
    }
    if not any(parts[: len(prefix)] == prefix for prefix in allowed[purpose]):
        raise CandidateIntakeError(f"ref is outside allowed namespaces for {purpose.value}")
    return parts


def _open_regular_read(root: Path, parts: tuple[str, ...]) -> int:
    """Open a workspace file without following any path-component symlink."""
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    current_fd = root_fd
    try:
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=current_fd,
            )
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd
        file_fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=current_fd)
        info = os.fstat(file_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(file_fd)
            raise CandidateIntakeError("referenced file must be regular with one hard link")
        return file_fd
    except OSError as exc:
        raise CandidateIntakeError("reference cannot be opened without following links") from exc
    finally:
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


def _read_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    while chunk := os.read(fd, 1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode):
            raise CandidateIntakeError("workspace root must not contain symlink components")


def _write_fd(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written < 1:
            raise CandidateIntakeError("ledger append made no progress")
        view = view[written:]


@dataclass(frozen=True, slots=True)
class DigestReference:
    """Unresolved strict-registry identity; never claims registry verification."""

    record_id: str
    sha256: str

    def __post_init__(self) -> None:
        if not _ID.fullmatch(_trimmed("record_id", self.record_id)):
            raise CandidateIntakeError(f"invalid record_id: {self.record_id}")
        _sha256("sha256", self.sha256)

    def to_dict(self) -> dict[str, str]:
        return {"record_id": self.record_id, "sha256": self.sha256}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        _exact(raw, {"record_id", "sha256"}, "digest reference")
        return cls(_trimmed("record_id", raw["record_id"]), _sha256("sha256", raw["sha256"]))


@dataclass(frozen=True, slots=True)
class WorkspaceFileReference:
    ref: str
    sha256: str
    purpose: ReferencePurpose

    def __post_init__(self) -> None:
        if not isinstance(self.purpose, ReferencePurpose):
            raise CandidateIntakeError("reference purpose is invalid")
        _relative_ref(self.ref, self.purpose)
        _sha256("sha256", self.sha256)

    @classmethod
    def capture(cls, root: Path, ref: str, purpose: ReferencePurpose) -> Self:
        resolved_root = root.resolve(strict=True)
        parts = _relative_ref(ref, purpose)
        fd = _open_regular_read(resolved_root, parts)
        try:
            digest = hashlib.sha256(_read_fd(fd)).hexdigest()
        finally:
            os.close(fd)
        return cls(ref, digest, purpose)

    def read_verified(self, root: Path, purpose: ReferencePurpose) -> bytes:
        if self.purpose is not purpose:
            raise CandidateIntakeError(f"reference purpose must be {purpose.value}")
        fd = _open_regular_read(root.resolve(strict=True), _relative_ref(self.ref, self.purpose))
        try:
            payload = _read_fd(fd)
        finally:
            os.close(fd)
        if hashlib.sha256(payload).hexdigest() != self.sha256:
            raise CandidateIntakeError(f"reference SHA-256 mismatch: {self.ref}")
        return payload

    def to_dict(self) -> dict[str, str]:
        return {"ref": self.ref, "sha256": self.sha256, "purpose": self.purpose.value}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        _exact(raw, {"ref", "sha256", "purpose"}, "workspace file reference")
        purpose = ReferencePurpose(_enum(ReferencePurpose, raw["purpose"], "purpose"))
        return cls(_trimmed("ref", raw["ref"]), _sha256("sha256", raw["sha256"]), purpose)


@dataclass(frozen=True, slots=True)
class ClosedFamilyComparison:
    nearest_family_ids: tuple[str, ...]
    matches_closed_family: bool
    rescue_requested: bool = False
    version_reset_requested: bool = False

    def __post_init__(self) -> None:
        canonical = tuple(sorted(self.nearest_family_ids))
        if self.nearest_family_ids != canonical or len(canonical) != len(set(canonical)):
            raise CandidateIntakeError("nearest_family_ids must be unique and sorted")
        for family_id in self.nearest_family_ids:
            if not _ID.fullmatch(_trimmed("nearest_family_ids", family_id)):
                raise CandidateIntakeError(f"invalid family identifier: {family_id}")
        flags = (self.matches_closed_family, self.rescue_requested, self.version_reset_requested)
        if any(not isinstance(value, bool) for value in flags):
            raise CandidateIntakeError("closed-family flags must be booleans")
        if self.matches_closed_family and not self.nearest_family_ids:
            raise CandidateIntakeError("a family match requires a nearest family")

    @classmethod
    def create(
        cls,
        nearest_family_ids: tuple[str, ...],
        matches_closed_family: bool,
        rescue_requested: bool = False,
        version_reset_requested: bool = False,
    ) -> Self:
        return cls(
            tuple(sorted(nearest_family_ids)),
            matches_closed_family,
            rescue_requested,
            version_reset_requested,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "nearest_family_ids": list(self.nearest_family_ids),
            "matches_closed_family": self.matches_closed_family,
            "rescue_requested": self.rescue_requested,
            "version_reset_requested": self.version_reset_requested,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "nearest_family_ids",
            "matches_closed_family",
            "rescue_requested",
            "version_reset_requested",
        }
        _exact(raw, fields, "closed-family comparison")
        nearest = raw["nearest_family_ids"]
        if not isinstance(nearest, list) or any(not isinstance(item, str) for item in nearest):
            raise CandidateIntakeError("nearest_family_ids must be a list of strings")
        matches = raw["matches_closed_family"]
        rescue = raw["rescue_requested"]
        reset = raw["version_reset_requested"]
        if (
            not isinstance(matches, bool)
            or not isinstance(rescue, bool)
            or not isinstance(reset, bool)
        ):
            raise CandidateIntakeError("closed-family flags must be booleans")
        return cls(tuple(nearest), matches, rescue, reset)


def _unique_digest_refs(refs: tuple[DigestReference, ...], field: str) -> None:
    by_id: dict[str, str] = {}
    for ref in refs:
        previous = by_id.setdefault(ref.record_id, ref.sha256)
        if previous != ref.sha256:
            raise CandidateIntakeError(f"{field} has conflicting hashes for {ref.record_id}")
    if len(by_id) != len(refs):
        raise CandidateIntakeError(f"{field} has duplicate logical record IDs")


def _unique_file_refs(refs: tuple[WorkspaceFileReference, ...], field: str) -> None:
    by_ref: dict[str, str] = {}
    for ref in refs:
        previous = by_ref.setdefault(ref.ref, ref.sha256)
        if previous != ref.sha256:
            raise CandidateIntakeError(f"{field} has conflicting hashes for {ref.ref}")
    if len(by_ref) != len(refs):
        raise CandidateIntakeError(f"{field} has duplicate logical refs")


@dataclass(frozen=True, slots=True)
class CandidateDossier:
    dossier_id: str
    dossier_digest: str
    research_input_digest: str
    source_records: tuple[DigestReference, ...]
    hypothesis: DigestReference
    family_id: str
    comparison: ClosedFamilyComparison
    closed_family_catalog: WorkspaceFileReference | None
    family_assessment: WorkspaceFileReference | None
    dataset_packages: tuple[WorkspaceFileReference, ...]
    canonical_spec_sha256: str
    lawful_evidence_class: LawfulEvidenceClass
    lawful_evidence: WorkspaceFileReference | None
    execution_authority: str = "NONE"

    def __post_init__(self) -> None:
        if not _DOSSIER_ID.fullmatch(self.dossier_id):
            raise CandidateIntakeError("invalid dossier_id")
        _sha256("dossier_digest", self.dossier_digest)
        _sha256("research_input_digest", self.research_input_digest)
        if not self.source_records:
            raise CandidateIntakeError("source_records must not be empty")
        _unique_digest_refs(self.source_records, "source_records")
        if self.source_records != tuple(
            sorted(self.source_records, key=lambda item: item.record_id)
        ):
            raise CandidateIntakeError("source_records must be canonically sorted")
        if not isinstance(self.hypothesis, DigestReference):
            raise CandidateIntakeError("hypothesis must be a DigestReference")
        if not _ID.fullmatch(_trimmed("family_id", self.family_id)):
            raise CandidateIntakeError("invalid family_id")
        if not isinstance(self.comparison, ClosedFamilyComparison):
            raise CandidateIntakeError("comparison is invalid")
        optional_refs = (
            (self.closed_family_catalog, ReferencePurpose.CLOSED_FAMILY_CATALOG),
            (self.family_assessment, ReferencePurpose.FAMILY_ASSESSMENT),
        )
        for ref, purpose in optional_refs:
            if ref is not None and (
                not isinstance(ref, WorkspaceFileReference) or ref.purpose is not purpose
            ):
                raise CandidateIntakeError(f"invalid {purpose.value} reference")
        if not self.dataset_packages:
            raise CandidateIntakeError("dataset_packages must not be empty")
        if any(ref.purpose is not ReferencePurpose.DATA_PACKAGE for ref in self.dataset_packages):
            raise CandidateIntakeError("dataset_packages must use DATA_PACKAGE purpose")
        _unique_file_refs(self.dataset_packages, "dataset_packages")
        if self.dataset_packages != tuple(sorted(self.dataset_packages, key=lambda item: item.ref)):
            raise CandidateIntakeError("dataset_packages must be canonically sorted")
        _sha256("canonical_spec_sha256", self.canonical_spec_sha256)
        if not isinstance(self.lawful_evidence_class, LawfulEvidenceClass):
            raise CandidateIntakeError("lawful_evidence_class is invalid")
        if self.lawful_evidence_class is LawfulEvidenceClass.NONE:
            if self.lawful_evidence is not None:
                raise CandidateIntakeError("NONE lawful evidence cannot bind a file")
        elif (
            not isinstance(self.lawful_evidence, WorkspaceFileReference)
            or self.lawful_evidence.purpose is not ReferencePurpose.LAWFUL_EVIDENCE
        ):
            raise CandidateIntakeError("lawful evidence requires a LAWFUL_EVIDENCE file")
        if self.execution_authority != "NONE":
            raise CandidateIntakeError("execution_authority must be NONE")
        if self.research_input_digest != _digest(self.research_input_payload()):
            raise CandidateIntakeError("research_input_digest mismatch")
        if self.dossier_id != f"RC-{_digest(self.identity_payload())[:32]}":
            raise CandidateIntakeError("dossier_id mismatch")
        if self.dossier_digest != _digest(self.content_payload()):
            raise CandidateIntakeError("dossier_digest mismatch")

    @classmethod
    def create(
        cls,
        *,
        source_records: tuple[DigestReference, ...],
        hypothesis: DigestReference,
        family_id: str,
        comparison: ClosedFamilyComparison,
        dataset_packages: tuple[WorkspaceFileReference, ...],
        canonical_spec_sha256: str,
        closed_family_catalog: WorkspaceFileReference | None = None,
        family_assessment: WorkspaceFileReference | None = None,
        lawful_evidence_class: LawfulEvidenceClass = LawfulEvidenceClass.NONE,
        lawful_evidence: WorkspaceFileReference | None = None,
    ) -> Self:
        sources = tuple(sorted(source_records, key=lambda item: item.record_id))
        packages = tuple(sorted(dataset_packages, key=lambda item: item.ref))
        research = _research_input_payload(
            sources,
            hypothesis,
            family_id,
            comparison,
            packages,
            canonical_spec_sha256,
            lawful_evidence_class,
            lawful_evidence,
        )
        research_digest = _digest(research)
        identity = {
            **research,
            "research_input_digest": research_digest,
            "closed_family_catalog": closed_family_catalog.to_dict()
            if closed_family_catalog
            else None,
            "family_assessment": family_assessment.to_dict() if family_assessment else None,
        }
        dossier_id = f"RC-{_digest(identity)[:32]}"
        content = {**identity, "dossier_id": dossier_id, "execution_authority": "NONE"}
        return cls(
            dossier_id,
            _digest(content),
            research_digest,
            sources,
            hypothesis,
            family_id,
            comparison,
            closed_family_catalog,
            family_assessment,
            packages,
            canonical_spec_sha256,
            lawful_evidence_class,
            lawful_evidence,
        )

    def research_input_payload(self) -> dict[str, object]:
        return _research_input_payload(
            self.source_records,
            self.hypothesis,
            self.family_id,
            self.comparison,
            self.dataset_packages,
            self.canonical_spec_sha256,
            self.lawful_evidence_class,
            self.lawful_evidence,
        )

    def identity_payload(self) -> dict[str, object]:
        return {
            **self.research_input_payload(),
            "research_input_digest": self.research_input_digest,
            "closed_family_catalog": self.closed_family_catalog.to_dict()
            if self.closed_family_catalog
            else None,
            "family_assessment": self.family_assessment.to_dict()
            if self.family_assessment
            else None,
        }

    def content_payload(self) -> dict[str, object]:
        return {
            **self.identity_payload(),
            "dossier_id": self.dossier_id,
            "execution_authority": "NONE",
        }

    def to_dict(self) -> dict[str, object]:
        return {"dossier_digest": self.dossier_digest, **self.content_payload()}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        if _OUTCOME_FIELDS.intersection(str(key).casefold() for key in raw):
            raise CandidateIntakeError("outcome fields are prohibited")
        fields = {
            "dossier_id",
            "dossier_digest",
            "research_input_digest",
            "source_records",
            "hypothesis",
            "family_id",
            "comparison",
            "closed_family_catalog",
            "family_assessment",
            "dataset_packages",
            "canonical_spec_sha256",
            "lawful_evidence_class",
            "lawful_evidence",
            "execution_authority",
        }
        _exact(raw, fields, "candidate dossier")
        return cls(
            _trimmed("dossier_id", raw["dossier_id"]),
            _sha256("dossier_digest", raw["dossier_digest"]),
            _sha256("research_input_digest", raw["research_input_digest"]),
            tuple(
                DigestReference.from_mapping(item)
                for item in _mapping_list(raw["source_records"], "source_records")
            ),
            DigestReference.from_mapping(_required_mapping(raw["hypothesis"], "hypothesis")),
            _trimmed("family_id", raw["family_id"]),
            ClosedFamilyComparison.from_mapping(_required_mapping(raw["comparison"], "comparison")),
            _optional_file(raw["closed_family_catalog"], "closed_family_catalog"),
            _optional_file(raw["family_assessment"], "family_assessment"),
            tuple(
                WorkspaceFileReference.from_mapping(item)
                for item in _mapping_list(raw["dataset_packages"], "dataset_packages")
            ),
            _sha256("canonical_spec_sha256", raw["canonical_spec_sha256"]),
            LawfulEvidenceClass(
                _enum(LawfulEvidenceClass, raw["lawful_evidence_class"], "lawful_evidence_class")
            ),
            _optional_file(raw["lawful_evidence"], "lawful_evidence"),
            _trimmed("execution_authority", raw["execution_authority"]),
        )


def _research_input_payload(
    sources: tuple[DigestReference, ...],
    hypothesis: DigestReference,
    family_id: str,
    comparison: ClosedFamilyComparison,
    packages: tuple[WorkspaceFileReference, ...],
    spec_sha: str,
    lawful_class: LawfulEvidenceClass,
    lawful_evidence: WorkspaceFileReference | None,
) -> dict[str, object]:
    return {
        "source_records": [item.to_dict() for item in sources],
        "hypothesis": hypothesis.to_dict(),
        "family_id": family_id,
        "comparison": comparison.to_dict(),
        "dataset_packages": [item.to_dict() for item in packages],
        "canonical_spec_sha256": spec_sha,
        "lawful_evidence_class": lawful_class.value,
        "lawful_evidence": lawful_evidence.to_dict() if lawful_evidence else None,
    }


@dataclass(frozen=True, slots=True)
class IntakeEntry:
    sequence: int
    previous_hash: str | None
    entry_hash: str
    dossier: CandidateDossier
    verdict: IntakeVerdict
    pending_reviews: tuple[ReviewDomain, ...]
    reasons: tuple[str, ...]
    execution_authority: str = "NONE"

    def payload_without_hash(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "sequence": self.sequence,
            "previous_hash": self.previous_hash,
            "dossier": self.dossier.to_dict(),
            "verdict": self.verdict.value,
            "pending_reviews": [item.value for item in self.pending_reviews],
            "reasons": list(self.reasons),
            "execution_authority": self.execution_authority,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self.payload_without_hash(), "entry_hash": self.entry_hash}

    @classmethod
    def build(cls, sequence: int, previous_hash: str | None, dossier: CandidateDossier) -> Self:
        verdict, pending, reasons = _policy(dossier)
        provisional = cls(
            sequence,
            previous_hash,
            "LE-" + "0" * 64,
            dossier,
            verdict,
            pending,
            reasons,
        )
        return cls(
            sequence,
            previous_hash,
            f"LE-{_digest(provisional.payload_without_hash())}",
            dossier,
            verdict,
            pending,
            reasons,
        )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> Self:
        fields = {
            "schema_version",
            "sequence",
            "previous_hash",
            "entry_hash",
            "dossier",
            "verdict",
            "pending_reviews",
            "reasons",
            "execution_authority",
        }
        _exact(raw, fields, "intake entry")
        _schema(raw["schema_version"])
        sequence = raw["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            raise CandidateIntakeError("sequence must be a positive integer")
        previous = raw["previous_hash"]
        if previous is not None and (
            not isinstance(previous, str) or not _ENTRY_HASH.fullmatch(previous)
        ):
            raise CandidateIntakeError("invalid previous_hash")
        pending_raw = raw["pending_reviews"]
        reasons_raw = raw["reasons"]
        if not isinstance(pending_raw, list) or not isinstance(reasons_raw, list):
            raise CandidateIntakeError("pending_reviews and reasons must be lists")
        entry = cls(
            sequence,
            previous,
            _trimmed("entry_hash", raw["entry_hash"]),
            CandidateDossier.from_mapping(_required_mapping(raw["dossier"], "dossier")),
            IntakeVerdict(_enum(IntakeVerdict, raw["verdict"], "verdict")),
            tuple(
                ReviewDomain(_enum(ReviewDomain, item, "pending_reviews")) for item in pending_raw
            ),
            tuple(_trimmed("reasons", item) for item in reasons_raw),
            _trimmed("execution_authority", raw["execution_authority"]),
        )
        expected = IntakeEntry.build(entry.sequence, entry.previous_hash, entry.dossier)
        if entry.execution_authority != "NONE":
            raise CandidateIntakeError("entry execution_authority must be NONE")
        if (
            entry.verdict != expected.verdict
            or entry.pending_reviews != expected.pending_reviews
            or entry.reasons != expected.reasons
        ):
            raise CandidateIntakeError("stored intake decision violates current policy")
        if (
            not _ENTRY_HASH.fullmatch(entry.entry_hash)
            or entry.entry_hash != f"LE-{_digest(entry.payload_without_hash())}"
        ):
            raise CandidateIntakeError("entry_hash mismatch")
        return entry


def _policy(
    dossier: CandidateDossier,
) -> tuple[IntakeVerdict, tuple[ReviewDomain, ...], tuple[str, ...]]:
    reasons: list[str] = []
    if dossier.comparison.rescue_requested:
        reasons.append("RESCUE_REQUEST_PROHIBITED")
    if dossier.comparison.version_reset_requested:
        reasons.append("VERSION_RESET_PROHIBITED")
    if (
        dossier.comparison.matches_closed_family
        and dossier.lawful_evidence_class is LawfulEvidenceClass.NONE
    ):
        reasons.append("CLOSED_FAMILY_REUSE_WITHOUT_NEW_EXOGENOUS_EVIDENCE")
    if reasons:
        return IntakeVerdict.REJECT, (), tuple(reasons)
    pending = {ReviewDomain.DATA, ReviewDomain.OPERATOR}
    if dossier.lawful_evidence_class is LawfulEvidenceClass.LICENSED_AUTHORITATIVE_SOURCE:
        pending.add(ReviewDomain.ACCESS)
    review_reasons = (
        "DATA_AND_LAWFUL_FILES_ARE_UNTRUSTED_METADATA_PENDING_REVIEW",
        "INDEPENDENT_TYPED_DECISION_UNAVAILABLE_UNTIL_PHASE_2B",
        "SOURCE_AND_HYPOTHESIS_REGISTRY_RESOLUTION_PENDING",
    )
    return (
        IntakeVerdict.REVIEW_REQUIRED,
        tuple(sorted(pending, key=lambda item: item.value)),
        review_reasons,
    )


@dataclass(frozen=True, slots=True)
class CandidateStatus:
    dossier: CandidateDossier
    verdict: IntakeVerdict
    lifecycle: CandidateLifecycle
    pending_reviews: tuple[ReviewDomain, ...]
    entry_hash: str


class CandidateIntakeLedger:
    """Descriptor-confined fixed-path candidate intake ledger."""

    def __init__(self, workspace_root: Path) -> None:
        supplied = workspace_root.absolute()
        _reject_symlink_components(supplied)
        self.root = supplied.resolve(strict=True)
        lowered = tuple(part.casefold() for part in self.root.parts)
        for prohibited in (("artifacts", "sealed"), ("artifacts", "holdout")):
            if any(lowered[index : index + 2] == prohibited for index in range(len(lowered) - 1)):
                raise CandidateIntakeError("workspace root is inside a prohibited artifact subtree")
        for marker in ("PROJECT_STATE.md", "pyproject.toml"):
            marker_fd = _open_regular_read(self.root, (marker,))
            os.close(marker_fd)
        _validate_path_parts(LEDGER_PARTS, "ledger")
        self.path = self.root.joinpath(*LEDGER_PARTS)

    def _open(self, *, create: bool, exclusive: bool) -> tuple[int, int] | None:
        root_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        current_fd = root_fd
        created_parent = False
        keep_parent_open = False
        try:
            for part in LEDGER_PARTS[:-1]:
                try:
                    next_fd = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                except FileNotFoundError:
                    if not create:
                        return None
                    try:
                        os.mkdir(part, 0o700, dir_fd=current_fd)
                    except FileExistsError:
                        pass
                    else:
                        os.fsync(current_fd)
                        created_parent = True
                    next_fd = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=current_fd,
                    )
                directory_info = os.fstat(next_fd)
                if not stat.S_ISDIR(directory_info.st_mode):
                    os.close(next_fd)
                    raise CandidateIntakeError("ledger parent component is not a directory")
                if current_fd != root_fd:
                    os.close(current_fd)
                current_fd = next_fd
            flags = os.O_RDONLY | os.O_NOFOLLOW
            if create:
                flags = os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_CREAT
            ledger_fd: int | None = None
            for _ in range(8):
                try:
                    ledger_fd = os.open(LEDGER_PARTS[-1], flags, 0o600, dir_fd=current_fd)
                    break
                except FileNotFoundError:
                    if not create:
                        return None
            if ledger_fd is None:
                raise CandidateIntakeError("ledger file could not be created after secure retries")
            info = os.fstat(ledger_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                os.close(ledger_fd)
                raise CandidateIntakeError("ledger must be a regular file with one hard link")
            fcntl.flock(ledger_fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            if create and (created_parent or info.st_size == 0):
                os.fsync(current_fd)
            keep_parent_open = True
            return ledger_fd, current_fd
        except OSError as exc:
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                raise CandidateIntakeError(
                    "ledger path contains a symlink or non-directory"
                ) from exc
            raise
        finally:
            if not keep_parent_open and current_fd != root_fd:
                os.close(current_fd)
            os.close(root_fd)

    @staticmethod
    def _close(opened: tuple[int, int]) -> None:
        ledger_fd, parent_fd = opened
        fcntl.flock(ledger_fd, fcntl.LOCK_UN)
        os.close(ledger_fd)
        os.close(parent_fd)

    def _parse(self, ledger_fd: int) -> tuple[IntakeEntry, ...]:
        os.lseek(ledger_fd, 0, os.SEEK_SET)
        payload = _read_fd(ledger_fd)
        entries: list[IntakeEntry] = []
        previous: str | None = None
        dossier_ids: set[str] = set()
        for line_number, line in enumerate(payload.splitlines(), 1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise CandidateIntakeError(f"corrupt ledger JSON at line {line_number}") from exc
            if not isinstance(raw, dict):
                raise CandidateIntakeError(f"ledger line {line_number} must be a mapping")
            entry = IntakeEntry.from_mapping(raw)
            if entry.sequence != len(entries) + 1 or entry.previous_hash != previous:
                raise CandidateIntakeError("ledger sequence/predecessor mismatch")
            if entry.dossier.dossier_id in dossier_ids:
                raise CandidateIntakeError("duplicate physical dossier registration")
            self._verify_dossier(entry.dossier)
            entries.append(entry)
            dossier_ids.add(entry.dossier.dossier_id)
            previous = entry.entry_hash
        return tuple(entries)

    def register(self, dossier: CandidateDossier) -> CandidateStatus:
        self._verify_dossier(dossier)
        opened = self._open(create=True, exclusive=True)
        assert opened is not None
        ledger_fd, _ = opened
        try:
            entries = self._parse(ledger_fd)
            for entry in entries:
                if entry.dossier.dossier_id == dossier.dossier_id:
                    if entry.dossier.dossier_digest != dossier.dossier_digest:
                        raise CandidateIntakeError("conflicting dossier identity")
                    return _status(entry)
            self._verify_dossier(dossier)
            previous = entries[-1].entry_hash if entries else None
            entry = IntakeEntry.build(len(entries) + 1, previous, dossier)
            _write_fd(ledger_fd, _canonical(entry.to_dict()) + b"\n")
            os.fsync(ledger_fd)
            return _status(entry)
        finally:
            self._close(opened)

    def list_statuses(self) -> tuple[CandidateStatus, ...]:
        opened = self._open(create=False, exclusive=False)
        if opened is None:
            return ()
        try:
            return tuple(_status(entry) for entry in self._parse(opened[0]))
        finally:
            self._close(opened)

    def _verify_dossier(self, dossier: CandidateDossier) -> None:
        for package in dossier.dataset_packages:
            package.read_verified(self.root, ReferencePurpose.DATA_PACKAGE)
        if dossier.lawful_evidence is not None:
            dossier.lawful_evidence.read_verified(self.root, ReferencePurpose.LAWFUL_EVIDENCE)
        if dossier.closed_family_catalog is not None:
            catalog = _json_metadata(
                dossier.closed_family_catalog.read_verified(
                    self.root, ReferencePurpose.CLOSED_FAMILY_CATALOG
                ),
                "closed-family catalog",
            )
            _validate_catalog(catalog, dossier)
        if dossier.family_assessment is not None:
            assessment = _json_metadata(
                dossier.family_assessment.read_verified(
                    self.root, ReferencePurpose.FAMILY_ASSESSMENT
                ),
                "family assessment",
            )
            _validate_assessment(assessment, dossier)


def _status(entry: IntakeEntry) -> CandidateStatus:
    lifecycle = (
        CandidateLifecycle.REJECTED
        if entry.verdict is IntakeVerdict.REJECT
        else CandidateLifecycle.REVIEW_REQUIRED
    )
    return CandidateStatus(
        entry.dossier,
        entry.verdict,
        lifecycle,
        entry.pending_reviews,
        entry.entry_hash,
    )


def _json_metadata(payload: bytes, label: str) -> Mapping[str, object]:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateIntakeError(f"{label} must be strict JSON") from exc
    if not isinstance(raw, dict) or not raw:
        raise CandidateIntakeError(f"{label} must be a non-empty JSON mapping")
    if _OUTCOME_FIELDS.intersection(str(key).casefold() for key in raw):
        raise CandidateIntakeError(f"{label} contains prohibited outcome fields")
    return raw


def _validate_catalog(raw: Mapping[str, object], dossier: CandidateDossier) -> None:
    fields = {"schema_version", "kind", "catalog_id", "closed_family_ids", "execution_authority"}
    _exact(raw, fields, "closed-family catalog")
    _schema(raw["schema_version"])
    if raw["kind"] != "CLOSED_FAMILY_CATALOG" or raw["execution_authority"] != "NONE":
        raise CandidateIntakeError("invalid closed-family catalog kind/authority")
    if not _ID.fullmatch(_trimmed("catalog_id", raw["catalog_id"])):
        raise CandidateIntakeError("invalid catalog_id")
    families = raw["closed_family_ids"]
    if not isinstance(families, list) or any(not isinstance(item, str) for item in families):
        raise CandidateIntakeError("closed_family_ids must be a list of strings")
    canonical = tuple(sorted(families))
    if tuple(families) != canonical or len(canonical) != len(set(canonical)):
        raise CandidateIntakeError("closed_family_ids must be unique and sorted")
    for family_id in canonical:
        if not _ID.fullmatch(_trimmed("closed_family_ids", family_id)):
            raise CandidateIntakeError(f"invalid closed family identifier: {family_id}")
    if any(family not in canonical for family in dossier.comparison.nearest_family_ids):
        raise CandidateIntakeError("nearest family is absent from bound catalog")


def _validate_assessment(raw: Mapping[str, object], dossier: CandidateDossier) -> None:
    fields = {
        "schema_version",
        "kind",
        "assessment_id",
        "family_id",
        "canonical_spec_sha256",
        "research_input_digest",
        "catalog_sha256",
        "nearest_family_ids",
        "matches_closed_family",
        "execution_authority",
    }
    _exact(raw, fields, "family assessment")
    _schema(raw["schema_version"])
    if raw["kind"] != "FAMILY_ASSESSMENT" or raw["execution_authority"] != "NONE":
        raise CandidateIntakeError("invalid family assessment kind/authority")
    if not _ID.fullmatch(_trimmed("assessment_id", raw["assessment_id"])):
        raise CandidateIntakeError("invalid assessment_id")
    if not isinstance(raw["matches_closed_family"], bool):
        raise CandidateIntakeError("family assessment matches_closed_family must be a boolean")
    expected_catalog = (
        dossier.closed_family_catalog.sha256 if dossier.closed_family_catalog else None
    )
    expected = {
        "family_id": dossier.family_id,
        "canonical_spec_sha256": dossier.canonical_spec_sha256,
        "research_input_digest": dossier.research_input_digest,
        "catalog_sha256": expected_catalog,
        "nearest_family_ids": list(dossier.comparison.nearest_family_ids),
        "matches_closed_family": dossier.comparison.matches_closed_family,
    }
    for field, value in expected.items():
        if raw[field] != value:
            raise CandidateIntakeError(f"family assessment {field} does not bind dossier")


def _mapping_list(value: object, field: str) -> list[Mapping[str, object]]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise CandidateIntakeError(f"{field} must be a list of mappings")
    return value


def _required_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not value:
        raise CandidateIntakeError(f"{field} must be a non-empty mapping")
    return value


def _optional_file(value: object, field: str) -> WorkspaceFileReference | None:
    if value is None:
        return None
    return WorkspaceFileReference.from_mapping(_required_mapping(value, field))
