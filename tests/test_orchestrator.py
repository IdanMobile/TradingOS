import json
from pathlib import Path

from tios.ops.driver import park
from tios.ops.orchestrator import (
    ACT,
    ESCALATE,
    INFO,
    PROSPECTIVE_MARKER_NAME,
    REPORT_DIR,
    SITUATION_FILENAME,
    journal,
    observe,
    observe_constraint_integrity,
    observe_evidence_freshness,
    observe_execution_envelope,
    observe_prospective_observers,
    observe_statistical_health,
    run_cycle,
)
from tios.ops.self_modification import IMMUTABLE_PATHS
from tios.validation.splits import ACCESS_LOG


def _constraints_present(root: Path) -> None:
    """Materialise every immutable constraint file so integrity checks pass."""
    for path in IMMUTABLE_PATHS:
        if path.endswith("OPERATOR_ATTESTATION.json"):
            continue
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")


def test_missing_constraint_file_escalates(tmp_path: Path) -> None:
    """A missing constraint is indistinguishable from a disabled one."""
    observations = observe_constraint_integrity(tmp_path)
    assert observations[0].severity == ESCALATE
    assert "missing" in observations[0].summary


def test_present_constraints_report_info(tmp_path: Path) -> None:
    _constraints_present(tmp_path)
    observations = observe_constraint_integrity(tmp_path)
    assert observations[0].severity == INFO


def test_second_holdout_access_escalates(tmp_path: Path) -> None:
    """The most damaging thing that can happen to this project's evidence."""
    log = tmp_path / ACCESS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps({"reason": "first", "opened_at": "2027-01-15T00:00:00+00:00", "holdout_rows": 5})
        + "\n"
        + json.dumps(
            {"reason": "peeking again", "opened_at": "2027-01-16T00:00:00+00:00", "holdout_rows": 5}
        )
        + "\n",
        encoding="utf-8",
    )

    observations = observe_statistical_health(tmp_path)
    escalations = [item for item in observations if item.severity == ESCALATE]

    assert escalations
    assert "compromised" in escalations[0].summary


def test_single_holdout_access_is_fine(tmp_path: Path) -> None:
    log = tmp_path / ACCESS_LOG
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps({"reason": "final", "opened_at": "2027-01-15T00:00:00+00:00", "holdout_rows": 5})
        + "\n",
        encoding="utf-8",
    )
    assert all(item.severity != ESCALATE for item in observe_statistical_health(tmp_path))


def test_stale_artifacts_raise_an_action(tmp_path: Path) -> None:
    from tios.evidence.provenance import ARTIFACT_SCHEMA

    module = tmp_path / "src" / "engine.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text("VALUE = 1\n", encoding="utf-8")

    artifact = tmp_path / "artifacts" / "a.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(
            {
                "artifact_schema": ARTIFACT_SCHEMA,
                "artifact_id": "ART-STALE",
                "code": {"module_sha256_by_path": {"src/engine.py": "0" * 64}},
            }
        ),
        encoding="utf-8",
    )

    observations = observe_evidence_freshness(tmp_path)
    actions = [item for item in observations if item.severity == ACT]

    assert actions
    assert "ART-STALE" in actions[0].detail["refs"]


def test_absent_attestation_is_informational_not_an_error(tmp_path: Path) -> None:
    """Offline research is a normal state and must not raise noise every cycle."""
    observations = observe_execution_envelope(tmp_path)
    assert observations[0].severity == INFO
    assert "offline research only" in observations[0].summary
    assert "no capital-bearing stage" in observations[0].summary


def test_malformed_attestation_escalates(tmp_path: Path) -> None:
    from tios.approval.attestation import DEFAULT_PATH, template

    target = tmp_path / DEFAULT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(template()), encoding="utf-8")

    observations = observe_execution_envelope(tmp_path)

    assert observations[0].severity == ESCALATE
    assert "unreadable" in observations[0].summary


def test_parked_items_are_surfaced(tmp_path: Path) -> None:
    park(tmp_path, item="unrecoverable data", cause="bytes never retained")
    situation = observe(tmp_path)
    parked = [item for item in situation.observations if item.domain == "parked"]
    assert parked
    assert "unrecoverable data" in parked[0].detail["items"]


