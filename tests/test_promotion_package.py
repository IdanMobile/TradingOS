from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import MappingProxyType

import pytest

from tios.validation.eligibility import REQUIRED_DIMENSIONS, MetricEvidence, ScorecardEvidence
from tios.validation.promotion_package import (
    GateEvidenceRecord,
    PromotionPackage,
    PromotionPackageError,
    build_promotion_package,
    revalidate_promotion_package,
)
from tios.validation.trial_budget import BudgetVerdict, preregister, record_trial


def _ledger(root: Path) -> str:
    ref = preregister(
        root,
        family="FAM-PROMOTION-PACKAGE-01",
        search_space={"parameter": [1, 2]},
        primary_endpoint="after_cost_return",
        cost_model="synthetic-cost-v1",
        chronology="synthetic-only",
        thresholds={"minimum": 1},
        stop_rules="no_rescue",
    )
    record_trial(root, ref, "trial-1")
    record_trial(root, ref, "trial-2")
    return ref


def _scorecard(registration_ref: str) -> ScorecardEvidence:
    return ScorecardEvidence(
        strategy_version_ref="SV-SYNTHETIC-1",
        context_ref="CTX-SYNTHETIC",
        dataset_ref="DS-SYNTHETIC",
        preregistration_ref=registration_ref,
        declared_trial_count=2,
        terminal_trial_count=2,
        causal_evidence_refs=("evidence:causal",),
        benchmark_ref="evidence:benchmark",
        after_cost_return_ref="evidence:returns",
        environment_ref="environment:synthetic",
        engine_version="engine:synthetic-1",
        dimension_statuses={dimension: "PASS" for dimension in REQUIRED_DIMENSIONS},
        dimension_blockers={},
    )


def _metrics() -> tuple[MetricEvidence, ...]:
    return (MetricEvidence("DSR", True, True, 2, 2, ("evidence:dsr",)),)


def _gates() -> tuple[GateEvidenceRecord, ...]:
    return tuple(
        GateEvidenceRecord(
            gate=f"G{number}",
            status="PASS",
            hard_fail=False,
            evidence_refs=(f"evidence:G{number}",),
            blockers=(),
        )
        for number in range(1, 12)
    )


def _build(root: Path, **overrides: object):  # type: ignore[no-untyped-def]
    ref = _ledger(root)
    values = {
        "ledger_root": root,
        "metrics": _metrics(),
        "scorecard": _scorecard(ref),
        "gate_evidence": _gates(),
        "validation_status": "COMPLETE_APPROVABLE",
        "live_orders_enabled": False,
    }
    values.update(overrides)
    return build_promotion_package(**values)  # type: ignore[arg-type]


def test_perfect_claimed_evidence_remains_blocked_pending_resolution(tmp_path: Path) -> None:
    package = _build(tmp_path)

    assert package.status == "ASSEMBLED_PENDING_EVIDENCE_RESOLUTION"
    assert package.blockers == ("EVIDENCE_REFS_UNRESOLVED",)
    assert package.execution_authority == "NONE"
    assert not package.eligibility.promotion_eligible
    assert set(package.eligibility.promotion_blockers) == {
        "INDEPENDENT_REVIEWS_NOT_ALL_PASS",
        "INDEPENDENT_REVIEW_EVIDENCE_INCOMPLETE",
    }
    assert tuple(request.review_role for request in package.review_requests) == (
        "STATISTICAL",
        "RISK",
        "SUPERVISOR",
        "SECURITY",
    )
    assert all(
        request.status == "BLOCKED_EVIDENCE_RESOLUTION" for request in package.review_requests
    )
    assert all(
        request.blockers == ("EVIDENCE_REFS_UNRESOLVED",) for request in package.review_requests
    )
    assert all(request.execution_authority == "NONE" for request in package.review_requests)
    assert all(
        request.subject_digest == package.package_digest for request in package.review_requests
    )
    assert tuple(request.request_id for request in package.review_requests) == tuple(
        f"IRR-{role}-{package.package_digest}"
        for role in ("STATISTICAL", "RISK", "SUPERVISOR", "SECURITY")
    )


