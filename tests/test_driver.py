import json
from pathlib import Path

import pytest
import yaml

from tios.ops.driver import (
    REPORT_DIR,
    DriverError,
    dispatchable,
    load_map,
    park,
    parked_items,
    run_cycle,
)

MAP = {
    "schema_version": 1,
    "map_id": "TEST-MAP-V1",
    "subject_ref": "TEST-SUBJECT",
    "semantic_boundaries": {"warmup_analysis": "ALLOWED"},
    "blockers": [
        {
            "code": "PASSING_BLOCKER",
            "producer": "scripts/produce.py",
            "verifier": "scripts/pass_verifier.py",
            "release_condition": "the thing is done",
            "earliest": "now",
            "contributes_to": ["G1"],
        },
        {
            "code": "FAILING_BLOCKER",
            "producer": "scripts/produce.py",
            "verifier": "scripts/fail_verifier.py",
            "release_condition": "the other thing is done",
            "earliest": "now",
            "contributes_to": ["G2"],
        },
        {
            "code": "FUTURE_BLOCKER",
            "producer": "future campaign",
            "verifier": "future independent statistical reproduction",
            "release_condition": "someday",
            "earliest": "later",
            "contributes_to": ["G10"],
        },
    ],
}


@pytest.fixture
def project(tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "pass_verifier.py").write_text("raise SystemExit(0)\n")
    (scripts / "fail_verifier.py").write_text(
        "import sys; print('condition not met', file=sys.stderr); raise SystemExit(1)\n"
    )
    (tmp_path / "map.yaml").write_text(yaml.safe_dump(MAP), encoding="utf-8")
    return tmp_path


def test_dispatchable_accepts_project_scripts() -> None:
    argv = dispatchable("scripts/run_prospective_observation_flow.py verify")
    assert argv is not None
    assert argv[1] == "scripts/run_prospective_observation_flow.py"
    assert argv[2] == "verify"


def test_dispatchable_rejects_prose_and_injection() -> None:
    """The map is config; executing arbitrary strings from it is an injection surface."""
    assert dispatchable("future campaign preflight") is None
    assert dispatchable("scripts/ok.py; rm -rf /") is None
    assert dispatchable("rm -rf /") is None
    assert dispatchable("$(curl evil.sh)") is None
    assert dispatchable("scripts/ok.py && cat /etc/passwd") is None


def test_dispatchable_rejects_path_traversal() -> None:
    """A `scripts/` prefix is not containment: traversal points anywhere on disk."""
    assert dispatchable("scripts/../../../etc/passwd.py") is None
    assert dispatchable("scripts/../../secrets.py") is None
    assert dispatchable("scripts/sub/../../../evil.py") is None
    # A legitimate nested script is still dispatchable.
    assert dispatchable("scripts/sub/ok.py") is not None


def test_traversal_verifier_is_not_executed(tmp_path: Path) -> None:
    """Second line of defence: containment is confirmed against the resolved path."""
    outside = tmp_path / "evil.py"
    outside.write_text("raise SystemExit(0)\n")  # would 'pass' if ever executed
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    node_map = {
        **MAP,
        "blockers": [
            {
                "code": "TRAVERSAL",
                "producer": "p",
                "verifier": "scripts/../evil.py",
                "release_condition": "x",
                "earliest": "now",
                "contributes_to": [],
            }
        ],
    }
    (project / "map.yaml").write_text(yaml.safe_dump(node_map), encoding="utf-8")

    report = run_cycle(project, project / "map.yaml")

    assert report.statuses[0].state == "PENDING"
    assert report.released == (), "a traversal verifier must never release a blocker"


def test_load_map_parses_nodes_and_boundaries(project: Path) -> None:
    map_id, subject, nodes, prohibitions = load_map(project / "map.yaml")
    assert map_id == "TEST-MAP-V1"
    assert subject == "TEST-SUBJECT"
    assert len(nodes) == 3
    assert prohibitions == ()


def test_malformed_map_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"blockers": [{"producer": "x"}]}), encoding="utf-8")
    with pytest.raises(DriverError, match="without a code"):
        load_map(bad)