def test_cycle_persists_situation_and_journal(tmp_path: Path) -> None:
    _constraints_present(tmp_path)

    run_cycle(tmp_path)
    run_cycle(tmp_path)

    situation_file = tmp_path / REPORT_DIR / SITUATION_FILENAME
    assert situation_file.is_file()
    payload = json.loads(situation_file.read_text())
    assert payload["schema_version"] == 1

    entries = journal(tmp_path)
    assert len(entries) == 2, "the journal is append-only across cycles"


def test_situation_halts_when_anything_escalates(tmp_path: Path) -> None:
    """No constraint files present, so integrity escalates and the loop must stop."""
    situation = observe(tmp_path)
    assert situation.halted
    assert situation.escalations


def test_clean_project_does_not_halt(tmp_path: Path) -> None:
    _constraints_present(tmp_path)
    situation = observe(tmp_path)
    assert not situation.halted, [item.summary for item in situation.escalations]


def _fake_observer_script(tmp_path: Path, *, name: str, exit_code: int, counter: Path) -> Path:
    """A tiny script that records each invocation and exits with a fixed code."""
    script = tmp_path / name
    script.write_text(
        "from pathlib import Path\n"
        f"Path({str(counter)!r}).open('a', encoding='utf-8').write('x\\n')\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    return script


def test_successful_observer_emits_info_and_writes_marker(tmp_path: Path) -> None:
    counter = tmp_path / "calls.count"
    script = _fake_observer_script(tmp_path, name="ok_observer.py", exit_code=0, counter=counter)
    observers = (("TEST-LANE", script.relative_to(tmp_path)),)

    observations = observe_prospective_observers(tmp_path, observers)

    assert len(observations) == 1
    assert observations[0].severity == INFO
    assert observations[0].domain == "prospective_observation"
    assert counter.read_text().count("x") == 1
    marker = tmp_path / "artifacts" / "prospective" / "TEST-LANE" / PROSPECTIVE_MARKER_NAME
    assert marker.is_file()


def test_second_same_day_call_does_not_rerun(tmp_path: Path) -> None:
    counter = tmp_path / "calls.count"
    script = _fake_observer_script(tmp_path, name="ok_observer.py", exit_code=0, counter=counter)
    observers = (("TEST-LANE", script.relative_to(tmp_path)),)

    first = observe_prospective_observers(tmp_path, observers)
    second = observe_prospective_observers(tmp_path, observers)

    assert len(first) == 1
    assert second == (), "the per-day marker guard must skip a second same-day run"
    assert counter.read_text().count("x") == 1, "script must not run twice in one UTC day"


def test_failing_observer_emits_act_and_does_not_halt(tmp_path: Path) -> None:
    counter = tmp_path / "calls.count"
    script = _fake_observer_script(tmp_path, name="bad_observer.py", exit_code=1, counter=counter)
    observers = (("TEST-LANE", script.relative_to(tmp_path)),)

    observations = observe_prospective_observers(tmp_path, observers)

    assert len(observations) == 1
    assert observations[0].severity == ACT
    assert observations[0].detail["returncode"] == 1
    assert observations[0].severity != ESCALATE


def test_missing_observer_script_emits_act(tmp_path: Path) -> None:
    observers = (("TEST-LANE", Path("scripts/does_not_exist_observer.py")),)

    observations = observe_prospective_observers(tmp_path, observers)

    assert len(observations) == 1
    assert observations[0].severity == ACT
    assert "missing" in observations[0].summary
    marker = tmp_path / "artifacts" / "prospective" / "TEST-LANE" / PROSPECTIVE_MARKER_NAME
    assert not marker.exists(), "a missing script made no API call, so no guard is needed"


def test_prospective_observer_failure_does_not_halt_full_cycle(tmp_path: Path) -> None:
    _constraints_present(tmp_path)
    counter = tmp_path / "calls.count"
    script = _fake_observer_script(tmp_path, name="bad_observer.py", exit_code=1, counter=counter)
    observers = (("TEST-LANE", script.relative_to(tmp_path)),)

    situation = observe(tmp_path, prospective_observers=observers)

    assert not situation.halted
    acts = [item for item in situation.actions if item.domain == "prospective_observation"]
    assert acts
