"""T-010-01 acceptance: lifecycle transition guards + license-class gating."""

import pytest

from tios.services.ingestion import (
    LIFECYCLE,
    AmbiguityRecord,
    LicenseRecord,
    LifecycleError,
    SourceRecord,
    license_gate,
    transition,
)


def test_forward_transitions_walk_the_whole_lifecycle() -> None:
    state = LIFECYCLE[0]
    for target in LIFECYCLE[1:]:
        state = transition(state, target)
    assert state == "VALIDATION_ELIGIBLE"


def test_skipping_a_state_is_rejected() -> None:
    with pytest.raises(LifecycleError):
        transition("DISCOVERED", "SEMANTIC_EXTRACTED")


def test_reordering_is_rejected() -> None:
    with pytest.raises(LifecycleError):
        transition("LICENSE_CHECKED", "SOURCE_CAPTURED")


def test_rejected_reachable_from_any_non_terminal_state() -> None:
    for state in LIFECYCLE[:-1]:
        assert transition(state, "REJECTED") == "REJECTED"


def test_terminal_states_have_no_further_transitions() -> None:
    with pytest.raises(LifecycleError):
        transition("VALIDATION_ELIGIBLE", "REJECTED")
    with pytest.raises(LifecycleError):
        transition("REJECTED", "DISCOVERED")


@pytest.mark.parametrize(
    ("license_class", "code_reuse_allowed", "requires_attribution"),
    [
        ("permissive", True, False),
        ("copyleft", True, True),
        ("proprietary", False, False),
        ("unclear", False, False),
    ],
)
def test_license_gate(
    license_class: str, code_reuse_allowed: bool, requires_attribution: bool
) -> None:
    gate = license_gate(license_class)
    assert gate["code_reuse_allowed"] is code_reuse_allowed
    assert gate["requires_attribution"] is requires_attribution
    assert gate["spec_extraction_allowed"] is True  # description-based extraction never blocked


def test_license_gate_rejects_unknown_class() -> None:
    with pytest.raises(ValueError):
        license_gate("public_domain_unlisted")


def test_source_record_rejects_inherited_profit_claims() -> None:
    with pytest.raises(ValueError):
        SourceRecord(
            source_id="SRC-X",
            source_class="official_framework",
            url="https://example.invalid",
            title="t",
            author="a",
            published_at="2020-01-01",
            retrieved_at="2026-07-07",
            license="MIT",
            version_or_commit="v1",
            market_claimed="crypto",
            timeframe_claimed="1h",
            profit_claims_inherited=True,
        )


def test_ambiguity_record_requires_content_or_justification() -> None:
    with pytest.raises(ValueError):
        AmbiguityRecord(source_id="SRC-X", ambiguities=())
    # non-empty list is fine
    AmbiguityRecord(source_id="SRC-X", ambiguities=("tie-break on same-bar signals",))
    # explicit justification for an empty list is fine
    AmbiguityRecord(
        source_id="SRC-X",
        ambiguities=(),
        justification_if_empty="fully specified by config schema",
    )


def test_license_record_rejects_unknown_class() -> None:
    with pytest.raises(ValueError):
        LicenseRecord(
            source_id="SRC-X",
            license_class="not_a_class",
            license_name="?",
            evidence_url="https://example.invalid",
        )
