from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
from pathlib import Path

import pytest

import tios.research_assets.admission as admission_module
from tios.research_assets.admission import (
    CandidateDossier,
    CandidateIntakeError,
    CandidateIntakeLedger,
    ClosedFamilyComparison,
    DigestReference,
    IntakeVerdict,
    LawfulEvidenceClass,
    ReferencePurpose,
    ReviewDomain,
    WorkspaceFileReference,
)

SHA_A = "a" * 64


@pytest.fixture(autouse=True)
def _repository_markers(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_STATE.md").write_text("test authority", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")


def _json_write(root: Path, ref: str, payload: object) -> None:
    target = root / ref
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _capture(root: Path, ref: str, purpose: ReferencePurpose) -> WorkspaceFileReference:
    return WorkspaceFileReference.capture(root, ref, purpose)


def _dossier(
    root: Path,
    *,
    comparison: ClosedFamilyComparison | None = None,
    lawful_class: LawfulEvidenceClass = LawfulEvidenceClass.NONE,
    include_catalog: bool = True,
    include_assessment: bool = True,
) -> CandidateDossier:
    comparison = comparison or ClosedFamilyComparison.create(("FAM-CLOSED-V1",), False)
    _json_write(root, "research/data_package.json", {"schema_version": 1, "kind": "DATA"})
    data = _capture(root, "research/data_package.json", ReferencePurpose.DATA_PACKAGE)
    lawful = None
    if lawful_class is not LawfulEvidenceClass.NONE:
        _json_write(
            root, "research/lawful_evidence.json", {"schema_version": 1, "kind": "PROTOCOL"}
        )
        lawful = _capture(root, "research/lawful_evidence.json", ReferencePurpose.LAWFUL_EVIDENCE)
    inputs = {
        "source_records": (DigestReference("SRC-ONE", SHA_A),),
        "hypothesis": DigestReference("HYP-ONE", SHA_A),
        "family_id": "FAM-FRESH-V1",
        "comparison": comparison,
        "dataset_packages": (data,),
        "canonical_spec_sha256": SHA_A,
        "lawful_evidence_class": lawful_class,
        "lawful_evidence": lawful,
    }
    base = CandidateDossier.create(**inputs)
    catalog = None
    if include_catalog:
        _json_write(
            root,
            "research/catalog_v9.json",
            {
                "schema_version": 1,
                "kind": "CLOSED_FAMILY_CATALOG",
                "catalog_id": "CATALOG-V9",
                "closed_family_ids": ["FAM-CLOSED-V1"],
                "execution_authority": "NONE",
            },
        )
        catalog = _capture(root, "research/catalog_v9.json", ReferencePurpose.CLOSED_FAMILY_CATALOG)
    assessment = None
    if include_assessment:
        _json_write(
            root,
            "docs/supervisor/family_assessment.json",
            {
                "schema_version": 1,
                "kind": "FAMILY_ASSESSMENT",
                "assessment_id": "ASSESSMENT-ONE",
                "family_id": "FAM-FRESH-V1",
                "canonical_spec_sha256": SHA_A,
                "research_input_digest": base.research_input_digest,
                "catalog_sha256": catalog.sha256 if catalog else None,
                "nearest_family_ids": list(comparison.nearest_family_ids),
                "matches_closed_family": comparison.matches_closed_family,
                "execution_authority": "NONE",
            },
        )
        assessment = _capture(
            root, "docs/supervisor/family_assessment.json", ReferencePurpose.FAMILY_ASSESSMENT
        )
    return CandidateDossier.create(
        **inputs,
        closed_family_catalog=catalog,
        family_assessment=assessment,
    )


