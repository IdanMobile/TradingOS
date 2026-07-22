from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tios.ops import demo_readiness

NOW = datetime(2026, 7, 22, 20, 0, tzinfo=UTC)


def _write_json(root: Path, relative: Path, payload: dict[str, Any]) -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload))


def _runtime(root: Path, *, halted: bool = False, check_age: timedelta = timedelta()) -> None:
    _write_json(
        root,
        demo_readiness.SITUATION_PATH,
        {
            "schema_version": 1,
            "observed_at": (NOW - timedelta(minutes=5)).isoformat(),
            "halted": halted,
        },
    )
    _write_json(
        root,
        demo_readiness.QUALITY_PATH,
        {
            "schema_version": 3,
            "gate": "check",
            "command": "make check",
            "status": "PASS",
            "includes_slow_data_tests": False,
            "includes_dependency_audit": False,
            "generated_at": (NOW - check_age).isoformat(),
        },
    )
    stop = {
        "state": "ACTIVE",
        "order_id": "demo-stop-1",
        "risk_boundary_price": "85",
        "trigger_price": "85.01",
        "base_qty": "1",
        "position_base_qty": "1",
        "risk_fraction": "0.15",
        "price_tick": "0.01",
    }
    _write_json(
        root,
        demo_readiness.DEMO_HEARTBEAT_PATH,
        {
            "schema_version": 2,
            "at": (NOW - timedelta(minutes=5)).isoformat(),
            "environment": "VENUE_DEMO",
            "real_money": False,
            "promotion_eligible": False,
            "lane_base": "1",
            "mark_price": "100",
            "resting_stop": stop,
        },
    )
    _write_json(
        root,
        demo_readiness.DEMO_STATE_PATH,
        {"lane_base": "1", "entry_price": "100", "resting_stop": stop},
    )
    orders = root / demo_readiness.DEMO_ORDERS_PATH
    orders.parent.mkdir(parents=True, exist_ok=True)
    orders.write_text(
        json.dumps(
            {
                "ok": True,
                "side": "Buy",
                "avg_price": "100",
                "reconcile": {"ETH_delta": "1", "USDT_delta": "-100"},
            }
        )
        + "\n"
    )


def _processes(root: Path) -> tuple[demo_readiness.ProcessRecord, ...]:
    interpreter = root / ".venv/bin/python"
    executable = interpreter.resolve()
    return (
        demo_readiness.ProcessRecord(
            101,
            executable,
            root.resolve(),
            (str(interpreter), "-m", "tios.services.dashboard_ui.server", "--port", "8765"),
        ),
        demo_readiness.ProcessRecord(
            102,
            executable,
            root.resolve(),
            (str(interpreter), "scripts/run_orchestrator.py", "--loop"),
        ),
        demo_readiness.ProcessRecord(
            103,
            executable,
            root.resolve(),
            (
                str(interpreter),
                str(root / "scripts/run_job_worker.py"),
                "run-loop",
                "--poll",
                "1.0",
            ),
        ),
        demo_readiness.ProcessRecord(
            104,
            executable,
            root.resolve(),
            (str(interpreter), "scripts/demo_eth_lane.py", "--loop"),
        ),
    )


def _dashboard(path: str) -> tuple[int, str, bytes]:
    if path == "/":
        return 200, "text/html", b"<!doctype html><html></html>"
    assert path == "/api/readiness-probe"
    return (
        410,
        "application/json",
        b'{"schema_version":1,"error":"legacy API removed; use /api/v1"}',
    )


@pytest.fixture
def jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        demo_readiness,
        "build_jobs_projection",
        lambda _root: {
            "schema_version": 1,
            "availability": "AVAILABLE",
            "database": {"schema_version": 4, "integrity": "PASS"},
            "counts": {
                "states": {
                    "QUEUED": 0,
                    "RUNNING": 0,
                    "SUCCEEDED": 4,
                    "FAILED": 0,
                    "CANCELLED": 1,
                }
            },
        },
    )


def _assess(root: Path, **overrides: Any) -> dict[str, Any]:
    arguments: dict[str, Any] = {
        "now": NOW,
        "processes": _processes(root),
        "dashboard_getter": _dashboard,
        "authority_probe": lambda: {
            "status": "BLOCKED",
            "blockers": ["REVIEWER_REQUIRED"],
            "execution_authority": "NONE",
        },
    }
    arguments.update(overrides)
    return demo_readiness.assess_full_demo_readiness(root, **arguments)


