from __future__ import annotations

import json
import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tios.ops import local_services as manage


def test_labels_and_fixed_argv_are_unique_and_restart_on_failure(tmp_path: Path) -> None:
    labels = [service.label for service in manage.SERVICES]
    assert len(labels) == len(set(labels))
    for service in manage.SERVICES:
        payload = manage.plist_payload(service, tmp_path)
        assert payload["ProgramArguments"] == [
            str(tmp_path / "ops/local_services" / service.wrapper)
        ]
        assert payload["KeepAlive"] == {"SuccessfulExit": False}
        assert "secret" not in json.dumps(payload).lower()
        assert "command" not in json.dumps(payload).lower()


def test_rendered_plists_round_trip(tmp_path: Path) -> None:
    paths = manage.render(tmp_path)
    assert len(paths) == 3
    assert {plistlib.loads(path.read_bytes())["Label"] for path in paths} == {
        service.label for service in manage.SERVICES
    }


def test_launchd_state_classifies_jobs_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *args, **kwargs: type(
            "Completed", (), {"returncode": 0, "stdout": "state = running\npid = 777\n"}
        )(),
    )
    assert manage.launchd_state("com.tios.jobs") == {
        "loaded": True,
        "running": True,
        "state": "RUNNING",
        "pid": 777,
    }


def test_dashboard_health_requires_http_json_object(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"summary": {}}'

    monkeypatch.setattr(manage, "urlopen", lambda *args, **kwargs: Response())
    assert manage.dashboard_health("http://127.0.0.1/status") == {
        "status": "REACHABLE",
        "reachable": True,
    }


def test_install_refuses_tcc_path_but_dry_run_renders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    root = home / "Downloads" / "project"
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("python")
    python.chmod(0o755)
    monkeypatch.setattr(manage.Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(manage.subprocess, "run", lambda *args, **kwargs: _completed("/python"))
    with pytest.raises(PermissionError, match="TCC-protected"):
        manage.install(force=False, dry_run=False, root=root)
    assert len(manage.install(force=False, dry_run=True, root=root)) == 3


def test_dry_run_writes_plists_without_launchd_state_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("python")
    python.chmod(0o755)
    monkeypatch.setattr(manage, "tcc_protected", lambda root: True)
    monkeypatch.setattr(
        manage,
        "installation_conflicts",
        lambda root: pytest.fail("dry-run inspected or mutated launchd state"),
    )
    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("dry-run invoked a subprocess"),
    )
    rendered = manage.install(force=False, dry_run=True, root=tmp_path)
    assert len(rendered) == 3
    assert all(path.is_file() for path in rendered)


def test_unmanaged_worker_refuses_before_launchctl_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("python")
    python.chmod(0o755)
    launchctl_calls: list[list[str]] = []

    def record(command: list[str], **kwargs: object) -> object:
        launchctl_calls.append(command)
        return _completed()

    monkeypatch.setattr(manage, "tcc_protected", lambda root: False)
    monkeypatch.setattr(
        manage,
        "launchd_state",
        lambda label: {"loaded": False, "running": False, "state": "NOT_LOADED"},
    )
    monkeypatch.setattr(
        manage,
        "_matching_processes",
        lambda root: {"dashboard": [], "orchestrator": [], "jobs": [4242]},
    )
    monkeypatch.setattr(manage, "_dashboard_port_occupied", lambda: False)
    monkeypatch.setattr(manage.subprocess, "run", record)
    with pytest.raises(RuntimeError, match="unmanaged.*jobs"):
        manage.install(force=False, dry_run=False, root=tmp_path)
    assert launchctl_calls == []


