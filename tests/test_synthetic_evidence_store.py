import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tios.evidence import SyntheticEvidenceStore, SyntheticEvidenceStoreError
from tios.trading_domain import (
    ApprovalId,
    CreatorType,
    DomainRef,
    OperationalIncidentRecord,
    OperationalIncidentSeverity,
    OperationalIncidentStatus,
    Provenance,
    Stage,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
EVIDENCE = (DomainRef("EV-stored-incident"),)
PROVENANCE = Provenance(EVIDENCE)


def incident(summary: str = "feed heartbeat stopped") -> OperationalIncidentRecord:
    return OperationalIncidentRecord(
        incident_id=ApprovalId("APR-stored-incident"),
        stage=Stage.S3_PAPER_DEMO,
        status=OperationalIncidentStatus.OPEN,
        severity=OperationalIncidentSeverity.CRITICAL,
        opened_at=NOW,
        summary=summary,
        event_refs=(ApprovalId("APR-stored-event"),),
        evidence_refs=EVIDENCE,
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def store(root: Path) -> SyntheticEvidenceStore:
    return SyntheticEvidenceStore(
        root / "artifacts/evidence/synthetic_s3_s4.sqlite3",
        root=root,
    )


def append(target: SyntheticEvidenceStore, record=None):  # type: ignore[no-untyped-def]
    return target.append(
        record or incident(),
        idempotency_key="incident-open-v1",
        record_id="APR-stored-incident",
        record_type="OperationalIncidentRecord",
        stage=Stage.S3_PAPER_DEMO,
        occurred_at=NOW,
        recorded_at=NOW,
    )


def test_synthetic_evidence_store_is_idempotent_queryable_and_integral(tmp_path: Path) -> None:
    target = store(tmp_path)
    first = append(target)
    replay = append(target)
    assert first == replay
    assert first.sequence == 1
    assert first.payload["execution_authority"] == "NONE"
    assert first.payload["paper_orders"] == "DISABLED"
    assert target.list(stage=Stage.S3_PAPER_DEMO) == (first,)
    assert target.list(record_type="OperationalIncidentRecord") == (first,)
    assert target.integrity_check() is True

    with pytest.raises(SyntheticEvidenceStoreError, match="idempotency key conflicts"):
        append(target, incident("different retained content"))


def test_synthetic_evidence_store_serializes_concurrent_replay(tmp_path: Path) -> None:
    target = store(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        rows = tuple(executor.map(lambda _: append(target), range(16)))
    assert {row.sequence for row in rows} == {1}
    assert len(target.list()) == 1


def test_synthetic_evidence_store_database_rows_cannot_update_or_delete(tmp_path: Path) -> None:
    target = store(tmp_path)
    append(target)
    connection = sqlite3.connect(target.path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("UPDATE evidence_events SET record_type = 'changed'")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("DELETE FROM evidence_events")
    connection.close()


def test_synthetic_evidence_store_is_confined_and_has_bounded_queries(tmp_path: Path) -> None:
    with pytest.raises(SyntheticEvidenceStoreError, match="artifacts/evidence"):
        SyntheticEvidenceStore(tmp_path / "outside.sqlite3", root=tmp_path)
    target = store(tmp_path)
    with pytest.raises(SyntheticEvidenceStoreError, match="limit"):
        target.list(limit=0)
    outside = tmp_path / "outside.sqlite3"
    outside.touch()
    link = tmp_path / "artifacts/evidence/synthetic_s3_s4.sqlite3"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    with pytest.raises(SyntheticEvidenceStoreError, match="artifacts/evidence"):
        store(tmp_path)