def test_intake_has_no_admit_or_resolution_api(tmp_path: Path) -> None:
    assert set(IntakeVerdict) == {IntakeVerdict.REVIEW_REQUIRED, IntakeVerdict.REJECT}
    assert not hasattr(CandidateIntakeLedger, "adjudicate")
    assert not hasattr(admission_module, "CandidateAdmissionLedger")
    assert not hasattr(admission_module, "CandidateAdmissionError")
    status = CandidateIntakeLedger(tmp_path).register(_dossier(tmp_path))
    assert status.verdict is IntakeVerdict.REVIEW_REQUIRED
    assert status.dossier.execution_authority == "NONE"
    assert (
        "INDEPENDENT_TYPED_DECISION_UNAVAILABLE_UNTIL_PHASE_2B"
        in json.loads(CandidateIntakeLedger(tmp_path).path.read_text())["reasons"]
    )


def test_identity_and_registration_are_permutation_stable_and_idempotent(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    assert dossier == _dossier(tmp_path)
    ledger = CandidateIntakeLedger(tmp_path)
    first = ledger.register(dossier)
    second = ledger.register(dossier)
    assert first.entry_hash == second.entry_hash
    assert len(ledger.path.read_text().splitlines()) == 1


def test_create_canonicalizes_set_like_input_permutations(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    _json_write(tmp_path, "research/data_second.json", {"schema_version": 1})
    second_data = _capture(tmp_path, "research/data_second.json", ReferencePurpose.DATA_PACKAGE)
    second_source = DigestReference("SRC-TWO", "b" * 64)
    common = {
        "hypothesis": dossier.hypothesis,
        "family_id": dossier.family_id,
        "comparison": ClosedFamilyComparison.create(("FAM-Z-V1", "FAM-A-V1"), False),
        "canonical_spec_sha256": dossier.canonical_spec_sha256,
    }
    first = CandidateDossier.create(
        **common,
        source_records=(second_source, dossier.source_records[0]),
        dataset_packages=(second_data, dossier.dataset_packages[0]),
    )
    second = CandidateDossier.create(
        **common,
        source_records=(dossier.source_records[0], second_source),
        dataset_packages=(dossier.dataset_packages[0], second_data),
    )
    assert first == second


@pytest.mark.parametrize("flag", ["rescue_requested", "version_reset_requested"])
def test_rescue_and_version_reset_are_terminal_intake_rejections(tmp_path: Path, flag: str) -> None:
    args = {
        "nearest_family_ids": ("FAM-CLOSED-V1",),
        "matches_closed_family": True,
        flag: True,
    }
    dossier = _dossier(tmp_path, comparison=ClosedFamilyComparison.create(**args))
    assert CandidateIntakeLedger(tmp_path).register(dossier).verdict is IntakeVerdict.REJECT


def test_closed_family_enum_and_file_never_self_admit(tmp_path: Path) -> None:
    dossier = _dossier(
        tmp_path,
        comparison=ClosedFamilyComparison.create(("FAM-CLOSED-V1",), True),
        lawful_class=LawfulEvidenceClass.LICENSED_AUTHORITATIVE_SOURCE,
    )
    status = CandidateIntakeLedger(tmp_path).register(dossier)
    assert status.verdict is IntakeVerdict.REVIEW_REQUIRED
    assert set(status.pending_reviews) == {
        ReviewDomain.ACCESS,
        ReviewDomain.DATA,
        ReviewDomain.OPERATOR,
    }


@pytest.mark.parametrize(
    ("lawful_class", "expected_reviews"),
    [
        (
            LawfulEvidenceClass.OFFICIAL_AUTHORITATIVE_SOURCE,
            {ReviewDomain.DATA, ReviewDomain.OPERATOR},
        ),
        (
            LawfulEvidenceClass.LICENSED_AUTHORITATIVE_SOURCE,
            {ReviewDomain.ACCESS, ReviewDomain.DATA, ReviewDomain.OPERATOR},
        ),
        (
            LawfulEvidenceClass.OPERATOR_SUPPLIED_SPEC_AND_UNSEEN_PIT_DATA,
            {ReviewDomain.DATA, ReviewDomain.OPERATOR},
        ),
        (
            LawfulEvidenceClass.PREREGISTERED_PROSPECTIVE_OBSERVATIONS,
            {ReviewDomain.DATA, ReviewDomain.OPERATOR},
        ),
    ],
)
def test_every_lawful_evidence_class_remains_review_required(
    tmp_path: Path,
    lawful_class: LawfulEvidenceClass,
    expected_reviews: set[ReviewDomain],
) -> None:
    dossier = _dossier(tmp_path, lawful_class=lawful_class)
    status = CandidateIntakeLedger(tmp_path).register(dossier)
    assert status.verdict is IntakeVerdict.REVIEW_REQUIRED
    assert set(status.pending_reviews) == expected_reviews
    assert not {"outcomes", "performance", "returns", "pnl"}.intersection(dossier.to_dict())


@pytest.mark.parametrize(
    "bad",
    [
        "/tmp/x",
        "../x",
        "research/../x",
        "research/sealed/x",
        "research/holdout/x",
        "research/outcomes.json",
        "research/performance.json",
        "research/results.json",
        "research/sharpe.json",
        "research/pnl.json",
        "research/returns.json",
        "research/profit.json",
        "research/drawdown.json",
        "research/score.json",
        "research/backtest.json",
        "research/evaluation.json",
        "research/metrics.json",
        "research/a\nx",
        "Research/data.json",
        "docs/Supervisor/data.json",
        "research//data.json",
        "research/data.json/",
    ],
)
def test_refs_reject_escape_gated_and_outcome_namespaces(bad: str) -> None:
    with pytest.raises(CandidateIntakeError):
        WorkspaceFileReference(bad, SHA_A, ReferencePurpose.DATA_PACKAGE)


def test_duplicate_logical_ids_and_refs_reject_conflicting_hashes(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    with pytest.raises(CandidateIntakeError, match="conflicting hashes"):
        CandidateDossier.create(
            source_records=(
                DigestReference("SRC-ONE", SHA_A),
                DigestReference("SRC-ONE", "b" * 64),
            ),
            hypothesis=dossier.hypothesis,
            family_id=dossier.family_id,
            comparison=dossier.comparison,
            dataset_packages=dossier.dataset_packages,
            canonical_spec_sha256=SHA_A,
        )
    conflicting = WorkspaceFileReference(
        dossier.dataset_packages[0].ref, "b" * 64, ReferencePurpose.DATA_PACKAGE
    )
    with pytest.raises(CandidateIntakeError, match="conflicting hashes"):
        CandidateDossier.create(
            source_records=dossier.source_records,
            hypothesis=dossier.hypothesis,
            family_id=dossier.family_id,
            comparison=dossier.comparison,
            dataset_packages=(dossier.dataset_packages[0], conflicting),
            canonical_spec_sha256=SHA_A,
        )


def test_catalog_and_assessment_are_strict_and_bound_to_dossier(tmp_path: Path) -> None:
    dossier = _dossier(tmp_path)
    assessment_path = tmp_path / "docs/supervisor/family_assessment.json"
    raw = json.loads(assessment_path.read_text())
    raw["family_id"] = "FAM-RENAMED-V1"
    _json_write(tmp_path, "docs/supervisor/family_assessment.json", raw)
    forged_ref = _capture(
        tmp_path, "docs/supervisor/family_assessment.json", ReferencePurpose.FAMILY_ASSESSMENT
    )
    forged = CandidateDossier.create(
        source_records=dossier.source_records,
        hypothesis=dossier.hypothesis,
        family_id=dossier.family_id,
        comparison=dossier.comparison,
        dataset_packages=dossier.dataset_packages,
        canonical_spec_sha256=dossier.canonical_spec_sha256,
        closed_family_catalog=dossier.closed_family_catalog,
        family_assessment=forged_ref,
    )
    with pytest.raises(CandidateIntakeError, match="does not bind dossier"):
        CandidateIntakeLedger(tmp_path).register(forged)


def test_assessment_rejects_non_boolean_match_and_catalog_rejects_invalid_id(
    tmp_path: Path,
) -> None:
    dossier = _dossier(tmp_path)
    assessment_path = tmp_path / "docs/supervisor/family_assessment.json"
    assessment = json.loads(assessment_path.read_text())
    assessment["matches_closed_family"] = 0
    _json_write(tmp_path, "docs/supervisor/family_assessment.json", assessment)
    bad_assessment = _capture(
        tmp_path,
        "docs/supervisor/family_assessment.json",
        ReferencePurpose.FAMILY_ASSESSMENT,
    )
    forged_assessment = CandidateDossier.create(
        source_records=dossier.source_records,
        hypothesis=dossier.hypothesis,
        family_id=dossier.family_id,
        comparison=dossier.comparison,
        dataset_packages=dossier.dataset_packages,
        canonical_spec_sha256=dossier.canonical_spec_sha256,
        closed_family_catalog=dossier.closed_family_catalog,
        family_assessment=bad_assessment,
    )
    with pytest.raises(CandidateIntakeError, match="must be a boolean"):
        CandidateIntakeLedger(tmp_path).register(forged_assessment)

    catalog_path = tmp_path / "research/catalog_v9.json"
    catalog = json.loads(catalog_path.read_text())
    catalog["closed_family_ids"] = ["bad family"]
    _json_write(tmp_path, "research/catalog_v9.json", catalog)
    bad_catalog = _capture(
        tmp_path, "research/catalog_v9.json", ReferencePurpose.CLOSED_FAMILY_CATALOG
    )
    forged = CandidateDossier.create(
        source_records=dossier.source_records,
        hypothesis=dossier.hypothesis,
        family_id=dossier.family_id,
        comparison=dossier.comparison,
        dataset_packages=dossier.dataset_packages,
        canonical_spec_sha256=dossier.canonical_spec_sha256,
        closed_family_catalog=bad_catalog,
    )
    with pytest.raises(CandidateIntakeError, match="invalid closed family identifier"):
        CandidateIntakeLedger(tmp_path).register(forged)


def test_workspace_root_must_be_exact_canonical_repository_root(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    with pytest.raises(CandidateIntakeError, match="cannot be opened"):
        CandidateIntakeLedger(nested)

    alias = tmp_path.parent / f"{tmp_path.name}-alias"
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(CandidateIntakeError, match="symlink components"):
        CandidateIntakeLedger(alias)

    prohibited = tmp_path / "artifacts/sealed/repository"
    prohibited.mkdir(parents=True)
    (prohibited / "PROJECT_STATE.md").write_text("x")
    (prohibited / "pyproject.toml").write_text("x")
    with pytest.raises(CandidateIntakeError, match="prohibited artifact subtree"):
        CandidateIntakeLedger(prohibited)


def test_every_read_reverifies_deleted_or_mutated_metadata(tmp_path: Path) -> None:
    ledger = CandidateIntakeLedger(tmp_path)
    ledger.register(_dossier(tmp_path))
    data = tmp_path / "research/data_package.json"
    data.write_text("changed")
    with pytest.raises(CandidateIntakeError, match="SHA-256 mismatch"):
        ledger.list_statuses()
    data.unlink()
    with pytest.raises(CandidateIntakeError, match="cannot be opened"):
        ledger.list_statuses()


def _rehash_entry(raw: dict[str, object]) -> None:
    unsigned = {key: value for key, value in raw.items() if key != "entry_hash"}
    digest = hashlib.sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    raw["entry_hash"] = f"LE-{digest}"


def test_policy_invalid_forged_chain_fails_even_with_recomputed_hash(tmp_path: Path) -> None:
    ledger = CandidateIntakeLedger(tmp_path)
    ledger.register(_dossier(tmp_path))
    raw = json.loads(ledger.path.read_text())
    raw["verdict"] = "REJECT"
    raw["pending_reviews"] = []
    raw["reasons"] = ["CALLER_ASSERTED"]
    _rehash_entry(raw)
    ledger.path.write_text(json.dumps(raw) + "\n")
    with pytest.raises(CandidateIntakeError, match="current policy"):
        ledger.list_statuses()


def test_chain_detects_physical_reorder_middle_delete_and_replacement(tmp_path: Path) -> None:
    ledger = CandidateIntakeLedger(tmp_path)
    first = _dossier(tmp_path)
    ledger.register(first)
    second = CandidateDossier.create(
        source_records=first.source_records,
        hypothesis=first.hypothesis,
        family_id="FAM-FRESH-V2",
        comparison=first.comparison,
        dataset_packages=first.dataset_packages,
        canonical_spec_sha256="b" * 64,
    )
    ledger.register(second)
    lines = ledger.path.read_text().splitlines()
    for corrupted in (
        [lines[1], lines[0]],
        [lines[1]],
        [lines[0].replace("FAM-FRESH-V1", "FAM-FORGED-V1"), lines[1]],
    ):
        ledger.path.write_text("\n".join(corrupted) + "\n")
        with pytest.raises(CandidateIntakeError):
            ledger.list_statuses()
    ledger.path.write_text("\n".join(lines) + "\n")


def test_symlinked_evidence_ledger_and_parent_are_rejected(tmp_path: Path) -> None:
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    secret = sealed / "secret.json"
    secret.write_text("secret")
    research = tmp_path / "research"
    research.mkdir()
    (research / "data_package.json").symlink_to(secret)
    with pytest.raises(CandidateIntakeError, match="links"):
        WorkspaceFileReference.capture(
            tmp_path, "research/data_package.json", ReferencePurpose.DATA_PACKAGE
        )
    (research / "data_package.json").unlink()
    dossier = _dossier(tmp_path)

    external = tmp_path / "external.jsonl"
    external.write_text("")
    ledger = CandidateIntakeLedger(tmp_path)
    ledger.path.parent.mkdir(parents=True)
    ledger.path.symlink_to(external)
    with pytest.raises(CandidateIntakeError, match="symlink"):
        ledger.register(dossier)

    ledger.path.unlink()
    (tmp_path / "artifacts/research/admission").rmdir()
    (tmp_path / "artifacts/research").rmdir()
    (tmp_path / "artifacts/research").symlink_to(sealed, target_is_directory=True)
    with pytest.raises(CandidateIntakeError, match="symlink"):
        ledger.register(dossier)


def test_parent_and_ledger_fsync_are_called(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real_fsync = admission_module.os.fsync

    def recording_fsync(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(admission_module.os, "fsync", recording_fsync)
    CandidateIntakeLedger(tmp_path).register(_dossier(tmp_path))
    assert len(calls) >= 2


def test_read_only_list_opens_ledger_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = CandidateIntakeLedger(tmp_path)
    ledger.register(_dossier(tmp_path))
    real_open = admission_module.os.open
    ledger_flags: list[int] = []

    def recording_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        if path == "ledger.jsonl":
            ledger_flags.append(flags)
        return real_open(path, flags, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(admission_module.os, "open", recording_open)
    ledger.list_statuses()
    assert ledger_flags
    assert ledger_flags[-1] & os.O_ACCMODE == os.O_RDONLY
    assert not ledger_flags[-1] & os.O_APPEND


def _register_process(root: str, dossier_payload: dict[str, object]) -> None:
    path = Path(root)
    CandidateIntakeLedger(path).register(CandidateDossier.from_mapping(dossier_payload))


def test_multiprocess_registration_has_one_physical_entry(tmp_path: Path) -> None:
    dossier_payload = _dossier(tmp_path).to_dict()
    processes = [
        multiprocessing.Process(
            target=_register_process,
            args=(str(tmp_path), dossier_payload),
        )
        for _ in range(4)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    ledger = CandidateIntakeLedger(tmp_path)
    assert len(ledger.list_statuses()) == 1
    assert len(ledger.path.read_text().splitlines()) == 1