def test_missing_gate_is_explicit_not_run_and_blocks(tmp_path: Path) -> None:
    package = _build(tmp_path, gate_evidence=_gates()[:-1])

    g11 = package.gates[-1]
    assert (g11.gate, g11.status) == ("G11", "NOT_RUN")
    assert g11.blockers == ("MISSING_GATE_EVIDENCE",)
    assert "G11:MISSING_GATE_EVIDENCE" in package.blockers
    assert package.status == "NOT_ELIGIBLE"
    assert all(
        request.status == "BLOCKED_EVIDENCE_RESOLUTION" for request in package.review_requests
    )


def test_missing_metrics_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(PromotionPackageError, match="non-empty"):
        _build(tmp_path, metrics=())


def test_unknown_and_duplicate_gates_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(PromotionPackageError, match="unknown gate"):
        GateEvidenceRecord("G12", "FAIL", False, (), ("UNKNOWN",))

    duplicate = (*_gates(), _gates()[0])
    with pytest.raises(PromotionPackageError, match="duplicate gate"):
        _build(tmp_path, gate_evidence=duplicate)


def test_hard_fail_is_preserved_and_cannot_be_overridden(tmp_path: Path) -> None:
    failed = replace(
        _gates()[4],
        status="FAIL",
        hard_fail=True,
        evidence_refs=("evidence:G5-hard-fail",),
        blockers=("NEGATIVE_AFTER_COSTS",),
    )
    package = _build(tmp_path, gate_evidence=(*_gates()[:4], failed, *_gates()[5:]))

    assert package.gates[4].hard_fail
    assert "VALIDATION_HARD_FAIL" in package.blockers
    assert "G5:NEGATIVE_AFTER_COSTS" in package.blockers
    assert package.status == "NOT_ELIGIBLE"


def test_live_order_capability_always_blocks(tmp_path: Path) -> None:
    package = _build(tmp_path, live_orders_enabled=True)

    assert "LIVE_ORDER_CAPABILITY_PRESENT" in package.blockers
    assert package.status == "NOT_ELIGIBLE"
    assert package.execution_authority == "NONE"


def test_trial_count_is_verified_against_the_supplied_ledger(tmp_path: Path) -> None:
    ref = _ledger(tmp_path)
    understated = replace(_scorecard(ref), declared_trial_count=1, terminal_trial_count=1)
    package = build_promotion_package(
        ledger_root=tmp_path,
        metrics=_metrics(),
        scorecard=understated,
        gate_evidence=_gates(),
        validation_status="COMPLETE_APPROVABLE",
        live_orders_enabled=False,
    )

    assert not package.budget_verdict.verified
    assert "DECLARED_TRIAL_COUNT_UNDERSTATES_LEDGER" in package.blockers
    assert package.status == "NOT_ELIGIBLE"


def test_missing_score_dimension_is_retained_as_not_run(tmp_path: Path) -> None:
    ref = _ledger(tmp_path)
    scorecard = _scorecard(ref)
    missing = sorted(REQUIRED_DIMENSIONS)[0]
    statuses = dict(scorecard.dimension_statuses)
    statuses.pop(missing)
    package = build_promotion_package(
        ledger_root=tmp_path,
        metrics=_metrics(),
        scorecard=replace(scorecard, dimension_statuses=statuses),
        gate_evidence=_gates(),
        validation_status="COMPLETE_APPROVABLE",
        live_orders_enabled=False,
    )

    assert package.scorecard.dimension_statuses[missing] == "NOT_RUN"
    assert package.scorecard.dimension_blockers[missing] == ("MISSING_DIMENSION_EVIDENCE",)
    assert f"DIMENSION_{missing}:NOT_RUN" in package.blockers


def test_package_identity_is_deterministic_and_material_sensitive(tmp_path: Path) -> None:
    ref = _ledger(tmp_path)
    arguments = {
        "ledger_root": tmp_path,
        "metrics": _metrics(),
        "scorecard": _scorecard(ref),
        "gate_evidence": _gates(),
        "validation_status": "COMPLETE_APPROVABLE",
        "live_orders_enabled": False,
    }
    first = build_promotion_package(**arguments)
    second = build_promotion_package(**arguments)
    changed_gate = replace(_gates()[0], evidence_refs=("evidence:G1-alternate",))
    changed = build_promotion_package(
        **{**arguments, "gate_evidence": (changed_gate, *_gates()[1:])}
    )

    assert first.package_id == second.package_id
    assert first.package_digest == second.package_digest
    assert first.package_digest != changed.package_digest
    assert first.evidence_digest != changed.evidence_digest


