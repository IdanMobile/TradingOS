import subprocess
from pathlib import Path

import pytest

from tios.ops.self_modification import (
    EVIDENCE_DIR,
    PROPOSALS_FILENAME,
    SelfModificationError,
    changed_paths,
    immutable_violations,
    land_change,
    record_constraint_change_proposal,
    start_change,
)


def _git(root: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=root, capture_output=True, text=True, check=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway git repo whose gate is a stub we can make pass or fail."""
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "orchestrator@test")
    _git(tmp_path, "config", "user.name", "orchestrator")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("VALUE = 1\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "initial")
    return tmp_path


PASSING_GATE = ("true",)
FAILING_GATE = ("false",)


def test_immutable_violations_flags_constraint_files() -> None:
    assert immutable_violations(("src/tios/validation/eligibility.py",))
    assert immutable_violations(("src/tios/validation/trial_budget.py",))
    assert immutable_violations(("src/tios/approval/attestation.py",))
    assert immutable_violations(("src/tios/approval/authority_audit.py",))
    assert immutable_violations(("src/tios/ai_eval/decision_inspector.py",))
    assert immutable_violations(("src/tios/services/reporting/backtest_attribution.py",))
    assert immutable_violations(("src/tios/services/reporting/decision_intelligence.py",))
    assert immutable_violations(("src/tios/trading_domain/decision_intelligence.py",))
    assert immutable_violations(("artifacts/evidence/B2_HISTORICAL_TRADE_TRACES_2026_07_21.jsonl",))
    assert immutable_violations(("artifacts/holdout/2027/returns.parquet",))
    assert not immutable_violations(("src/tios/strategy/momentum.py",))


def test_change_starting_from_dirty_tree_is_refused(repo: Path) -> None:
    (repo / "src" / "app.py").write_text("VALUE = 2\n")
    with pytest.raises(SelfModificationError, match="dirty working tree"):
        start_change(repo, "some-change")


def test_passing_change_lands_and_records_evidence(repo: Path) -> None:
    branch = start_change(repo, "bump-value")
    (repo / "src" / "app.py").write_text("VALUE = 2\n")

    outcome = land_change(repo, rationale="bump value", gate_command=PASSING_GATE)

    assert outcome.landed
    assert outcome.branch == branch
    assert "src/app.py" in outcome.changed_paths
    assert (repo / "src" / "app.py").read_text() == "VALUE = 2\n"
    assert not changed_paths(repo), "tree should be clean after a successful commit"
    evidence = repo / EVIDENCE_DIR / f"{branch.replace('/', '_')}.json"
    assert evidence.is_file()


def test_landed_change_fast_forwards_into_main(repo: Path) -> None:
    """Work must reach main, or the orchestrator's changes strand on dead branches."""
    start_change(repo, "bump-value")
    (repo / "src" / "app.py").write_text("VALUE = 2\n")

    outcome = land_change(repo, rationale="bump value", gate_command=PASSING_GATE)

    assert outcome.landed
    current = subprocess.run(
        ("git", "rev-parse", "--abbrev-ref", "HEAD"),
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert current == "main"
    assert (repo / "src" / "app.py").read_text() == "VALUE = 2\n"


def test_failing_gate_reverts_the_change_entirely(repo: Path) -> None:
    start_change(repo, "bad-change")
    (repo / "src" / "app.py").write_text("VALUE = 999\n")
    (repo / "src" / "extra.py").write_text("junk\n")

    outcome = land_change(repo, rationale="breaks the gate", gate_command=FAILING_GATE)

    assert not outcome.landed
    assert "GATE_FAILED" in outcome.blockers
    # Both the edit and the new file are gone: a red gate never survives.
    assert (repo / "src" / "app.py").read_text() == "VALUE = 1\n"
    assert not (repo / "src" / "extra.py").exists()
    assert not changed_paths(repo)


def test_immutable_edit_is_rejected_even_when_the_gate_would_pass(repo: Path) -> None:
    """A constraint edit that passes the suite is more dangerous, not less."""
    start_change(repo, "weaken-gate")
    target = repo / "src" / "tios" / "validation"
    target.mkdir(parents=True)
    (target / "eligibility.py").write_text("PROMOTION_ELIGIBLE = True\n")

    outcome = land_change(repo, rationale="relax eligibility", gate_command=PASSING_GATE)

    assert not outcome.landed
    assert any("IMMUTABLE_PATH_MODIFIED" in blocker for blocker in outcome.blockers)
    assert not (target / "eligibility.py").exists()


def test_sealed_holdout_cannot_be_rewritten(repo: Path) -> None:
    start_change(repo, "touch-holdout")
    holdout = repo / "artifacts" / "holdout"
    holdout.mkdir(parents=True)
    (holdout / "returns.json").write_text("[]\n")

    outcome = land_change(repo, rationale="adjust holdout", gate_command=PASSING_GATE)

    assert not outcome.landed
    assert any("IMMUTABLE_PATH_MODIFIED" in blocker for blocker in outcome.blockers)


def test_change_without_rationale_is_refused(repo: Path) -> None:
    start_change(repo, "no-rationale")
    (repo / "src" / "app.py").write_text("VALUE = 3\n")
    with pytest.raises(SelfModificationError, match="requires a rationale"):
        land_change(repo, rationale="   ", gate_command=PASSING_GATE)


def test_empty_change_reports_no_changes(repo: Path) -> None:
    start_change(repo, "noop")
    outcome = land_change(repo, rationale="nothing to do", gate_command=PASSING_GATE)
    assert not outcome.landed
    assert "NO_CHANGES" in outcome.blockers


def test_constraint_proposals_are_recorded_not_applied(repo: Path) -> None:
    record_constraint_change_proposal(
        repo,
        path="src/tios/validation/eligibility.py",
        argument="G10 threshold may be too strict for low-frequency families",
    )
    ledger = repo / EVIDENCE_DIR / PROPOSALS_FILENAME
    assert ledger.is_file()
    assert "OPEN_FOR_OPERATOR_REVIEW" in ledger.read_text()
    # The constraint itself is untouched.
    assert not (repo / "src" / "tios" / "validation" / "eligibility.py").exists()