def test_unmanaged_dashboard_port_refuses_before_launchctl_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("python")
    python.chmod(0o755)
    monkeypatch.setattr(manage, "tcc_protected", lambda root: False)
    monkeypatch.setattr(
        manage,
        "launchd_state",
        lambda label: {"loaded": False, "running": False, "state": "NOT_LOADED"},
    )
    monkeypatch.setattr(
        manage,
        "_matching_processes",
        lambda root: {"dashboard": [], "orchestrator": [], "jobs": []},
    )
    monkeypatch.setattr(manage, "_dashboard_port_occupied", lambda: True)
    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("launchctl mutation occurred before refusal"),
    )
    with pytest.raises(RuntimeError, match="127.0.0.1:8765"):
        manage.install(force=False, dry_run=False, root=tmp_path)


def test_loaded_but_down_dashboard_with_occupied_port_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        manage,
        "launchd_state",
        lambda label: {"loaded": True, "running": False, "state": "EXITED", "pid": None},
    )
    monkeypatch.setattr(
        manage,
        "_matching_processes",
        lambda root: {"dashboard": [], "orchestrator": [], "jobs": []},
    )
    monkeypatch.setattr(manage, "_dashboard_port_occupied", lambda: True)
    assert manage.installation_conflicts(Path("/project")) == [
        "dashboard: 127.0.0.1:8765 is already occupied"
    ]


def test_loaded_label_with_extra_matching_pid_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = {
        "com.tios.dashboard": {"loaded": True, "running": True, "state": "RUNNING", "pid": 10},
        "com.tios.orchestrator": {
            "loaded": True,
            "running": True,
            "state": "RUNNING",
            "pid": 20,
        },
        "com.tios.jobs": {"loaded": True, "running": True, "state": "RUNNING", "pid": 30},
    }
    monkeypatch.setattr(manage, "launchd_state", states.__getitem__)
    monkeypatch.setattr(
        manage,
        "_matching_processes",
        lambda root: {"dashboard": [10, 11], "orchestrator": [20], "jobs": [30]},
    )
    monkeypatch.setattr(manage, "_dashboard_port_occupied", lambda: True)
    assert manage.installation_conflicts(Path("/project")) == [
        "dashboard: matching unmanaged process PID(s) 11"
    ]


def test_loaded_dashboard_pid_without_fixed_argv_cannot_explain_occupied_port(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = {
        "com.tios.dashboard": {"loaded": True, "running": True, "state": "RUNNING", "pid": 10},
        "com.tios.orchestrator": {
            "loaded": True,
            "running": True,
            "state": "RUNNING",
            "pid": 20,
        },
        "com.tios.jobs": {"loaded": True, "running": True, "state": "RUNNING", "pid": 30},
    }
    monkeypatch.setattr(manage, "launchd_state", states.__getitem__)
    monkeypatch.setattr(
        manage,
        "_matching_processes",
        lambda root: {"dashboard": [], "orchestrator": [20], "jobs": [30]},
    )
    monkeypatch.setattr(manage, "_dashboard_port_occupied", lambda: True)
    assert manage.installation_conflicts(Path("/project")) == [
        "dashboard: 127.0.0.1:8765 is already occupied"
    ]


def test_confirmed_sole_launchd_owned_process_is_replaceable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = {
        "com.tios.dashboard": {"loaded": True, "running": True, "state": "RUNNING", "pid": 10},
        "com.tios.orchestrator": {
            "loaded": True,
            "running": True,
            "state": "RUNNING",
            "pid": 20,
        },
        "com.tios.jobs": {"loaded": True, "running": True, "state": "RUNNING", "pid": 30},
    }
    monkeypatch.setattr(manage, "launchd_state", states.__getitem__)
    monkeypatch.setattr(
        manage,
        "_matching_processes",
        lambda root: {"dashboard": [10], "orchestrator": [20], "jobs": [30]},
    )
    monkeypatch.setattr(manage, "_dashboard_port_occupied", lambda: True)
    assert manage.installation_conflicts(Path("/project")) == []


def test_process_inspection_matches_only_fixed_service_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = "\n".join(
        (
            "101 /venv/python -m tios.services.dashboard_ui.server",
            "102 /venv/python scripts/run_orchestrator.py --loop",
            "103 /venv/python scripts/run_job_worker.py run-loop --poll 1.0",
            "104 /venv/python scripts/run_job_worker.py status some-job",
        )
    )
    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *args, **kwargs: type("Completed", (), {"returncode": 0, "stdout": output})(),
    )
    assert manage._matching_processes(tmp_path) == {
        "dashboard": [101],
        "orchestrator": [102],
        "jobs": [103],
    }


