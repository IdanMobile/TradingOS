"""Validated, deterministic registry of primary strategy-research sources."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

_SOURCE_ID = re.compile(r"SRC-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")
_DOI = re.compile(r"10\.\d{4,9}/\S+\Z", re.IGNORECASE)


class ResearchSourceError(ValueError):
    """Raised when source data violates the primary-source contract."""


class SourceClass(StrEnum):
    PRIMARY_ACADEMIC_PAPER = "primary_academic_paper"
    EXCHANGE_BOT_MARKETPLACE = "exchange_bot_marketplace"
    COPY_TRADING_LEADERBOARD = "copy_trading_leaderboard"
    ONLINE_SIGNAL_FEED = "online_signal_feed"
    THIRD_PARTY_BOT_PLATFORM = "third_party_bot_platform"


class AccessLicenseStatus(StrEnum):
    PUBLISHER_PAGE_ONLY = "publisher_page_only"
    LAWFUL_FULL_TEXT_LINKED = "lawful_full_text_linked"
    PUBLIC_PAGE_ONLY = "public_page_only"
    PLATFORM_TERMS_REQUIRED = "platform_terms_required"


class HypothesisFamily(StrEnum):
    CROSS_SECTIONAL_MOMENTUM = "cross_sectional_momentum"
    TIME_SERIES_MOMENTUM = "time_series_momentum"
    REVERSAL = "reversal"
    VOLATILITY_SCALING = "volatility_scaling"
    TRANSACTION_COSTS = "transaction_costs"
    MULTIPLE_TESTING_CONTROLS = "multiple_testing_controls"
    EXCHANGE_BOT_REPLAY = "exchange_bot_replay"
    COPY_TRADING_REPLAY = "copy_trading_replay"
    SIGNAL_REPLAY = "signal_replay"
    BOT_PLATFORM_REPLAY = "bot_platform_replay"


class ExactSpanStatus(StrEnum):
    NOT_CAPTURED = "not_captured"
    CAPTURED = "captured"


class EvidenceStrength(StrEnum):
    HYPOTHESIS_ONLY = "hypothesis_only"


def _nonempty(name: str, value: object) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ResearchSourceError(f"{name} must be non-empty and trimmed")


def _https_url(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise ResearchSourceError(f"{name} must be an absolute HTTPS URL")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise ResearchSourceError(f"{name} must be an absolute HTTPS URL")


def _enum(enum_type: type[StrEnum], value: object, field: str) -> StrEnum:
    if not isinstance(value, str):
        raise ResearchSourceError(f"{field} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ResearchSourceError(f"invalid {field}: {value}") from exc


def _strings(value: object, field: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ResearchSourceError(f"{field} must be a list of strings")
    result = tuple(value)
    if nonempty and not result:
        raise ResearchSourceError(f"{field} must not be empty")
    for item in result:
        _nonempty(field, item)
    return result


@dataclass(frozen=True)
class ResearchSourceRecord:
    """Bibliographic source metadata; never evidence that a strategy is profitable."""

    source_id: str
    source_class: SourceClass
    title: str
    authors: tuple[str, ...]
    publication: str
    year: int
    volume: str
    issue: str
    pages: str
    doi: str | None
    canonical_publisher_url: str
    lawful_full_text_url: str | None
    checked_at: str
    access_license_status: AccessLicenseStatus
    hypothesis_families: tuple[HypothesisFamily, ...]
    claim_summary: str
    exact_span_status: ExactSpanStatus
    evidence_strength: EvidenceStrength
    profit_claims_inherited: bool
    locally_reproduced: bool
    approval_eligible: bool
    contradictions: tuple[str, ...]
    reverify_trigger: str
    supersedes: tuple[str, ...]
    related_source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        enum_fields = {
            "source_class": SourceClass,
            "access_license_status": AccessLicenseStatus,
            "exact_span_status": ExactSpanStatus,
            "evidence_strength": EvidenceStrength,
        }
        for field, enum_type in enum_fields.items():
            if not isinstance(getattr(self, field), enum_type):
                raise ResearchSourceError(f"{field} must be a {enum_type.__name__}")
        for name in ("source_id", "title", "publication", "volume", "issue", "pages"):
            _nonempty(name, getattr(self, name))
        if not _SOURCE_ID.fullmatch(self.source_id):
            raise ResearchSourceError(f"invalid source_id: {self.source_id}")
        if (
            not isinstance(self.year, int)
            or isinstance(self.year, bool)
            or not 1800 <= self.year <= 2100
        ):
            raise ResearchSourceError("year must be an integer from 1800 through 2100")
        if not isinstance(self.authors, tuple) or not self.authors:
            raise ResearchSourceError("authors must not be empty")
        for author in self.authors:
            _nonempty("authors", author)
        if not isinstance(self.hypothesis_families, tuple) or not self.hypothesis_families:
            raise ResearchSourceError("hypothesis_families must not be empty")
        if any(not isinstance(family, HypothesisFamily) for family in self.hypothesis_families):
            raise ResearchSourceError("hypothesis_families contains an invalid family")
        if self.source_class is SourceClass.PRIMARY_ACADEMIC_PAPER:
            if not isinstance(self.doi, str) or not _DOI.fullmatch(self.doi):
                raise ResearchSourceError(f"invalid DOI: {self.doi}")
        elif self.doi is not None and (
            not isinstance(self.doi, str) or not _DOI.fullmatch(self.doi)
        ):
            raise ResearchSourceError(f"invalid DOI: {self.doi}")
        _https_url("canonical_publisher_url", self.canonical_publisher_url)
        if self.lawful_full_text_url is not None:
            _https_url("lawful_full_text_url", self.lawful_full_text_url)
            if self.access_license_status is not AccessLicenseStatus.LAWFUL_FULL_TEXT_LINKED:
                raise ResearchSourceError("a lawful full-text URL requires lawful_full_text_linked")
        elif self.access_license_status is AccessLicenseStatus.LAWFUL_FULL_TEXT_LINKED:
            raise ResearchSourceError("lawful_full_text_linked requires a lawful full-text URL")
        if not isinstance(self.checked_at, str):
            raise ResearchSourceError("checked_at must be an ISO 8601 UTC timestamp")
        try:
            checked = datetime.fromisoformat(self.checked_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ResearchSourceError("checked_at must be an ISO 8601 UTC timestamp") from exc
        if not self.checked_at.endswith("Z") or checked.tzinfo != UTC:
            raise ResearchSourceError("checked_at must be an ISO 8601 UTC timestamp ending in Z")
        _nonempty("claim_summary", self.claim_summary)
        _nonempty("reverify_trigger", self.reverify_trigger)
        for field in ("contradictions", "supersedes", "related_source_ids"):
            if not isinstance(getattr(self, field), tuple):
                raise ResearchSourceError(f"{field} must be a tuple")
            for value in getattr(self, field):
                _nonempty(field, value)
        for related_id in (*self.supersedes, *self.related_source_ids):
            if not _SOURCE_ID.fullmatch(related_id):
                raise ResearchSourceError(f"invalid related source identifier: {related_id}")
        bool_fields = ("profit_claims_inherited", "locally_reproduced", "approval_eligible")
        if any(not isinstance(getattr(self, field), bool) for field in bool_fields):
            raise ResearchSourceError(f"{', '.join(bool_fields)} must be booleans")
        if self.profit_claims_inherited:
            raise ResearchSourceError("research sources cannot provide inherited profit proof")
        if self.locally_reproduced:
            raise ResearchSourceError("initial sources cannot claim local reproduction")
        if self.approval_eligible:
            raise ResearchSourceError("initial sources cannot be approval eligible")
        if self.evidence_strength is not EvidenceStrength.HYPOTHESIS_ONLY:
            raise ResearchSourceError("initial sources must remain hypothesis-only")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ResearchSourceRecord:
        expected = set(cls.__dataclass_fields__)
        missing, extra = expected - raw.keys(), raw.keys() - expected
        if missing or extra:
            raise ResearchSourceError(
                f"source fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )

        def string(field: str) -> str:
            value = raw[field]
            if not isinstance(value, str):
                raise ResearchSourceError(f"{field} must be a string")
            return value

        def boolean(field: str) -> bool:
            value = raw[field]
            if not isinstance(value, bool):
                raise ResearchSourceError(f"{field} must be a boolean")
            return value

        full_text = raw["lawful_full_text_url"]
        if full_text is not None and not isinstance(full_text, str):
            raise ResearchSourceError("lawful_full_text_url must be a string or null")
        year = raw["year"]
        if not isinstance(year, int):
            raise ResearchSourceError("year must be an integer")
        families_raw = raw["hypothesis_families"]
        if not isinstance(families_raw, list):
            raise ResearchSourceError("hypothesis_families must be a list")
        families = tuple(
            _enum(HypothesisFamily, value, "hypothesis_families") for value in families_raw
        )
        return cls(
            source_id=string("source_id"),
            source_class=SourceClass(_enum(SourceClass, raw["source_class"], "source_class")),
            title=string("title"),
            authors=_strings(raw["authors"], "authors", nonempty=True),
            publication=string("publication"),
            year=year,
            volume=string("volume"),
            issue=string("issue"),
            pages=string("pages"),
            doi=string("doi") if raw["doi"] is not None else None,
            canonical_publisher_url=string("canonical_publisher_url"),
            lawful_full_text_url=full_text,
            checked_at=string("checked_at"),
            access_license_status=AccessLicenseStatus(
                _enum(AccessLicenseStatus, raw["access_license_status"], "access_license_status")
            ),
            hypothesis_families=tuple(HypothesisFamily(item) for item in families),
            claim_summary=string("claim_summary"),
            exact_span_status=ExactSpanStatus(
                _enum(ExactSpanStatus, raw["exact_span_status"], "exact_span_status")
            ),
            evidence_strength=EvidenceStrength(
                _enum(EvidenceStrength, raw["evidence_strength"], "evidence_strength")
            ),
            profit_claims_inherited=boolean("profit_claims_inherited"),
            locally_reproduced=boolean("locally_reproduced"),
            approval_eligible=boolean("approval_eligible"),
            contradictions=_strings(raw["contradictions"], "contradictions"),
            reverify_trigger=string("reverify_trigger"),
            supersedes=_strings(raw["supersedes"], "supersedes"),
            related_source_ids=_strings(raw["related_source_ids"], "related_source_ids"),
        )


class ResearchSourceRegistry:
    """Immutable in-memory index loaded from the application-owned YAML file."""

    def __init__(self, records: Iterable[ResearchSourceRecord]) -> None:
        ordered = tuple(sorted(records, key=lambda record: record.source_id))
        ids = [record.source_id for record in ordered]
        dois = [record.doi.casefold() for record in ordered if record.doi is not None]
        if len(ids) != len(set(ids)):
            raise ResearchSourceError("duplicate source_id")
        if len(dois) != len(set(dois)):
            raise ResearchSourceError("duplicate DOI")
        self._records = ordered
        self._by_id = {record.source_id: record for record in ordered}
        for record in ordered:
            for field in ("supersedes", "related_source_ids"):
                refs = getattr(record, field)
                if len(refs) != len(set(refs)):
                    raise ResearchSourceError(f"duplicate {field} reference on {record.source_id}")
                for source_id in refs:
                    if source_id == record.source_id:
                        raise ResearchSourceError(
                            f"{record.source_id} cannot reference itself in {field}"
                        )
                    if source_id not in self._by_id:
                        raise ResearchSourceError(
                            f"{record.source_id} references unknown source in {field}: {source_id}"
                        )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(source_id: str) -> None:
            if source_id in visiting:
                raise ResearchSourceError("cyclic supersession is not allowed")
            if source_id in visited:
                return
            visiting.add(source_id)
            for superseded_id in self._by_id[source_id].supersedes:
                visit(superseded_id)
            visiting.remove(source_id)
            visited.add(source_id)

        for source_id in ids:
            visit(source_id)

    @classmethod
    def load(cls, path: Path) -> ResearchSourceRegistry:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"registry_version", "sources"}:
            raise ResearchSourceError("registry must contain registry_version and sources")
        if raw["registry_version"] != 1 or not isinstance(raw["sources"], list):
            raise ResearchSourceError("registry_version must be 1 and sources must be a list")
        records = []
        for source in raw["sources"]:
            if not isinstance(source, dict):
                raise ResearchSourceError("each source must be a mapping")
            records.append(ResearchSourceRecord.from_mapping(source))
        return cls(records)

    def get(self, source_id: str) -> ResearchSourceRecord:
        try:
            return self._by_id[source_id]
        except KeyError as exc:
            raise ResearchSourceError(f"unknown source: {source_id}") from exc

    def list(self) -> tuple[ResearchSourceRecord, ...]:
        return self._records

    def related(self, source_id: str) -> tuple[ResearchSourceRecord, ...]:
        return tuple(self.get(ref) for ref in self.get(source_id).related_source_ids)

    def supersedes(self, source_id: str) -> tuple[ResearchSourceRecord, ...]:
        return tuple(self.get(ref) for ref in self.get(source_id).supersedes)

    def family(self, family: HypothesisFamily | str) -> tuple[ResearchSourceRecord, ...]:
        try:
            target = HypothesisFamily(family)
        except ValueError as exc:
            raise ResearchSourceError(f"unknown hypothesis family: {family}") from exc
        return tuple(record for record in self._records if target in record.hypothesis_families)

    def digest(self) -> str:
        payload = json.dumps(
            [record.to_dict() for record in self._records],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()