def test_public_types_are_frozen_and_expose_no_approval_record(tmp_path: Path) -> None:
    package = _build(tmp_path)
    with pytest.raises(FrozenInstanceError):
        package.status = "APPROVED"  # type: ignore[misc]

    payload = package.as_dict()
    assert "human_decision" not in str(payload).lower()
    assert "gated_approval" not in str(payload).lower()
    assert all(request["execution_authority"] == "NONE" for request in payload["review_requests"])


def test_current_trial_ledger_must_be_revalidated_and_later_trial_invalidates(
    tmp_path: Path,
) -> None:
    package = _build(tmp_path)
    fresh = revalidate_promotion_package(tmp_path, package)
    assert fresh.valid and fresh.blockers == ()

    record_trial(tmp_path, package.scorecard.preregistration_ref, "trial-3")
    stale = revalidate_promotion_package(tmp_path, package)
    assert not stale.valid
    assert stale.blockers == (
        "TRIAL_BUDGET_VERDICT_STALE",
        "TRIAL_LEDGER_CHECKPOINT_STALE",
    )
    assert stale.current_checkpoint_digest != stale.retained_checkpoint_digest


def test_replace_and_direct_constructor_cannot_forge_semantics(tmp_path: Path) -> None:
    package = _build(tmp_path)
    with pytest.raises(PromotionPackageError, match="exactly derived"):
        replace(package, status="NOT_ELIGIBLE")

    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    constructor["blockers"] = ("EVIDENCE_REFS_UNRESOLVED", "FORGED")
    with pytest.raises(PromotionPackageError, match="exactly derived"):
        PromotionPackage(**constructor)


def test_direct_constructor_rejects_mutable_scorecard_mappings(tmp_path: Path) -> None:
    package = _build(tmp_path)
    mutable_statuses = dict(package.scorecard.dimension_statuses)
    mutable_blockers = dict(package.scorecard.dimension_blockers)
    mutable_scorecard = replace(
        package.scorecard,
        dimension_statuses=mutable_statuses,
        dimension_blockers=mutable_blockers,
    )
    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    constructor["scorecard"] = mutable_scorecard

    with pytest.raises(PromotionPackageError, match="immutable mappingproxy"):
        PromotionPackage(**constructor)
    mutable_statuses[next(iter(mutable_statuses))] = "FAIL"
    assert all(status == "PASS" for status in package.scorecard.dimension_statuses.values())


def test_direct_constructor_detaches_external_mappingproxy_backing_dicts(
    tmp_path: Path,
) -> None:
    package = _build(tmp_path)
    status_backing = dict(package.scorecard.dimension_statuses)
    blocker_backing = dict(package.scorecard.dimension_blockers)
    externally_backed = replace(
        package.scorecard,
        dimension_statuses=MappingProxyType(status_backing),
        dimension_blockers=MappingProxyType(blocker_backing),
    )
    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    constructor["scorecard"] = externally_backed
    detached = PromotionPackage(**constructor)
    retained = detached.as_dict()

    dimension = next(iter(status_backing))
    status_backing[dimension] = "FAIL"
    blocker_backing[dimension] = ("external mutation",)
    assert detached.as_dict() == retained
    assert detached.scorecard.dimension_statuses[dimension] == "PASS"
    assert dimension not in detached.scorecard.dimension_blockers


def test_direct_constructor_malformed_nested_types_raise_package_error(
    tmp_path: Path,
) -> None:
    package = _build(tmp_path)
    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    for field_name in (
        "scorecard",
        "gates",
        "metrics",
        "budget_verdict",
        "trial_ledger_checkpoint",
        "eligibility",
        "review_requests",
    ):
        malformed = dict(constructor)
        malformed[field_name] = None
        with pytest.raises(PromotionPackageError):
            PromotionPackage(**malformed)