def test_cycle_classifies_released_blocked_and_pending(project: Path) -> None:
    report = run_cycle(project, project / "map.yaml")
    states = {status.code: status.state for status in report.statuses}
    assert states["PASSING_BLOCKER"] == "RELEASED"
    assert states["FAILING_BLOCKER"] == "BLOCKED"
    assert states["FUTURE_BLOCKER"] == "PENDING"
    assert report.released == ("PASSING_BLOCKER",)


def test_future_work_is_never_reported_as_passing(project: Path) -> None:
    """A verifier that names work not yet built must not be invented as evidence."""
    report = run_cycle(project, project / "map.yaml")
    future = next(s for s in report.statuses if s.code == "FUTURE_BLOCKER")
    assert future.state == "PENDING"
    assert "not an executable project script" in future.detail


def test_declared_prohibition_withholds_all_dispatch(project: Path) -> None:
    prohibited = {**MAP, "semantic_boundaries": {"warmup_analysis": "PROHIBITED"}}
    (project / "map.yaml").write_text(yaml.safe_dump(prohibited), encoding="utf-8")

    report = run_cycle(project, project / "map.yaml")

    assert report.prohibitions == ("warmup_analysis",)
    assert all(status.state == "PROHIBITED" for status in report.statuses)
    assert report.released == ()


def test_sealed_holdout_prohibition_is_honoured(project: Path) -> None:
    prohibited = {**MAP, "semantic_boundaries": {"sealed_v2_holdout_access": "PROHIBITED"}}
    (project / "map.yaml").write_text(yaml.safe_dump(prohibited), encoding="utf-8")
    report = run_cycle(project, project / "map.yaml")
    assert "sealed_v2_holdout_access" in report.prohibitions
    assert report.released == ()


def test_absent_verifier_script_is_pending_not_released(project: Path) -> None:
    node_map = {
        **MAP,
        "blockers": [
            {
                "code": "MISSING_SCRIPT",
                "producer": "p",
                "verifier": "scripts/does_not_exist.py",
                "release_condition": "x",
                "earliest": "now",
                "contributes_to": [],
            }
        ],
    }
    (project / "map.yaml").write_text(yaml.safe_dump(node_map), encoding="utf-8")
    report = run_cycle(project, project / "map.yaml")
    assert report.statuses[0].state == "PENDING"
    assert "absent" in report.statuses[0].detail


def test_cycle_writes_a_report_artifact(project: Path) -> None:
    run_cycle(project, project / "map.yaml")
    artifact = project / REPORT_DIR / "TEST-MAP-V1.json"
    assert artifact.is_file()
    payload = json.loads(artifact.read_text())
    assert payload["map_id"] == "TEST-MAP-V1"
    assert "PASSING_BLOCKER" in payload["released"]


def test_parked_items_record_cause_and_persist(tmp_path: Path) -> None:
    park(tmp_path, item="SUP-007 historical REST payloads", cause="bytes never retained", phase="2")
    park(tmp_path, item="T-011-05 real AI runs", cause="no provider credential", phase="2")

    items = parked_items(tmp_path)
    assert len(items) == 2
    assert items[0]["cause"] == "bytes never retained"
    assert all(item["parked_at"] for item in items)


def test_parked_items_empty_when_nothing_parked(tmp_path: Path) -> None:
    assert parked_items(tmp_path) == ()


def test_real_producer_map_parses(project: Path) -> None:
    """The shipped D-100 map must remain loadable by the driver that walks it."""
    real = Path("research/PROSPECTIVE_SIGNAL_EVIDENCE_PRODUCER_MAP_V1.yaml")
    if not real.is_file():
        pytest.skip("producer map not present in this checkout")
    map_id, subject, nodes, prohibitions = load_map(real)
    assert map_id == "PROSPECTIVE-SIGNAL-EVIDENCE-PRODUCER-MAP-V1"
    assert subject == "PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1"
    assert len(nodes) >= 9
    # The live map prohibits warm-up analysis and sealed-holdout access.
    assert "warmup_analysis" in prohibitions