def test_healthy_demo_is_authority_gated_but_exits_zero(tmp_path: Path, jobs: None) -> None:
    _runtime(tmp_path)
    report = _assess(tmp_path)
    assert report["status"] == "AUTHORITY_GATED"
    assert report["operational"] is True
    assert demo_readiness.exit_code(report) == 0
    assert report["safety"] == {
        "network": "FIXED_LOOPBACK_GET_ONLY",
        "mutations": "NONE",
        "preregistered_prospective_or_sealed_outcomes_read": False,
        "historical_or_operational_evidence_may_be_read": True,
        "orders_or_campaigns_started": False,
    }


def test_verified_empty_authority_can_report_ready(tmp_path: Path, jobs: None) -> None:
    _runtime(tmp_path)
    report = _assess(
        tmp_path,
        authority_probe=lambda: {
            "schema_version": 1,
            "status": "ACTIVE_NO_DECISIONS",
            "snapshot_verified": True,
            "execution_authority": "NONE",
            "blockers": [],
        },
    )
    assert report["status"] == "READY"
    assert demo_readiness.exit_code(report) == 0


def test_unsafe_authority_status_is_degraded(tmp_path: Path, jobs: None) -> None:
    _runtime(tmp_path)
    report = _assess(
        tmp_path,
        authority_probe=lambda: {
            "status": "BLOCKED",
            "blockers": ["ACTIVATION_AUTHORITY_PATH_UNSAFE"],
            "execution_authority": "NONE",
        },
    )
    assert report["status"] == "DEGRADED"
    assert report["operational"] is False


def test_dashboard_probe_requests_only_nonprojection_routes() -> None:
    requested: list[str] = []

    def getter(path: str) -> tuple[int, str, bytes]:
        requested.append(path)
        return _dashboard(path)

    check = demo_readiness._dashboard_check(getter)
    assert check["status"] == "PASS"
    assert requested == ["/", "/api/readiness-probe"]
    assert check["evidence"]["projection_endpoints_read"] == []


@pytest.mark.parametrize("service", ["dashboard", "orchestrator", "jobs", "demo_lane"])
def test_tail_spoof_cannot_satisfy_any_service(root_path: Path, service: str) -> None:
    legitimate = _processes(root_path)
    index = ["dashboard", "orchestrator", "jobs", "demo_lane"].index(service)
    target = legitimate[index]
    spoof = demo_readiness.ProcessRecord(
        target.pid,
        Path("/bin/echo"),
        root_path.resolve(),
        ("/bin/echo", *target.argv[1:]),
    )
    records = (*legitimate[:index], spoof, *legitimate[index + 1 :])
    assert demo_readiness._process_counts(root_path, records)[service] == 0


@pytest.mark.parametrize("service", ["dashboard", "orchestrator", "jobs", "demo_lane"])
def test_wrong_cwd_cannot_satisfy_any_service(root_path: Path, service: str) -> None:
    legitimate = _processes(root_path)
    index = ["dashboard", "orchestrator", "jobs", "demo_lane"].index(service)
    target = legitimate[index]
    wrong_cwd = demo_readiness.ProcessRecord(
        target.pid,
        target.executable,
        root_path.parent.resolve(),
        target.argv,
    )
    records = (*legitimate[:index], wrong_cwd, *legitimate[index + 1 :])
    assert demo_readiness._process_counts(root_path, records)[service] == 0


def test_current_safe_dashboard_argv_is_accepted(root_path: Path) -> None:
    assert demo_readiness._process_counts(root_path, _processes(root_path))["dashboard"] == 1


@pytest.mark.parametrize("service", ["dashboard", "orchestrator", "jobs", "demo_lane"])
def test_duplicate_authenticated_process_degrades_readiness(
    tmp_path: Path, jobs: None, service: str
) -> None:
    _runtime(tmp_path)
    legitimate = _processes(tmp_path)
    index = ["dashboard", "orchestrator", "jobs", "demo_lane"].index(service)
    target = legitimate[index]
    duplicate = demo_readiness.ProcessRecord(
        target.pid + 1000,
        target.executable,
        target.cwd,
        target.argv,
    )
    report = _assess(tmp_path, processes=(*legitimate, duplicate))
    assert report["status"] == "DEGRADED"
    process_check = next(
        check for check in report["checks"] if check["id"] == "fixed_service_processes"
    )
    assert process_check["status"] == "FAIL"
    assert process_check["evidence"]["invalid_process_counts"] == {service: 2}


