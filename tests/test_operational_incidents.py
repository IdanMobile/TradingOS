from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from tios.trading_domain import (
    ApprovalId,
    ContractError,
    CreatorType,
    DomainRef,
    OperationalIncidentRecord,
    OperationalIncidentSeverity,
    OperationalIncidentStatus,
    Provenance,
    Stage,
    advance_operational_incident,
)

NOW = datetime(2026, 7, 12, tzinfo=UTC)
EVIDENCE = DomainRef("EV-incident-open")
OWNER = DomainRef("APR-operator-owner")
PROVENANCE = Provenance((EVIDENCE,))


def opened() -> OperationalIncidentRecord:
    return OperationalIncidentRecord(
        incident_id=ApprovalId("APR-incident-feed-loss"),
        stage=Stage.S3_PAPER_DEMO,
        status=OperationalIncidentStatus.OPEN,
        severity=OperationalIncidentSeverity.CRITICAL,
        opened_at=NOW,
        summary="paper market-data heartbeat stopped",
        event_refs=(ApprovalId("APR-paper-event-heartbeat-missed"),),
        evidence_refs=(EVIDENCE,),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def test_operational_incident_lifecycle_is_append_only_and_inert() -> None:
    incident = opened()
    acknowledged = advance_operational_incident(
        incident,
        OperationalIncidentStatus.ACKNOWLEDGED,
        at=NOW + timedelta(minutes=2),
        owner_ref=OWNER,
        evidence_ref=DomainRef("EV-incident-acknowledged"),
    )
    assert incident.status is OperationalIncidentStatus.OPEN
    assert acknowledged.owner_ref == OWNER
    assert acknowledged.execution_authority.value == "NONE"
    assert acknowledged.paper_orders.value == acknowledged.live_orders.value == "DISABLED"

    resolved = advance_operational_incident(
        acknowledged,
        OperationalIncidentStatus.RESOLVED,
        at=NOW + timedelta(minutes=10),
        owner_ref=OWNER,
        evidence_ref=DomainRef("EV-incident-resolved"),
        resolution_summary="feed restored and stale-data guard verified",
        post_incident_ref=DomainRef("EV-post-incident-report"),
    )
    assert resolved.status is OperationalIncidentStatus.RESOLVED
    assert resolved.resolution_summary is not None
    assert len(resolved.evidence_refs) == 3


def test_operational_incident_lifecycle_rejects_skips_and_incomplete_resolution() -> None:
    with pytest.raises(ContractError, match="invalid operational incident transition"):
        advance_operational_incident(
            opened(),
            OperationalIncidentStatus.RESOLVED,
            at=NOW + timedelta(minutes=1),
            owner_ref=OWNER,
            evidence_ref=DomainRef("EV-incident-invalid-skip"),
            resolution_summary="not allowed",
            post_incident_ref=DomainRef("EV-post-incident-invalid"),
        )
    acknowledged = advance_operational_incident(
        opened(),
        OperationalIncidentStatus.ACKNOWLEDGED,
        at=NOW + timedelta(minutes=2),
        owner_ref=OWNER,
        evidence_ref=DomainRef("EV-incident-acknowledged"),
    )
    with pytest.raises(ContractError, match="require resolution"):
        advance_operational_incident(
            acknowledged,
            OperationalIncidentStatus.RESOLVED,
            at=NOW + timedelta(minutes=3),
            owner_ref=OWNER,
            evidence_ref=DomainRef("EV-incident-bad-resolution"),
        )
    with pytest.raises(ContractError, match="cannot activate orders"):
        replace(opened(), paper_orders="ENABLED")  # type: ignore[arg-type]