def test_budget_verdict_is_detached_from_external_blocker_list(tmp_path: Path) -> None:
    package = _build(tmp_path)
    external_blockers: list[str] = []
    externally_backed = BudgetVerdict(
        verified=True,
        registration_ref=package.budget_verdict.registration_ref,
        declared_trial_count=package.budget_verdict.declared_trial_count,
        ledger_trial_count=package.budget_verdict.ledger_trial_count,
        blockers=external_blockers,  # type: ignore[arg-type]
    )
    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    constructor["budget_verdict"] = externally_backed
    detached = PromotionPackage(**constructor)
    retained = detached.as_dict()

    external_blockers.append("FORGED_AFTER_CONSTRUCTION")
    assert detached.as_dict() == retained
    assert detached.budget_verdict.blockers == ()


def test_budget_verdict_rejects_bool_aliases_for_verified_and_counts(tmp_path: Path) -> None:
    package = _build(tmp_path)
    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    valid = package.budget_verdict

    forged_verified = BudgetVerdict(
        verified=1,  # type: ignore[arg-type]
        registration_ref=valid.registration_ref,
        declared_trial_count=valid.declared_trial_count,
        ledger_trial_count=valid.ledger_trial_count,
        blockers=(),
    )
    with pytest.raises(PromotionPackageError, match="verified must be an exact bool"):
        PromotionPackage(**{**constructor, "budget_verdict": forged_verified})

    for field_name in ("declared_trial_count", "ledger_trial_count"):
        counts = {
            "declared_trial_count": valid.declared_trial_count,
            "ledger_trial_count": valid.ledger_trial_count,
        }
        counts[field_name] = True
        bool_count = BudgetVerdict(
            verified=True,
            registration_ref=valid.registration_ref,
            declared_trial_count=counts["declared_trial_count"],
            ledger_trial_count=counts["ledger_trial_count"],
            blockers=(),
        )
        with pytest.raises(PromotionPackageError, match="non-negative exact int"):
            PromotionPackage(**{**constructor, "budget_verdict": bool_count})


def test_budget_verdict_rejects_string_blockers_aliases_and_count_conflicts(
    tmp_path: Path,
) -> None:
    package = _build(tmp_path)
    constructor = {field.name: getattr(package, field.name) for field in fields(package)}
    valid = package.budget_verdict

    for blockers, message in (
        ("BLOCKER", "non-string sequence"),
        (["BLOCKER", "blocker"], "duplicates or aliases"),
    ):
        malformed = BudgetVerdict(
            verified=False,
            registration_ref=valid.registration_ref,
            declared_trial_count=valid.declared_trial_count,
            ledger_trial_count=valid.ledger_trial_count,
            blockers=blockers,  # type: ignore[arg-type]
        )
        with pytest.raises(PromotionPackageError, match=message):
            PromotionPackage(**{**constructor, "budget_verdict": malformed})

    missing_relationship_blocker = BudgetVerdict(
        verified=False,
        registration_ref=valid.registration_ref,
        declared_trial_count=valid.declared_trial_count - 1,
        ledger_trial_count=valid.ledger_trial_count,
        blockers=("SOME_OTHER_BLOCKER",),
    )
    with pytest.raises(PromotionPackageError, match="understated budget count"):
        PromotionPackage(**{**constructor, "budget_verdict": missing_relationship_blocker})


def test_request_id_or_status_cannot_be_forged(tmp_path: Path) -> None:
    package = _build(tmp_path)
    forged = replace(package.review_requests[0], request_id="IRR-forged")
    with pytest.raises(PromotionPackageError, match="exact package-derived"):
        replace(package, review_requests=(forged, *package.review_requests[1:]))

    with pytest.raises(PromotionPackageError, match="invalid review request status"):
        replace(package.review_requests[0], status="PENDING")