def test_unapproved_dashboard_port_is_rejected(root_path: Path) -> None:
    target = _processes(root_path)[0]
    unapproved = demo_readiness.ProcessRecord(
        target.pid,
        target.executable,
        target.cwd,
        (*target.argv[:-1], "9999"),
    )
    assert demo_readiness._process_counts(root_path, (unapproved,))["dashboard"] == 0


def test_bounded_command_collects_normal_stdout_and_stderr() -> None:
    stdout, stderr = demo_readiness._run_bounded(
        [sys.executable, "-c", "import sys; print('ok'); print('note', file=sys.stderr)"],
        max_stdout=64,
        max_stderr=64,
        timeout_seconds=2,
    )
    assert stdout == b"ok\n"
    assert stderr == b"note\n"


def test_bounded_command_rejects_oversized_output() -> None:
    with pytest.raises(ValueError, match="output limit"):
        demo_readiness._run_bounded(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * 1024)"],
            max_stdout=16,
            max_stderr=16,
            timeout_seconds=2,
        )


def test_bounded_command_enforces_timeout_without_output() -> None:
    with pytest.raises(TimeoutError, match="deadline"):
        demo_readiness._run_bounded(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            max_stdout=64,
            max_stderr=64,
            timeout_seconds=0.05,
        )


def test_bounded_command_times_out_when_descendant_holds_pipe_open() -> None:
    source = (
        "import subprocess,sys; "
        "subprocess.Popen(['/bin/sleep','5'], stdout=sys.stdout, stderr=sys.stderr); "
        "print('small', flush=True)"
    )
    with pytest.raises(TimeoutError, match="deadline"):
        demo_readiness._run_bounded(
            [sys.executable, "-c", source],
            max_stdout=64,
            max_stderr=64,
            timeout_seconds=0.1,
        )


@pytest.fixture
def root_path(tmp_path: Path) -> Path:
    return tmp_path


@pytest.mark.parametrize("failure", ["missing_process", "halted", "stale_gate", "unsafe_demo"])
def test_operational_failure_is_degraded(tmp_path: Path, jobs: None, failure: str) -> None:
    _runtime(
        tmp_path,
        halted=failure == "halted",
        check_age=timedelta(days=2) if failure == "stale_gate" else timedelta(),
    )
    processes = _processes(tmp_path)
    if failure == "missing_process":
        processes = processes[:-1]
    if failure == "unsafe_demo":
        heartbeat = json.loads((tmp_path / demo_readiness.DEMO_HEARTBEAT_PATH).read_text())
        heartbeat["real_money"] = True
        _write_json(tmp_path, demo_readiness.DEMO_HEARTBEAT_PATH, heartbeat)
    report = _assess(tmp_path, processes=processes)
    assert report["status"] == "DEGRADED"
    assert report["operational"] is False
    assert demo_readiness.exit_code(report) == 1


def test_assessment_does_not_change_runtime_files(tmp_path: Path, jobs: None) -> None:
    _runtime(tmp_path)
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    _assess(tmp_path)
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_symlinked_final_evidence_fails_closed(tmp_path: Path, jobs: None) -> None:
    _runtime(tmp_path)
    target = tmp_path / "real-heartbeat.json"
    target.write_text((tmp_path / demo_readiness.DEMO_HEARTBEAT_PATH).read_text())
    (tmp_path / demo_readiness.DEMO_HEARTBEAT_PATH).unlink()
    (tmp_path / demo_readiness.DEMO_HEARTBEAT_PATH).symlink_to(target)
    assert _assess(tmp_path)["status"] == "DEGRADED"


def test_symlinked_evidence_ancestor_fails_closed(tmp_path: Path, jobs: None) -> None:
    _runtime(tmp_path)
    trading_domain = tmp_path / "artifacts/trading_domain"
    moved = tmp_path / "outside-trading-domain"
    trading_domain.rename(moved)
    trading_domain.symlink_to(moved, target_is_directory=True)
    assert _assess(tmp_path)["status"] == "DEGRADED"
