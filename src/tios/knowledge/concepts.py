"""Validated dictionary concepts with a small SQLite FTS query surface."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

_CONCEPT_ID = re.compile(r"CON-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")


class ConceptError(ValueError):
    """Raised when concept data violates the dictionary contract."""


class ConceptFreshness(StrEnum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"


class ConceptEvidenceStatus(StrEnum):
    LOCAL_CONTRACT = "LOCAL_CONTRACT"
    FIBO_PROVENANCE = "FIBO_PROVENANCE"
    GAP = "GAP"


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ConceptError(f"{field} must be a non-empty trimmed string")
    return value


def _strings(value: object, field: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ConceptError(f"{field} must be a list of strings")
    result = tuple(_nonempty(item, field) for item in value)
    if nonempty and not result:
        raise ConceptError(f"{field} must not be empty")
    return result


@dataclass(frozen=True)
class ConceptRecord:
    concept_id: str
    canonical_name: str
    abbreviations: tuple[str, ...]
    aliases: tuple[str, ...]
    definition: str
    category: str
    market_contexts: tuple[str, ...]
    venue_variants: tuple[str, ...]
    related: tuple[str, ...]
    sources: tuple[str, ...]
    fibo_uri: str | None
    examples: tuple[str, ...]
    evidence_status: ConceptEvidenceStatus
    freshness: ConceptFreshness

    def __post_init__(self) -> None:
        for field in ("concept_id", "canonical_name", "definition", "category"):
            _nonempty(getattr(self, field), field)
        if not _CONCEPT_ID.fullmatch(self.concept_id):
            raise ConceptError(f"invalid concept_id: {self.concept_id}")
        for field in (
            "abbreviations",
            "aliases",
            "market_contexts",
            "venue_variants",
            "related",
            "sources",
            "examples",
        ):
            if not isinstance(getattr(self, field), tuple):
                raise ConceptError(f"{field} must be a tuple")
            for item in getattr(self, field):
                _nonempty(item, field)
        if not self.sources:
            raise ConceptError("concepts require at least one source")
        for related_id in self.related:
            if not _CONCEPT_ID.fullmatch(related_id):
                raise ConceptError(f"invalid related concept: {related_id}")
        if self.fibo_uri is not None and not self.fibo_uri.startswith(
            "https://spec.edmcouncil.org/fibo/"
        ):
            raise ConceptError("fibo_uri must be an EDM Council FIBO HTTPS URI")
        if self.evidence_status is ConceptEvidenceStatus.FIBO_PROVENANCE and not self.fibo_uri:
            raise ConceptError("FIBO_PROVENANCE concepts require fibo_uri")
        if not isinstance(self.evidence_status, ConceptEvidenceStatus):
            raise ConceptError("evidence_status must be a ConceptEvidenceStatus")
        if not isinstance(self.freshness, ConceptFreshness):
            raise ConceptError("freshness must be a ConceptFreshness")
        text = " ".join((self.definition, *self.examples))
        if re.search(r"\b(?:fast|slow|window|period|threshold|fee|slippage)\s*=", text):
            raise ConceptError("concepts cannot store strategy parameter values")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ConceptRecord:
        expected = set(cls.__dataclass_fields__)
        missing, extra = expected - raw.keys(), raw.keys() - expected
        if missing or extra:
            raise ConceptError(
                f"concept fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        fibo_uri = raw["fibo_uri"]
        if fibo_uri is not None and not isinstance(fibo_uri, str):
            raise ConceptError("fibo_uri must be a string or null")
        return cls(
            concept_id=_nonempty(raw["concept_id"], "concept_id"),
            canonical_name=_nonempty(raw["canonical_name"], "canonical_name"),
            abbreviations=_strings(raw["abbreviations"], "abbreviations"),
            aliases=_strings(raw["aliases"], "aliases"),
            definition=_nonempty(raw["definition"], "definition"),
            category=_nonempty(raw["category"], "category"),
            market_contexts=_strings(raw["market_contexts"], "market_contexts"),
            venue_variants=_strings(raw["venue_variants"], "venue_variants"),
            related=_strings(raw["related"], "related"),
            sources=_strings(raw["sources"], "sources", nonempty=True),
            fibo_uri=fibo_uri,
            examples=_strings(raw["examples"], "examples"),
            evidence_status=ConceptEvidenceStatus(
                _nonempty(raw["evidence_status"], "evidence_status")
            ),
            freshness=ConceptFreshness(_nonempty(raw["freshness"], "freshness")),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ConceptRegistry:
    def __init__(self, records: Iterable[ConceptRecord]) -> None:
        ordered = tuple(sorted(records, key=lambda record: record.concept_id))
        ids = [record.concept_id for record in ordered]
        if len(ids) != len(set(ids)):
            raise ConceptError("duplicate concept_id")
        self._records = ordered
        self._by_id = {record.concept_id: record for record in ordered}
        self._gaps: tuple[str, ...] = ()
        for record in ordered:
            for related_id in record.related:
                if related_id == record.concept_id:
                    raise ConceptError(f"{record.concept_id} cannot reference itself")
                if related_id not in self._by_id:
                    raise ConceptError(
                        f"{record.concept_id} references unknown concept: {related_id}"
                    )
        self._connection = sqlite3.connect(":memory:")
        self._build_fts()

    @classmethod
    def load(cls, path: Path) -> ConceptRegistry:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"registry_version", "concepts", "gaps"}:
            raise ConceptError("registry must contain registry_version, concepts, and gaps")
        if raw["registry_version"] != 1 or not isinstance(raw["concepts"], list):
            raise ConceptError("registry_version must be 1 and concepts must be a list")
        if not isinstance(raw["gaps"], list):
            raise ConceptError("gaps must be a list")
        records = []
        for concept in raw["concepts"]:
            if not isinstance(concept, dict):
                raise ConceptError("each concept must be a mapping")
            records.append(ConceptRecord.from_mapping(concept))
        registry = cls(records)
        registry._gaps = tuple(_nonempty(gap, "gaps") for gap in raw["gaps"])
        return registry

    def _build_fts(self) -> None:
        self._connection.execute(
            "CREATE VIRTUAL TABLE concepts_fts USING fts5("
            "concept_id UNINDEXED, canonical_name, aliases, definition, category, contexts)"
        )
        self._connection.executemany(
            "INSERT INTO concepts_fts VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    record.concept_id,
                    record.canonical_name,
                    " ".join((*record.abbreviations, *record.aliases)),
                    record.definition,
                    record.category,
                    " ".join((*record.market_contexts, *record.venue_variants)),
                )
                for record in self._records
            ],
        )

    def list(self) -> tuple[ConceptRecord, ...]:
        return self._records

    def get(self, concept_id: str) -> ConceptRecord:
        try:
            return self._by_id[concept_id]
        except KeyError as exc:
            raise ConceptError(f"unknown concept: {concept_id}") from exc

    def gaps(self) -> tuple[str, ...]:
        return getattr(self, "_gaps", ())

    def search(self, query: str) -> tuple[ConceptRecord, ...]:
        _nonempty(query, "query")
        rows = self._connection.execute(
            "SELECT concept_id FROM concepts_fts WHERE concepts_fts MATCH ? ORDER BY rank",
            (query,),
        ).fetchall()
        return tuple(self.get(row[0]) for row in rows)