def _completed(stdout: str = "") -> object:
    return type("Completed", (), {"stdout": stdout, "returncode": 0})()


def test_orchestrator_health_separates_process_freshness_and_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 7, 21, 12, tzinfo=UTC)
    target = tmp_path / manage.REPORT_DIR / manage.SITUATION_FILENAME
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"observed_at": (now - timedelta(minutes=5)).isoformat(), "halted": True})
    )
    monkeypatch.setattr(
        manage,
        "launchd_state",
        lambda label: {"loaded": True, "running": False, "state": "EXITED"},
    )
    result = manage.orchestrator_health(tmp_path, now, 900)
    assert result["status"] == "DOWN"
    assert result["process"]["running"] is False
    assert result["evidence"]["freshness"] == "FRESH"
    assert result["evidence"]["status"] == "HALTED"
    assert manage.orchestrator_halted(tmp_path)


def test_stale_orchestrator_evidence_is_not_process_liveness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 7, 21, 12, tzinfo=UTC)
    target = tmp_path / manage.REPORT_DIR / manage.SITUATION_FILENAME
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps({"observed_at": (now - timedelta(hours=1)).isoformat(), "halted": False})
    )
    monkeypatch.setattr(
        manage,
        "launchd_state",
        lambda label: {"loaded": True, "running": True, "state": "RUNNING"},
    )
    result = manage.orchestrator_health(tmp_path, now, 900)
    assert result["status"] == "RUNNING"
    assert result["process"]["running"] is True
    assert result["evidence"]["status"] == "STALE"


def test_orchestrator_not_loaded_is_top_level_even_with_fresh_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 7, 21, 12, tzinfo=UTC)
    target = tmp_path / manage.REPORT_DIR / manage.SITUATION_FILENAME
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"observed_at": now.isoformat(), "halted": False}))
    monkeypatch.setattr(
        manage,
        "launchd_state",
        lambda label: {"loaded": False, "running": False, "state": "NOT_LOADED"},
    )
    result = manage.orchestrator_health(tmp_path, now, 900)
    assert result["status"] == "NOT_LOADED"
    assert result["evidence"]["status"] == "FRESH"


def test_new_intentional_halt_suppresses_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / manage.REPORT_DIR / manage.SITUATION_FILENAME
    target.parent.mkdir(parents=True)

    def halted_run(*args: object, **kwargs: object) -> object:
        target.write_text(json.dumps({"halted": True}))
        return type("Completed", (), {"returncode": 1})()

    monkeypatch.setattr(manage.subprocess, "run", halted_run)
    assert manage.run_orchestrator(tmp_path) == 0


def test_stale_halt_does_not_hide_unexpected_orchestrator_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / manage.REPORT_DIR / manage.SITUATION_FILENAME
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"halted": True}))
    monkeypatch.setattr(
        manage.subprocess,
        "run",
        lambda *args, **kwargs: type("Completed", (), {"returncode": 1})(),
    )
    assert manage.run_orchestrator(tmp_path) == 1


def test_demo_health_is_observed_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manage, "dashboard_health", lambda url: {"reachable": True})
    monkeypatch.setattr(manage, "orchestrator_health", lambda *args: {"status": "FRESH"})
    monkeypatch.setattr(manage, "launchd_state", lambda label: {"state": "RUNNING"})
    monkeypatch.setattr(
        manage, "build_demo_lane", lambda root: {"status": "IDLE", "running": False}
    )
    result = manage.health(tmp_path, "http://127.0.0.1/status", 900)
    assert result["demo"] == {
        "management": "OBSERVED_ONLY",
        "status": "IDLE",
        "running": False,
    }
