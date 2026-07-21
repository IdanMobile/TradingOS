from __future__ import annotations

import hashlib
import json
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tios.approval.intake_admission import (
    EXTERNAL_ACTIVATION_BLOCKERS,
    DetachedAttestation,
    IndependentIntakeVerifier,
    IntakeAdmissionError,
    IntakeAdmissionState,
    IntakeAdmissionStatus,
    IntakeDecisionOutcome,
    ReviewerRole,
    ReviewResolution,
    ReviewResolutionOutcome,
    SignedIntakeDecision,
    VerifiedReviewer,
    assess_intake_decision,
    build_intake_decision,
    parse_signed_intake_decision,
)
from tios.research_assets.admission import (
    CandidateDossier,
    CandidateIntakeLedger,
    ClosedFamilyComparison,
    DigestReference,
    LawfulEvidenceClass,
    ReferencePurpose,
    WorkspaceFileReference,
)

SHA_A = "a" * 64
NOW = datetime(2026, 7, 21, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _workspace(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_STATE.md").write_text("authority", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")


def _write_json(root: Path, ref: str, payload: object) -> None:
    target = root / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _capture(root: Path, ref: str, purpose: ReferencePurpose) -> WorkspaceFileReference:
    return WorkspaceFileReference.capture(root, ref, purpose)


def _dossier(root: Path, *, reject: bool = False) -> CandidateDossier:
    comparison = ClosedFamilyComparison.create(("FAM-CLOSED-V1",), reject, rescue_requested=reject)
    _write_json(root, "research/data.json", {"schema_version": 1, "kind": "DATA"})
    data = _capture(root, "research/data.json", ReferencePurpose.DATA_PACKAGE)
    common: dict[str, Any] = {
        "source_records": (DigestReference("SRC-ONE", SHA_A),),
        "hypothesis": DigestReference("HYP-ONE", SHA_A),
        "family_id": "FAM-FRESH-V1",
        "comparison": comparison,
        "dataset_packages": (data,),
        "canonical_spec_sha256": SHA_A,
        "lawful_evidence_class": LawfulEvidenceClass.NONE,
    }
    base = CandidateDossier.create(**common)
    _write_json(
        root,
        "research/catalog.json",
        {
            "schema_version": 1,
            "kind": "CLOSED_FAMILY_CATALOG",
            "catalog_id": "CATALOG-V9",
            "closed_family_ids": ["FAM-CLOSED-V1"],
            "execution_authority": "NONE",
        },
    )
    catalog = _capture(root, "research/catalog.json", ReferencePurpose.CLOSED_FAMILY_CATALOG)
    _write_json(
        root,
        "docs/supervisor/assessment.json",
        {
            "schema_version": 1,
            "kind": "FAMILY_ASSESSMENT",
            "assessment_id": "ASSESSMENT-ONE",
            "family_id": "FAM-FRESH-V1",
            "canonical_spec_sha256": SHA_A,
            "research_input_digest": base.research_input_digest,
            "catalog_sha256": catalog.sha256,
            "nearest_family_ids": ["FAM-CLOSED-V1"],
            "matches_closed_family": reject,
            "execution_authority": "NONE",
        },
    )
    assessment = _capture(
        root, "docs/supervisor/assessment.json", ReferencePurpose.FAMILY_ASSESSMENT
    )
    return CandidateDossier.create(
        **common, closed_family_catalog=catalog, family_assessment=assessment
    )


class FakeVerifier(IndependentIntakeVerifier):
    def __init__(self, reviewer: VerifiedReviewer) -> None:
        self.reviewer = reviewer
        self.calls = 0

    def verify(self, signing_bytes: bytes, attestation: DetachedAttestation) -> VerifiedReviewer:
        assert signing_bytes.startswith(b"TIOS/INTAKE-ADMISSION/v1\0{")
        assert attestation.signature_base64 == "ZmFrZQ=="
        self.calls += 1
        return self.reviewer


class MalformedVerifier(IndependentIntakeVerifier):
    def verify(self, signing_bytes: bytes, attestation: DetachedAttestation) -> VerifiedReviewer:
        del signing_bytes, attestation
        return object()  # type: ignore[return-value]


def _reviewer(**changes: object) -> VerifiedReviewer:
    values: dict[str, Any] = {
        "reviewer_id": "REVIEWER-EXTERNAL-ONE",
        "credential_id": "CREDENTIAL-ONE",
        "trusted_roles": (ReviewerRole.INDEPENDENT_INTAKE_ADMISSION_REVIEWER,),
        "credential_valid_from": NOW - timedelta(days=2),
        "credential_expires_at": NOW + timedelta(days=2),
        "credential_revoked_at": None,
        "trust_snapshot_id": "TRUST-SNAPSHOT-ONE",
        "trust_snapshot_digest": "b" * 64,
        "trust_snapshot_observed_at": NOW - timedelta(hours=1),
        "trust_snapshot_valid_until": NOW + timedelta(hours=2),
    }
    return VerifiedReviewer(**{**values, **changes})


def _decision(
    ledger: CandidateIntakeLedger,
    dossier: CandidateDossier,
    *,
    outcome: IntakeDecisionOutcome = IntakeDecisionOutcome.ADMIT,
    resolution_outcome: ReviewResolutionOutcome = ReviewResolutionOutcome.SATISFIED,
    **changes: object,
) -> SignedIntakeDecision:
    status = ledger.list_statuses()[0]
    assert dossier.closed_family_catalog is not None
    assert dossier.family_assessment is not None
    resolutions = tuple(
        ReviewResolution(domain, resolution_outcome, ("c" * 64,), ("REVIEWED",))
        for domain in status.pending_reviews
    )
    values: dict[str, Any] = {
        "dossier_id": dossier.dossier_id,
        "dossier_digest": dossier.dossier_digest,
        "catalog_sha256": dossier.closed_family_catalog.sha256,
        "assessment_sha256": dossier.family_assessment.sha256,
        "predecessor_entry_hash": status.entry_hash,
        "predecessor_state": IntakeAdmissionState.REVIEW_REQUIRED,
        "outcome": outcome,
        "reviewer_id": "REVIEWER-EXTERNAL-ONE",
        "asserted_role": ReviewerRole.INDEPENDENT_INTAKE_ADMISSION_REVIEWER,
        "credential_id": "CREDENTIAL-ONE",
        "trust_snapshot_id": "TRUST-SNAPSHOT-ONE",
        "trust_snapshot_digest": "b" * 64,
        "trust_snapshot_observed_at": NOW - timedelta(hours=1),
        "decision_at": NOW - timedelta(minutes=30),
        "expires_at": NOW + timedelta(hours=1),
        "resolutions": resolutions,
        "rejection_reasons": ("INDEPENDENT_REJECTION",)
        if outcome is IntakeDecisionOutcome.REJECT
        else (),
    }
    statement = build_intake_decision(**{**values, **changes})
    digest = hashlib.sha256(statement.signing_bytes()).hexdigest()
    return SignedIntakeDecision(
        statement,
        DetachedAttestation("ED25519", statement.credential_id, "ZmFrZQ==", digest),
    )


def _registered(root: Path) -> tuple[CandidateIntakeLedger, CandidateDossier]:
    dossier = _dossier(root)
    ledger = CandidateIntakeLedger(root)
    ledger.register(dossier)
    return ledger, dossier


def test_default_verifier_and_empty_or_generic_files_cannot_admit(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier)
    status = assess_intake_decision(ledger, dossier.dossier_id, (decision,), evaluated_at=NOW)
    assert status.state is IntakeAdmissionState.REVIEW_REQUIRED
    assert status.blockers == ("INDEPENDENT_VERIFIER_UNAVAILABLE",)
    assert status.execution_authority == "NONE"
    (tmp_path / "generic_operator_approval.json").write_text('{"decision":"APPROVE"}')
    assert (
        assess_intake_decision(
            ledger, dossier.dossier_id, (), evaluated_at=NOW, verifier=FakeVerifier(_reviewer())
        ).state
        is IntakeAdmissionState.REVIEW_REQUIRED
    )


def test_valid_fake_verifier_only_reaches_blocked_pending_activation(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier)
    verifier = FakeVerifier(_reviewer())
    status = assess_intake_decision(
        ledger, dossier.dossier_id, (decision,), evaluated_at=NOW, verifier=verifier
    )
    assert status.state is IntakeAdmissionState.VERIFIED_PENDING_EXTERNAL_ACTIVATION
    assert status.decision_id == decision.statement.decision_id
    assert EXTERNAL_ACTIVATION_BLOCKERS.issubset(status.blockers)
    assert "AUTHORITATIVE_EXTERNAL_DECISION_HISTORY_UNAVAILABLE" in status.blockers
    assert "REVIEW_EVIDENCE_DIGESTS_ARE_UNTRUSTED_CLAIMS" in status.blockers
    assert "ADMITTED" not in {state.value for state in IntakeAdmissionState}
    assert status.execution_authority == "NONE"
    assert verifier.calls == 1


def test_canonical_round_trip_and_signing_bytes_are_stable(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier)
    encoded = json.dumps(decision.to_dict(), sort_keys=True, separators=(",", ":"))
    parsed = parse_signed_intake_decision(encoded)
    assert parsed == decision
    assert parsed.statement.signing_bytes() == decision.statement.signing_bytes()
    assert (
        build_intake_decision(
            **{
                field.name: getattr(decision.statement, field.name)
                for field in fields(decision.statement)
                if field.name != "decision_id"
            }
        )
        == decision.statement
    )


def test_text_parser_rejects_duplicate_keys_and_noncanonical_artifacts(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier)
    canonical = json.dumps(decision.to_dict(), sort_keys=True, separators=(",", ":"))
    with pytest.raises(IntakeAdmissionError, match="exact canonical JSON"):
        parse_signed_intake_decision(json.dumps(decision.to_dict(), indent=2))
    duplicate = (
        '{"attestation":'
        + json.dumps(decision.attestation.to_dict(), sort_keys=True, separators=(",", ":"))
        + ',"statement":'
        + json.dumps(decision.statement.to_dict(), sort_keys=True, separators=(",", ":"))
        + ',"statement":'
        + json.dumps(decision.statement.to_dict(), sort_keys=True, separators=(",", ":"))
        + "}"
    )
    with pytest.raises(IntakeAdmissionError, match="duplicate JSON key"):
        parse_signed_intake_decision(duplicate)
    assert parse_signed_intake_decision(canonical.encode()) == decision


@pytest.mark.parametrize("algorithm", ["NONE", "FAKE", "FAKE-V1", "TEST", "TEST-V2"])
def test_sentinel_attestation_algorithms_are_rejected(algorithm: str) -> None:
    with pytest.raises(IntakeAdmissionError, match="sentinel"):
        DetachedAttestation(algorithm, "CREDENTIAL-ONE", "ZmFrZQ==", "a" * 64)


def test_status_cannot_be_fabricated_as_authoritative() -> None:
    with pytest.raises(IntakeAdmissionError):
        IntakeAdmissionStatus("RC-x", IntakeAdmissionState.REVIEW_REQUIRED, None, ())
    with pytest.raises(IntakeAdmissionError):
        IntakeAdmissionStatus(
            "RC-x",
            IntakeAdmissionState.VERIFIED_PENDING_EXTERNAL_ACTIVATION,
            "IAD-" + "a" * 32,
            ("AUTHORITATIVE_EXTERNAL_DECISION_HISTORY_UNAVAILABLE",),
        )
    with pytest.raises(IntakeAdmissionError):
        IntakeAdmissionStatus("RC-x", IntakeAdmissionState.REJECTED, None, ("UNEXPECTED_BLOCKER",))
    with pytest.raises(IntakeAdmissionError, match="only be produced"):
        IntakeAdmissionStatus(
            "RC-x",
            IntakeAdmissionState.VERIFIED_PENDING_EXTERNAL_ACTIVATION,
            "IAD-" + "a" * 32,
            tuple(sorted(EXTERNAL_ACTIVATION_BLOCKERS)),
        )


def test_malformed_verifier_return_fails_closed(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    status = assess_intake_decision(
        ledger,
        dossier.dossier_id,
        (_decision(ledger, dossier),),
        evaluated_at=NOW,
        verifier=MalformedVerifier(),
    )
    assert status.state is IntakeAdmissionState.REVIEW_REQUIRED
    assert status.blockers == ("ATTESTATION_NOT_VERIFIED",)


def test_verified_reviewer_rejects_snapshot_time_rollback() -> None:
    with pytest.raises(IntakeAdmissionError, match="snapshot predates"):
        _reviewer(
            credential_valid_from=NOW - timedelta(minutes=30),
            trust_snapshot_observed_at=NOW - timedelta(hours=1),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"dossier_digest": "d" * 64},
        {"catalog_sha256": "d" * 64},
        {"assessment_sha256": "d" * 64},
        {"predecessor_entry_hash": "LE-" + "d" * 64},
    ],
)
def test_wrong_authoritative_bindings_fail_closed(tmp_path: Path, change: dict[str, Any]) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier, **change)
    assert (
        assess_intake_decision(
            ledger,
            dossier.dossier_id,
            (decision,),
            evaluated_at=NOW,
            verifier=FakeVerifier(_reviewer()),
        ).state
        is IntakeAdmissionState.REVIEW_REQUIRED
    )


