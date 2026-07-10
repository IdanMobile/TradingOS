"""Local-first Trading Evidence Registry records and storage."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ValidationState = Literal["UNVALIDATED", "VALIDATED", "REJECTED"]
ApprovalState = Literal["NOT_ELIGIBLE", "ELIGIBLE", "APPROVED"]


class EvidenceError(ValueError):
    """Raised when an evidence record would violate its contract."""


@dataclass(frozen=True)
class EvidenceRecord:
    """Trading-domain link to generic run and dataset lineage.

    ``run_ref`` and ``dataset_ref`` are stable public references only. This
    record intentionally does not import or mirror MLflow/DVC structures.
    """

    evidence_id: str
    hypothesis_id: str
    strategy_version_id: str
    market: str
    instrument: str
    timeframe: str
    run_ref: str
    dataset_ref: str
    validation_state: ValidationState = "UNVALIDATED"
    approval_state: ApprovalState = "NOT_ELIGIBLE"

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "hypothesis_id",
            "strategy_version_id",
            "market",
            "instrument",
            "timeframe",
            "run_ref",
            "dataset_ref",
        ):
            value = getattr(self, name)
            if not value or value != value.strip() or any(char.isspace() for char in value):
                raise EvidenceError(f"{name} must be a non-empty stable reference")
        if self.validation_state == "UNVALIDATED" and self.approval_state != "NOT_ELIGIBLE":
            raise EvidenceError("UNVALIDATED evidence must remain NOT_ELIGIBLE")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class EvidenceRegistry:
    """Append-only JSONL registry suitable for a local developer checkout."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def add(self, record: EvidenceRecord) -> EvidenceRecord:
        if any(item.evidence_id == record.evidence_id for item in self.list()):
            raise EvidenceError(f"evidence already exists: {record.evidence_id}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")) + "\n")
        return record

    def list(self) -> tuple[EvidenceRecord, ...]:
        if not self.path.exists():
            return ()
        return tuple(
            EvidenceRecord(**json.loads(line))
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    def get(self, evidence_id: str) -> EvidenceRecord:
        for record in self.list():
            if record.evidence_id == evidence_id:
                return record
        raise EvidenceError(f"unknown evidence: {evidence_id}")