def test_scorecard_maps_are_copied_and_deep_frozen(tmp_path: Path) -> None:
    ref = _ledger(tmp_path)
    statuses = {dimension: "PASS" for dimension in REQUIRED_DIMENSIONS}
    dimension_blockers: dict[str, tuple[str, ...]] = {}
    scorecard = replace(
        _scorecard(ref),
        dimension_statuses=statuses,
        dimension_blockers=dimension_blockers,
    )
    package = build_promotion_package(
        ledger_root=tmp_path,
        metrics=_metrics(),
        scorecard=scorecard,
        gate_evidence=_gates(),
        validation_status="COMPLETE_APPROVABLE",
        live_orders_enabled=False,
    )
    retained = package.as_dict()
    digest = package.package_digest

    statuses[next(iter(statuses))] = "FAIL"
    dimension_blockers[next(iter(statuses))] = ("mutated",)
    assert package.as_dict() == retained
    assert package.package_digest == digest
    with pytest.raises(TypeError):
        package.scorecard.dimension_statuses[next(iter(statuses))] = "FAIL"  # type: ignore[index]


def test_metric_and_scorecard_aliases_or_noncanonical_refs_are_rejected(tmp_path: Path) -> None:
    alias_metrics = (
        MetricEvidence("DSR", True, True, 2, 2, ("evidence:a",)),
        MetricEvidence("D-S-R", True, True, 2, 2, ("evidence:b",)),
    )
    with pytest.raises(PromotionPackageError, match="duplicate or alias"):
        _build(tmp_path, metrics=alias_metrics)

    with pytest.raises(PromotionPackageError, match="canonical text"):
        _build(tmp_path, metrics=(replace(_metrics()[0], name=" DSR"),))
    with pytest.raises(PromotionPackageError, match="invalid text"):
        _build(
            tmp_path,
            metrics=(replace(_metrics()[0], evidence_refs=(" evidence:dsr",)),),
        )

    ref = _ledger(tmp_path)
    with pytest.raises(PromotionPackageError, match="canonical text"):
        build_promotion_package(
            ledger_root=tmp_path,
            metrics=_metrics(),
            scorecard=replace(_scorecard(ref), dataset_ref=" DS-SYNTHETIC"),
            gate_evidence=_gates(),
            validation_status="COMPLETE_APPROVABLE",
            live_orders_enabled=False,
        )


def test_malformed_scorecard_inputs_raise_package_errors(tmp_path: Path) -> None:
    with pytest.raises(PromotionPackageError, match="scorecard must be ScorecardEvidence"):
        build_promotion_package(
            ledger_root=tmp_path,
            metrics=_metrics(),
            scorecard=None,  # type: ignore[arg-type]
            gate_evidence=_gates(),
            validation_status="COMPLETE_APPROVABLE",
            live_orders_enabled=False,
        )

    ref = _ledger(tmp_path)
    dimension = sorted(REQUIRED_DIMENSIONS)[0]
    for malformed in ("not-a-tuple", ["not-a-tuple"]):
        with pytest.raises(PromotionPackageError, match="must be an exact tuple"):
            build_promotion_package(
                ledger_root=tmp_path,
                metrics=_metrics(),
                scorecard=replace(
                    _scorecard(ref),
                    dimension_statuses={
                        **_scorecard(ref).dimension_statuses,
                        dimension: "FAIL",
                    },
                    dimension_blockers={dimension: malformed},  # type: ignore[dict-item]
                ),
                gate_evidence=_gates(),
                validation_status="COMPLETE_APPROVABLE",
                live_orders_enabled=False,
            )

    with pytest.raises(PromotionPackageError, match="must be mappings"):
        build_promotion_package(
            ledger_root=tmp_path,
            metrics=_metrics(),
            scorecard=replace(
                _scorecard(ref),
                dimension_statuses=[],  # type: ignore[arg-type]
            ),
            gate_evidence=_gates(),
            validation_status="COMPLETE_APPROVABLE",
            live_orders_enabled=False,
        )
    with pytest.raises(PromotionPackageError, match="duplicates or aliases"):
        build_promotion_package(
            ledger_root=tmp_path,
            metrics=_metrics(),
            scorecard=replace(_scorecard(ref), context_ref="DS-SYNTHETIC"),
            gate_evidence=_gates(),
            validation_status="COMPLETE_APPROVABLE",
            live_orders_enabled=False,
        )