def test_file_mutation_fails_before_verifier(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier)
    verifier = FakeVerifier(_reviewer())
    (tmp_path / "research/data.json").write_text("changed", encoding="utf-8")
    with pytest.raises(IntakeAdmissionError, match="ledger verification failed"):
        assess_intake_decision(
            ledger, dossier.dossier_id, (decision,), evaluated_at=NOW, verifier=verifier
        )
    assert verifier.calls == 0


def test_tampered_payload_digest_and_extra_outcome_fields_are_rejected(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    raw = _decision(ledger, dossier).to_dict()
    raw["attestation"]["signed_payload_digest"] = "d" * 64  # type: ignore[index]
    with pytest.raises(IntakeAdmissionError, match="signed payload digest"):
        parse_signed_intake_decision(raw)
    raw = _decision(ledger, dossier).to_dict()
    raw["statement"]["performance"] = "PASS"  # type: ignore[index]
    with pytest.raises(IntakeAdmissionError, match="outcome fields"):
        parse_signed_intake_decision(raw)


def test_phase_two_reject_is_terminal_without_calling_verifier(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path, reject=True)
    ledger = CandidateIntakeLedger(tmp_path)
    ledger.register(dossier)
    verifier = FakeVerifier(_reviewer())
    status = assess_intake_decision(
        ledger, dossier.dossier_id, (), evaluated_at=NOW, verifier=verifier
    )
    assert status.state is IntakeAdmissionState.REJECTED
    assert verifier.calls == 0


def test_missing_extra_duplicate_and_unsatisfied_domains_fail_closed(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    valid = _decision(ledger, dossier)
    resolutions = valid.statement.resolutions
    cases = (
        resolutions[:-1],
        resolutions
        + (
            ReviewResolution(
                resolutions[0].domain, ReviewResolutionOutcome.SATISFIED, ("d" * 64,), ("SECOND",)
            ),
        ),
        tuple(
            replace(item, outcome=ReviewResolutionOutcome.UNSATISFIED) if index == 0 else item
            for index, item in enumerate(resolutions)
        ),
    )
    for replacement in cases:
        try:
            decision = _decision(ledger, dossier, resolutions=replacement)
        except IntakeAdmissionError:
            continue
        assert (
            assess_intake_decision(
                ledger,
                dossier.dossier_id,
                (decision,),
                evaluated_at=NOW,
                verifier=FakeVerifier(_reviewer()),
            ).state
            is IntakeAdmissionState.REVIEW_REQUIRED
        )


def test_typed_external_rejection_requires_reason_but_cannot_close_candidate(
    tmp_path: Path,
) -> None:
    ledger, dossier = _registered(tmp_path)
    with pytest.raises(IntakeAdmissionError, match="requires rejection reasons"):
        _decision(
            ledger,
            dossier,
            outcome=IntakeDecisionOutcome.REJECT,
            rejection_reasons=(),
        )
    rejection = _decision(ledger, dossier, outcome=IntakeDecisionOutcome.REJECT)
    status = assess_intake_decision(
        ledger,
        dossier.dossier_id,
        (rejection,),
        evaluated_at=NOW,
        verifier=FakeVerifier(_reviewer()),
    )
    assert status.state is IntakeAdmissionState.VERIFIED_REJECTION_PENDING_EXTERNAL_ACTIVATION
    assert status.decision_id == rejection.statement.decision_id
    assert EXTERNAL_ACTIVATION_BLOCKERS.issubset(status.blockers)
    assert status.execution_authority == "NONE"


@pytest.mark.parametrize(
    "reviewer_change",
    [
        {"reviewer_id": "REVIEWER-OTHER"},
        {"credential_id": "CREDENTIAL-OTHER"},
        {"trusted_roles": ()},
        {"credential_revoked_at": NOW - timedelta(minutes=1)},
        {
            "credential_valid_from": NOW - timedelta(minutes=20),
            "trust_snapshot_observed_at": NOW - timedelta(minutes=10),
        },
        {"credential_expires_at": NOW},
        {"trust_snapshot_id": "TRUST-SNAPSHOT-OTHER"},
        {"trust_snapshot_digest": "d" * 64},
        {"trust_snapshot_observed_at": NOW - timedelta(hours=2)},
        {"trust_snapshot_valid_until": NOW},
    ],
)
def test_identity_credential_role_revocation_and_snapshot_fail_closed(
    tmp_path: Path, reviewer_change: dict[str, object]
) -> None:
    ledger, dossier = _registered(tmp_path)
    decision = _decision(ledger, dossier)
    reviewer = _reviewer(**reviewer_change)
    assert (
        assess_intake_decision(
            ledger,
            dossier.dossier_id,
            (decision,),
            evaluated_at=NOW,
            verifier=FakeVerifier(reviewer),
        ).state
        is IntakeAdmissionState.REVIEW_REQUIRED
    )


def test_future_expired_naive_and_replayed_decisions_fail_closed(tmp_path: Path) -> None:
    ledger, dossier = _registered(tmp_path)
    valid = _decision(ledger, dossier)
    future = _decision(
        ledger,
        dossier,
        decision_at=NOW + timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=2),
    )
    expired = _decision(
        ledger,
        dossier,
        trust_snapshot_observed_at=NOW - timedelta(hours=3),
        decision_at=NOW - timedelta(hours=2),
        expires_at=NOW,
    )
    verifier = FakeVerifier(_reviewer())
    for decisions in ((future,), (expired,), (valid, valid)):
        assert (
            assess_intake_decision(
                ledger, dossier.dossier_id, decisions, evaluated_at=NOW, verifier=verifier
            ).state
            is IntakeAdmissionState.REVIEW_REQUIRED
        )
    with pytest.raises(IntakeAdmissionError, match="timezone-aware"):
        replace(valid.statement, decision_at=datetime(2026, 7, 21, 11))
