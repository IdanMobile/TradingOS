from pathlib import Path

import pytest

from tios.validation.trial_budget import (
    TrialBudgetError,
    effective_trials_for_family,
    effective_trials_hierarchy_wide,
    families,
    family_count,
    global_trial_count,
    preregister,
    record_trial,
    registration,
    trial_count,
    verify_declared_trials,
)

FAMILY = {
    "family": "FAM-CALENDAR-UTC-01",
    "search_space": {"weekday": [0, 1, 2, 3, 4, 5, 6]},
    "primary_endpoint": "per_bar_sharpe",
    "cost_model": "six_cell_stress_v1",
    "chronology": "2020-01-01/2026-07-13",
    "thresholds": {"pbo_max": 0.5, "dsr_min": 0.95},
    "stop_rules": "no_rescue_on_fail",
}


def _register(root: Path, **overrides: object) -> str:
    return preregister(root, **{**FAMILY, **overrides})


def test_preregistration_is_idempotent_and_retrievable(tmp_path: Path) -> None:
    first = _register(tmp_path)
    second = _register(tmp_path)
    assert first == second
    record = registration(tmp_path, first)
    assert record is not None
    assert record["family"] == "FAM-CALENDAR-UTC-01"
    assert record["primary_endpoint"] == "per_bar_sharpe"


def test_amended_search_space_is_a_new_family(tmp_path: Path) -> None:
    original = _register(tmp_path)
    widened = _register(tmp_path, search_space={"weekday": list(range(7)), "hour": [0, 12]})
    assert original != widened
    # The widened search must not inherit the original's budget.
    record_trial(tmp_path, original, "trial-a")
    assert trial_count(tmp_path, widened) == 0


def test_missing_registration_fields_are_rejected(tmp_path: Path) -> None:
    incomplete = {name: value for name, value in FAMILY.items() if name != "stop_rules"}
    with pytest.raises(TrialBudgetError, match="missing required fields"):
        preregister(tmp_path, **incomplete)


def test_unregistered_search_cannot_record_trials(tmp_path: Path) -> None:
    with pytest.raises(TrialBudgetError, match="unregistered family"):
        record_trial(tmp_path, "PREREG-does-not-exist", "trial-a")


def test_trials_accumulate_and_reruns_do_not_inflate_the_budget(tmp_path: Path) -> None:
    ref = _register(tmp_path)
    assert record_trial(tmp_path, ref, "trial-a") == 1
    assert record_trial(tmp_path, ref, "trial-b") == 2
    # A crash-and-retry of an identical trial is not an additional search.
    assert record_trial(tmp_path, ref, "trial-a") == 2


def test_global_count_spans_families(tmp_path: Path) -> None:
    first = _register(tmp_path)
    second = _register(tmp_path, family="FAM-OTHER-02")
    record_trial(tmp_path, first, "trial-a")
    record_trial(tmp_path, second, "trial-a")
    record_trial(tmp_path, second, "trial-b")
    assert global_trial_count(tmp_path) == 3


def test_declared_count_matching_the_ledger_verifies(tmp_path: Path) -> None:
    ref = _register(tmp_path)
    record_trial(tmp_path, ref, "trial-a")
    record_trial(tmp_path, ref, "trial-b")
    verdict = verify_declared_trials(tmp_path, ref, 2)
    assert verdict.verified
    assert verdict.blockers == ()


def test_understated_declaration_is_blocked(tmp_path: Path) -> None:
    """The core defence: searching wide and declaring narrow."""
    ref = _register(tmp_path)
    for index in range(50):
        record_trial(tmp_path, ref, f"trial-{index}")
    verdict = verify_declared_trials(tmp_path, ref, 3)
    assert not verdict.verified
    assert "DECLARED_TRIAL_COUNT_UNDERSTATES_LEDGER" in verdict.blockers
    assert verdict.ledger_trial_count == 50


def test_overstated_declaration_is_blocked(tmp_path: Path) -> None:
    ref = _register(tmp_path)
    record_trial(tmp_path, ref, "trial-a")
    verdict = verify_declared_trials(tmp_path, ref, 9)
    assert not verdict.verified
    assert "DECLARED_TRIAL_COUNT_EXCEEDS_LEDGER" in verdict.blockers


def test_unknown_and_missing_registrations_fail_closed(tmp_path: Path) -> None:
    unknown = verify_declared_trials(tmp_path, "PREREG-nope", 0)
    assert not unknown.verified
    assert "PREREGISTRATION_NOT_FOUND" in unknown.blockers

    missing = verify_declared_trials(tmp_path, "", 0)
    assert not missing.verified
    assert "PREREGISTRATION_REF_MISSING" in missing.blockers


def test_boolean_declared_count_is_invalid(tmp_path: Path) -> None:
    ref = _register(tmp_path)
    verdict = verify_declared_trials(tmp_path, ref, True)  # noqa: FBT003
    assert not verdict.verified
    assert "DECLARED_TRIAL_COUNT_INVALID" in verdict.blockers


def test_effective_trials_deflate_against_the_whole_search(tmp_path: Path) -> None:
    ref = _register(tmp_path)
    for index in range(100):
        record_trial(tmp_path, ref, f"trial-{index}")
    # Uncorrelated trials imply the full population; perfect correlation implies one.
    assert effective_trials_for_family(tmp_path, ref, 0.0) == pytest.approx(100.0)
    assert effective_trials_for_family(tmp_path, ref, 1.0) == pytest.approx(1.0)


def test_effective_trials_refuse_an_empty_ledger(tmp_path: Path) -> None:
    ref = _register(tmp_path)
    with pytest.raises(TrialBudgetError, match="empty ledger"):
        effective_trials_for_family(tmp_path, ref, 0.5)


def test_family_count_tracks_admissions(tmp_path: Path) -> None:
    """Families are themselves a search; an uncounted outer search is invisible."""
    assert family_count(tmp_path) == 0
    _register(tmp_path)
    assert family_count(tmp_path) == 1
    _register(tmp_path)  # idempotent
    assert family_count(tmp_path) == 1
    _register(tmp_path, family="FAM-OTHER", search_space={"weekday": [0]})
    assert family_count(tmp_path) == 2
    assert len(families(tmp_path)) == 2


def test_hierarchy_deflation_counts_every_family(tmp_path: Path) -> None:
    first = _register(tmp_path)
    second = _register(tmp_path, family="FAM-SECOND", search_space={"weekday": [1]})
    for index in range(10):
        record_trial(tmp_path, first, f"a-{index}")
    for index in range(10):
        record_trial(tmp_path, second, f"b-{index}")

    per_family = effective_trials_for_family(tmp_path, first, 0.0)
    hierarchy = effective_trials_hierarchy_wide(tmp_path, 0.0)

    assert per_family == pytest.approx(10.0)
    assert hierarchy == pytest.approx(20.0), "both families' searches must count"


def test_hierarchy_deflation_refuses_an_empty_ledger(tmp_path: Path) -> None:
    _register(tmp_path)
    with pytest.raises(TrialBudgetError, match="empty ledger"):
        effective_trials_hierarchy_wide(tmp_path, 0.5)
