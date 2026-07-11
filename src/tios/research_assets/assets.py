"""Validated registry for application-owned research assets."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

_RA_ID = re.compile(r"RA-[A-Z0-9]+(?:-[A-Z0-9]+)*\Z")


class ResearchAssetError(ValueError):
    """Raised when a research-asset registry is not usable as evidence."""


class FreshnessState(StrEnum):
    CURRENT = "CURRENT"
    AGING = "AGING"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"
    SUPERSEDED = "SUPERSEDED"


class HumanReviewStatus(StrEnum):
    REVIEWED = "REVIEWED"
    PENDING_HUMAN_REVIEW = "PENDING_HUMAN_REVIEW"
    NOT_REQUIRED = "NOT_REQUIRED"


def _nonempty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ResearchAssetError(f"{field} must be a non-empty trimmed string")
    return value


def _strings(value: object, field: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ResearchAssetError(f"{field} must be a list of strings")
    result = tuple(_nonempty(item, field) for item in value)
    if nonempty and not result:
        raise ResearchAssetError(f"{field} must not be empty")
    return result


@dataclass(frozen=True)
class ResearchAssetRecord:
    """A retained research artifact plus its freshness and consumers."""

    asset_id: str
    title: str
    question: str
    creator: str
    created_at: str
    cost_usd: float
    sources: tuple[str, ...]
    quality_score_refs: tuple[str, ...]
    human_review: HumanReviewStatus
    dependencies: tuple[str, ...]
    consumers: tuple[str, ...]
    freshness: FreshnessState
    contradiction_refs: tuple[str, ...]
    supersedes: tuple[str, ...]
    reverify_trigger: str

    def __post_init__(self) -> None:
        for field in ("asset_id", "title", "question", "creator", "created_at", "reverify_trigger"):
            _nonempty(getattr(self, field), field)
        if not _RA_ID.fullmatch(self.asset_id):
            raise ResearchAssetError(f"invalid asset_id: {self.asset_id}")
        if not isinstance(self.cost_usd, int | float) or isinstance(self.cost_usd, bool):
            raise ResearchAssetError("cost_usd must be numeric")
        if self.cost_usd < 0:
            raise ResearchAssetError("cost_usd must be non-negative")
        if not isinstance(self.human_review, HumanReviewStatus):
            raise ResearchAssetError("human_review must be a HumanReviewStatus")
        if not isinstance(self.freshness, FreshnessState):
            raise ResearchAssetError("freshness must be a FreshnessState")
        for field in (
            "sources",
            "quality_score_refs",
            "dependencies",
            "consumers",
            "contradiction_refs",
            "supersedes",
        ):
            if not isinstance(getattr(self, field), tuple):
                raise ResearchAssetError(f"{field} must be a tuple")
            for item in getattr(self, field):
                _nonempty(item, field)
        if not self.sources and not self.quality_score_refs:
            raise ResearchAssetError("research assets require source or quality evidence")
        for field in ("dependencies", "supersedes"):
            for asset_id in getattr(self, field):
                if not _RA_ID.fullmatch(asset_id):
                    raise ResearchAssetError(f"invalid {field} reference: {asset_id}")
        if self.freshness is FreshnessState.SUPERSEDED and not self.supersedes:
            raise ResearchAssetError("SUPERSEDED assets must name supersession evidence")
        if self.freshness is FreshnessState.CONTRADICTED and not self.contradiction_refs:
            raise ResearchAssetError("CONTRADICTED assets must name contradiction evidence")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> ResearchAssetRecord:
        expected = set(cls.__dataclass_fields__)
        missing, extra = expected - raw.keys(), raw.keys() - expected
        if missing or extra:
            raise ResearchAssetError(
                f"asset fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        cost = raw["cost_usd"]
        if not isinstance(cost, int | float) or isinstance(cost, bool):
            raise ResearchAssetError("cost_usd must be numeric")
        return cls(
            asset_id=_nonempty(raw["asset_id"], "asset_id"),
            title=_nonempty(raw["title"], "title"),
            question=_nonempty(raw["question"], "question"),
            creator=_nonempty(raw["creator"], "creator"),
            created_at=_nonempty(raw["created_at"], "created_at"),
            cost_usd=float(cost),
            sources=_strings(raw["sources"], "sources"),
            quality_score_refs=_strings(raw["quality_score_refs"], "quality_score_refs"),
            human_review=HumanReviewStatus(_nonempty(raw["human_review"], "human_review")),
            dependencies=_strings(raw["dependencies"], "dependencies"),
            consumers=_strings(raw["consumers"], "consumers", nonempty=True),
            freshness=FreshnessState(_nonempty(raw["freshness"], "freshness")),
            contradiction_refs=_strings(raw["contradiction_refs"], "contradiction_refs"),
            supersedes=_strings(raw["supersedes"], "supersedes"),
            reverify_trigger=_nonempty(raw["reverify_trigger"], "reverify_trigger"),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ResearchAssetRegistry:
    """Immutable in-memory index loaded from the application-owned JSON registry."""

    def __init__(self, records: Iterable[ResearchAssetRecord]) -> None:
        ordered = tuple(sorted(records, key=lambda record: record.asset_id))
        ids = [record.asset_id for record in ordered]
        if len(ids) != len(set(ids)):
            raise ResearchAssetError("duplicate asset_id")
        self._records = ordered
        self._by_id = {record.asset_id: record for record in ordered}
        for record in ordered:
            for field in ("dependencies", "supersedes"):
                refs = getattr(record, field)
                if len(refs) != len(set(refs)):
                    raise ResearchAssetError(f"duplicate {field} reference on {record.asset_id}")
                for asset_id in refs:
                    if asset_id == record.asset_id:
                        raise ResearchAssetError(f"{record.asset_id} cannot reference itself")
                    if asset_id not in self._by_id:
                        raise ResearchAssetError(
                            f"{record.asset_id} references unknown {field}: {asset_id}"
                        )
        self._reject_cycles("dependencies")
        self._reject_cycles("supersedes")

    @classmethod
    def load(cls, path: Path) -> ResearchAssetRegistry:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or set(raw) != {"registry_version", "assets"}:
            raise ResearchAssetError("registry must contain registry_version and assets")
        if raw["registry_version"] != 1 or not isinstance(raw["assets"], list):
            raise ResearchAssetError("registry_version must be 1 and assets must be a list")
        records = []
        for asset in raw["assets"]:
            if not isinstance(asset, dict):
                raise ResearchAssetError("each asset must be a mapping")
            records.append(ResearchAssetRecord.from_mapping(asset))
        return cls(records)

    def _reject_cycles(self, field: str) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(asset_id: str) -> None:
            if asset_id in visiting:
                raise ResearchAssetError(f"cyclic {field} graph is not allowed")
            if asset_id in visited:
                return
            visiting.add(asset_id)
            for ref in getattr(self._by_id[asset_id], field):
                visit(ref)
            visiting.remove(asset_id)
            visited.add(asset_id)

        for asset_id in self._by_id:
            visit(asset_id)

    def get(self, asset_id: str) -> ResearchAssetRecord:
        try:
            return self._by_id[asset_id]
        except KeyError as exc:
            raise ResearchAssetError(f"unknown asset: {asset_id}") from exc

    def list(self) -> tuple[ResearchAssetRecord, ...]:
        return self._records

    def consumers(self, consumer: str) -> tuple[ResearchAssetRecord, ...]:
        return tuple(record for record in self._records if consumer in record.consumers)

    def freshness(self, state: FreshnessState | str) -> tuple[ResearchAssetRecord, ...]:
        try:
            target = FreshnessState(state)
        except ValueError as exc:
            raise ResearchAssetError(f"unknown freshness state: {state}") from exc
        return tuple(record for record in self._records if record.freshness is target)

    def cost_amortization(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "asset_id": record.asset_id,
                "cost_usd": record.cost_usd,
                "consumer_count": len(record.consumers),
                "cost_per_consumer_usd": record.cost_usd / len(record.consumers),
                "consumers": record.consumers,
            }
            for record in self._records
        )

    def digest(self) -> str:
        payload = json.dumps(
            [record.to_dict() for record in self._records],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(payload).hexdigest()
