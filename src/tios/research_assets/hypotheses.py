"""Immutable source-to-executable hypothesis records."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from tios.research_assets.registry import ResearchSourceError, ResearchSourceRegistry

_HYPOTHESIS_ID = re.compile(r"HYP-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")
_STRATEGY_ID = re.compile(r"STRAT-[A-Za-z0-9_-]+\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class HypothesisError(ValueError):
    """Raised when executable-hypothesis lineage is invalid."""


def _string(raw: Mapping[str, object], field: str) -> str:
    value = raw[field]
    if not isinstance(value, str) or not value or value != value.strip():
        raise HypothesisError(f"{field} must be a non-empty trimmed string")
    return value


def _strings(raw: Mapping[str, object], field: str, *, nonempty: bool = False) -> tuple[str, ...]:
    value = raw[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise HypothesisError(f"{field} must be a list of strings")
    result = tuple(value)
    if nonempty and not result:
        raise HypothesisError(f"{field} must not be empty")
    if any(not item or item != item.strip() for item in result):
        raise HypothesisError(f"{field} values must be non-empty and trimmed")
    return result


@dataclass(frozen=True, slots=True)
class HypothesisRecord:
    """A cited idea and its explicitly lossy executable transformation."""

    hypothesis_id: str
    candidate_id: str
    title: str
    source_refs: tuple[str, ...]
    expected_strategy_id: str
    expected_spec_sha256: str
    semantic_transformation: str
    proxy_notes: tuple[str, ...]
    target_market: str
    target_instrument: str
    target_timeframe: str
    assumptions: tuple[str, ...]
    ambiguities: tuple[str, ...]
    faithful_paper_reproduction: bool
    profit_claims_inherited: bool
    locally_reproduced: bool
    approval_eligible: bool

    def __post_init__(self) -> None:
        for field in (
            "hypothesis_id",
            "candidate_id",
            "title",
            "expected_strategy_id",
            "expected_spec_sha256",
            "semantic_transformation",
            "target_market",
            "target_instrument",
            "target_timeframe",
        ):
            value = getattr(self, field)
            if not value or value != value.strip():
                raise HypothesisError(f"{field} must be non-empty and trimmed")
        if not _HYPOTHESIS_ID.fullmatch(self.hypothesis_id):
            raise HypothesisError(f"invalid hypothesis_id: {self.hypothesis_id}")
        if not _STRATEGY_ID.fullmatch(self.expected_strategy_id):
            raise HypothesisError(f"invalid expected_strategy_id: {self.expected_strategy_id}")
        if not _SHA256.fullmatch(self.expected_spec_sha256):
            raise HypothesisError("expected_spec_sha256 must be a lowercase SHA-256 digest")
        if not re.fullmatch(r"B[234]", self.candidate_id):
            raise HypothesisError(f"invalid candidate_id: {self.candidate_id}")
        for field in ("source_refs", "proxy_notes", "assumptions", "ambiguities"):
            values = getattr(self, field)
            if not isinstance(values, tuple) or any(
                not value or value != value.strip() for value in values
            ):
                raise HypothesisError(f"{field} must contain trimmed strings")
        if not self.source_refs or not self.proxy_notes or not self.assumptions:
            raise HypothesisError("source_refs, proxy_notes, and assumptions must not be empty")
        booleans = (
            self.faithful_paper_reproduction,
            self.profit_claims_inherited,
            self.locally_reproduced,
            self.approval_eligible,
        )
        if any(not isinstance(value, bool) for value in booleans):
            raise HypothesisError("lineage state fields must be booleans")
        if any(booleans):
            raise HypothesisError("proxy hypotheses cannot inherit proof or approval state")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> HypothesisRecord:
        expected = set(cls.__dataclass_fields__)
        missing, extra = expected - raw.keys(), raw.keys() - expected
        if missing or extra:
            raise HypothesisError(
                f"hypothesis fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )

        def boolean(field: str) -> bool:
            value = raw[field]
            if not isinstance(value, bool):
                raise HypothesisError(f"{field} must be a boolean")
            return value

        return cls(
            hypothesis_id=_string(raw, "hypothesis_id"),
            candidate_id=_string(raw, "candidate_id"),
            title=_string(raw, "title"),
            source_refs=_strings(raw, "source_refs", nonempty=True),
            expected_strategy_id=_string(raw, "expected_strategy_id"),
            expected_spec_sha256=_string(raw, "expected_spec_sha256"),
            semantic_transformation=_string(raw, "semantic_transformation"),
            proxy_notes=_strings(raw, "proxy_notes", nonempty=True),
            target_market=_string(raw, "target_market"),
            target_instrument=_string(raw, "target_instrument"),
            target_timeframe=_string(raw, "target_timeframe"),
            assumptions=_strings(raw, "assumptions", nonempty=True),
            ambiguities=_strings(raw, "ambiguities"),
            faithful_paper_reproduction=boolean("faithful_paper_reproduction"),
            profit_claims_inherited=boolean("profit_claims_inherited"),
            locally_reproduced=boolean("locally_reproduced"),
            approval_eligible=boolean("approval_eligible"),
        )


class HypothesisRegistry:
    """Deterministic index whose source references resolve at construction."""

    def __init__(
        self, records: Iterable[HypothesisRecord], sources: ResearchSourceRegistry
    ) -> None:
        ordered = tuple(sorted(records, key=lambda record: record.hypothesis_id))
        ids = [record.hypothesis_id for record in ordered]
        candidates = [record.candidate_id for record in ordered]
        if len(ids) != len(set(ids)):
            raise HypothesisError("duplicate hypothesis_id")
        if len(candidates) != len(set(candidates)):
            raise HypothesisError("duplicate candidate_id")
        for record in ordered:
            for source_ref in record.source_refs:
                try:
                    sources.get(source_ref)
                except ResearchSourceError as exc:
                    raise HypothesisError(
                        f"{record.hypothesis_id} references unknown source: {source_ref}"
                    ) from exc
        self._records = ordered
        self._by_id = {record.hypothesis_id: record for record in ordered}
        self._by_candidate = {record.candidate_id: record for record in ordered}

    @classmethod
    def load(cls, path: Path, sources: ResearchSourceRegistry) -> HypothesisRegistry:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"registry_version", "hypotheses"}:
            raise HypothesisError("registry must contain registry_version and hypotheses")
        if raw["registry_version"] != 1 or not isinstance(raw["hypotheses"], list):
            raise HypothesisError("registry_version must be 1 and hypotheses must be a list")
        records = []
        for hypothesis in raw["hypotheses"]:
            if not isinstance(hypothesis, dict):
                raise HypothesisError("each hypothesis must be a mapping")
            records.append(HypothesisRecord.from_mapping(hypothesis))
        return cls(records, sources)

    def get(self, hypothesis_id: str) -> HypothesisRecord:
        try:
            return self._by_id[hypothesis_id]
        except KeyError as exc:
            raise HypothesisError(f"unknown hypothesis: {hypothesis_id}") from exc

    def for_candidate(self, candidate_id: str) -> HypothesisRecord:
        try:
            return self._by_candidate[candidate_id]
        except KeyError as exc:
            raise HypothesisError(f"unknown candidate: {candidate_id}") from exc

    def list(self) -> tuple[HypothesisRecord, ...]:
        return self._records

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(
                [record.to_dict() for record in self._records],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
