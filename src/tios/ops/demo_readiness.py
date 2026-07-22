"""Read-only, fail-closed readiness assessment for the local full-demo surface.

The assessment observes fixed local services and retained operational evidence.  It
never starts or stops a service, runs a campaign, contacts a venue, reads research
outcomes, or changes repository/runtime state.
"""

from __future__ import annotations

import http.client
import json
import os
import selectors
import shlex
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from tios.services.dashboard_api.demo_lane import _operational_disaster_stop, _order_money
from tios.services.jobs.projection import build_jobs_projection
from tios.services.jobs.store import SCHEMA_VERSION as JOBS_SCHEMA_VERSION

SCHEMA_VERSION = 1
DASHBOARD_HOST = "127.0.0.1"
DASHBOARD_PORT = 8765
MAX_HTTP_BYTES = 2 * 1024 * 1024
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_PROCESS_TABLE_BYTES = 2 * 1024 * 1024
MAX_AUTHORITY_STATUS_BYTES = 64 * 1024
CHECK_MAX_AGE = timedelta(hours=24)
ORCHESTRATOR_MAX_AGE = timedelta(minutes=30)
DEMO_HEARTBEAT_MAX_AGE = timedelta(minutes=75)

QUALITY_PATH = Path("artifacts/quality/check.json")
SITUATION_PATH = Path("artifacts/orchestrator/SITUATION.json")
DEMO_HEARTBEAT_PATH = Path("artifacts/trading_domain/demo_lane/heartbeat.json")
DEMO_STATE_PATH = Path("artifacts/trading_domain/demo_lane/lane_state.json")
DEMO_ORDERS_PATH = Path("artifacts/trading_domain/demo_lane/orders.jsonl")
DEMO_KILL_SWITCH_PATH = Path("artifacts/trading_domain/demo_lane/KILL_SWITCH")
AUTHORITY_BINARY = Path(
    "/Library/PrivilegedHelperTools/com.tios.intake-authority.d/tios-intake-authority"
)

DashboardGetter = Callable[[str], tuple[int, str, bytes]]


@dataclass(frozen=True)
class ProcessRecord:
    pid: int
    executable: Path
    cwd: Path
    argv: tuple[str, ...]


def _result(
    check_id: str,
    passed: bool,
    detail: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
        "evidence": dict(evidence or {}),
    }


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is not a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(UTC)


def _freshness(value: object, now: datetime, maximum: timedelta) -> tuple[bool, float | None]:
    try:
        age = (now - _parse_time(value)).total_seconds()
    except (OverflowError, TypeError, ValueError):
        return False, None
    return 0 <= age <= maximum.total_seconds(), round(age, 3)


def _read_bounded_bytes(root: Path, relative: Path) -> bytes:
    """Read a bounded file through no-follow descriptors at every path component."""
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise ValueError("operational evidence path is not a fixed relative path")
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | no_follow
    file_flags = os.O_RDONLY | os.O_CLOEXEC | no_follow
    descriptors = [os.open(root, directory_flags)]
    try:
        for component in relative.parts[:-1]:
            descriptor = os.open(component, directory_flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
        descriptor = os.open(relative.parts[-1], file_flags, dir_fd=descriptors[-1])
        descriptors.append(descriptor)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_JSON_BYTES:
            raise ValueError(f"unsafe operational evidence: {relative.as_posix()}")
        chunks: list[bytes] = []
        remaining = MAX_JSON_BYTES + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    if not raw or len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"invalid operational evidence size: {relative.as_posix()}")
    return raw


def _read_bounded_json(root: Path, relative: Path) -> Mapping[str, Any]:
    raw = _read_bounded_bytes(root, relative)
    payload = json.loads(raw)
    if not isinstance(payload, Mapping):
        raise ValueError(f"operational evidence is not an object: {relative.as_posix()}")
    return payload


def _read_bounded_json_lines(root: Path, relative: Path) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for line in _read_bounded_bytes(root, relative).splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, Mapping):
            raise ValueError(f"operational evidence row is not an object: {relative.as_posix()}")
        rows.append(payload)
    return rows


def _fixed_entry_info(root: Path, relative: Path) -> os.stat_result | None:
    """Inspect a fixed entry while anchoring and no-following every ancestor."""
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | no_follow
    descriptors = [os.open(root, directory_flags)]
    try:
        for component in relative.parts[:-1]:
            descriptor = os.open(component, directory_flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
        try:
            return os.stat(relative.parts[-1], dir_fd=descriptors[-1], follow_symlinks=False)
        except FileNotFoundError:
            return None
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _get_dashboard(path: str) -> tuple[int, str, bytes]:
    """GET a fixed route whose server handler reads no project evidence."""
    if path not in {"/", "/api/readiness-probe"}:
        raise ValueError("dashboard path is not allowlisted")
    connection = http.client.HTTPConnection(DASHBOARD_HOST, DASHBOARD_PORT, timeout=2)
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        declared = response.getheader("Content-Length")
        if declared is not None:
            declared_size = int(declared)
            if not 0 <= declared_size <= MAX_HTTP_BYTES:
                raise ValueError("dashboard response is too large")
        raw = response.read(MAX_HTTP_BYTES + 1)
        if not raw or len(raw) > MAX_HTTP_BYTES:
            raise ValueError("dashboard response has an invalid size")
        return response.status, content_type, raw
    finally:
        connection.close()


def _run_bounded(
    argv: list[str],
    *,
    max_stdout: int,
    max_stderr: int,
    timeout_seconds: float,
) -> tuple[bytes, bytes]:
    """Run fixed read-only argv with concurrent caps and a deadline on both pipes."""
    process = subprocess.Popen(  # noqa: S603 (callers supply fixed system executables)
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
    )
    assert process.stdout is not None and process.stderr is not None
    stdout_fd = process.stdout.fileno()
    stderr_fd = process.stderr.fileno()
    streams = {stdout_fd: (bytearray(), max_stdout), stderr_fd: (bytearray(), max_stderr)}
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + timeout_seconds
    try:
        for descriptor in streams:
            os.set_blocking(descriptor, False)
            selector.register(descriptor, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("bounded subprocess deadline exceeded")
            events = selector.select(remaining)
            if not events:
                raise TimeoutError("bounded subprocess deadline exceeded")
            for key, _mask in events:
                descriptor = key.fd
                output, limit = streams[descriptor]
                chunk = os.read(descriptor, min(65_536, limit + 1 - len(output)))
                if not chunk:
                    selector.unregister(descriptor)
                    continue
                output.extend(chunk)
                if len(output) > limit:
                    raise ValueError("bounded subprocess output limit exceeded")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("bounded subprocess deadline exceeded")
        return_code = process.wait(timeout=remaining)
        if return_code != 0:
            raise subprocess.SubprocessError("bounded subprocess failed")
        return bytes(streams[stdout_fd][0]), bytes(streams[stderr_fd][0])
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        raise
    finally:
        selector.close()
        process.stdout.close()
        process.stderr.close()


def _resolved_process_executable(pid: int) -> Path:
    if sys.platform == "darwin":
        import ctypes

        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        buffer = ctypes.create_string_buffer(4096)
        length = library.proc_pidpath(pid, buffer, len(buffer))
        if length <= 0:
            raise OSError(ctypes.get_errno(), "proc_pidpath failed")
        return Path(os.fsdecode(buffer.value)).resolve()
    return Path(os.readlink(f"/proc/{pid}/exe")).resolve()


def _resolved_process_cwd(pid: int) -> Path:
    raw, _stderr = _run_bounded(
        ["/usr/sbin/lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        max_stdout=16 * 1024,
        max_stderr=16 * 1024,
        timeout_seconds=5,
    )
    lines = raw.decode("utf-8").splitlines()
    names = [line[1:] for line in lines if line.startswith("n")]
    if len(names) != 1 or not names[0].startswith("/"):
        raise ValueError("process cwd metadata is missing or ambiguous")
    return Path(names[0]).resolve()


def _collect_processes(root: Path) -> tuple[ProcessRecord, ...]:
    raw, _stderr = _run_bounded(
        ["/bin/ps", "-ww", "-axo", "pid=,args="],
        max_stdout=MAX_PROCESS_TABLE_BYTES,
        max_stderr=64 * 1024,
        timeout_seconds=5,
    )
    text = raw.decode("utf-8")
    allowed_argv0 = {
        str(root / ".venv/bin/python"),
        str(root / ".venv/bin/python3"),
        str((root / ".venv/bin/python").resolve()),
        str((root / ".venv/bin/python3").resolve()),
    }
    records: list[ProcessRecord] = []
    for line in text.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2 or not fields[0].isdigit():
            continue
        try:
            argv = tuple(shlex.split(fields[1]))
        except ValueError:
            continue
        if not argv or argv[0] not in allowed_argv0:
            continue
        try:
            executable = _resolved_process_executable(int(fields[0]))
            cwd = _resolved_process_cwd(int(fields[0]))
        except (OSError, TimeoutError, ValueError, subprocess.SubprocessError):
            continue
        records.append(ProcessRecord(int(fields[0]), executable, cwd, argv))
    return tuple(records)


def _process_counts(root: Path, processes: tuple[ProcessRecord, ...]) -> dict[str, int]:
    interpreters = {
        str(root / ".venv/bin/python"),
        str(root / ".venv/bin/python3"),
        str((root / ".venv/bin/python").resolve()),
        str((root / ".venv/bin/python3").resolve()),
    }
    executable = (root / ".venv/bin/python").resolve()
    scripts = root / "scripts"
    suffixes: dict[str, set[tuple[str, ...]]] = {
        "dashboard": {
            ("-m", "tios.services.dashboard_ui.server"),
            ("-m", "tios.services.dashboard_ui.server", "--port", "8765"),
            (
                "-m",
                "tios.services.dashboard_ui.server",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ),
        },
        "orchestrator": {
            ("scripts/run_orchestrator.py", "--loop"),
            ("scripts/run_orchestrator.py", "--loop", "--interval", "900"),
            (str(scripts / "run_orchestrator.py"), "--loop"),
            (str(scripts / "run_orchestrator.py"), "--loop", "--interval", "900"),
        },
        "jobs": {
            ("scripts/run_job_worker.py", "run-loop", "--poll", "1.0"),
            (str(scripts / "run_job_worker.py"), "run-loop", "--poll", "1.0"),
        },
        "demo_lane": {
            ("scripts/demo_eth_lane.py", "--loop"),
            (str(scripts / "demo_eth_lane.py"), "--loop"),
        },
    }
    counts = {name: 0 for name in suffixes}
    for record in processes:
        if (
            record.executable != executable
            or record.cwd != root.resolve()
            or not record.argv
            or record.argv[0] not in interpreters
        ):
            continue
        complete_tail = record.argv[1:]
        for name, allowed_tails in suffixes.items():
            if complete_tail in allowed_tails:
                counts[name] += 1
    return counts


def _service_check(root: Path, processes: tuple[ProcessRecord, ...]) -> dict[str, Any]:
    counts = _process_counts(root, processes)
    invalid_counts = {name: count for name, count in sorted(counts.items()) if count != 1}
    return _result(
        "fixed_service_processes",
        not invalid_counts,
        (
            "exactly one authenticated process exists for each fixed service"
            if not invalid_counts
            else "fixed service process count is not exactly one"
        ),
        {
            "matching_process_counts": counts,
            "invalid_process_counts": invalid_counts,
        },
    )


def _dashboard_check(getter: DashboardGetter) -> dict[str, Any]:
    try:
        page_status, page_type, page = getter("/")
        api_status, api_type, api_raw = getter("/api/readiness-probe")
        api = json.loads(api_raw)
        valid = (
            page_status == 200
            and page_type == "text/html"
            and b"<html" in page.lower()
            and api_status == 410
            and api_type == "application/json"
            and api == {"schema_version": 1, "error": "legacy API removed; use /api/v1"}
        )
    except (OSError, ValueError, json.JSONDecodeError, http.client.HTTPException) as error:
        return _result("dashboard_loopback_api", False, str(error))
    return _result(
        "dashboard_loopback_api",
        valid,
        (
            "dashboard shell and bounded negative API schema probe passed"
            if valid
            else "dashboard shell or API schema probe failed"
        ),
        {
            "host": DASHBOARD_HOST,
            "port": DASHBOARD_PORT,
            "shell_status": page_status,
            "schema_probe_status": api_status,
            "schema_version": api.get("schema_version") if isinstance(api, Mapping) else None,
            "projection_endpoints_read": [],
        },
    )


def _orchestrator_check(root: Path, now: datetime) -> dict[str, Any]:
    try:
        payload = _read_bounded_json(root, SITUATION_PATH)
        fresh, age = _freshness(payload.get("observed_at"), now, ORCHESTRATOR_MAX_AGE)
        valid = payload.get("schema_version") == 1 and payload.get("halted") is False and fresh
        return _result(
            "orchestrator_evidence",
            valid,
            (
                "orchestrator evidence is fresh and not halted"
                if valid
                else "orchestrator evidence is stale, malformed, or halted"
            ),
            {
                "observed_at": payload.get("observed_at"),
                "age_seconds": age,
                "halted": payload.get("halted"),
            },
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _result("orchestrator_evidence", False, str(error))


def _jobs_check(root: Path) -> dict[str, Any]:
    try:
        payload = build_jobs_projection(root)
        database = payload.get("database")
        counts = payload.get("counts")
        states = counts.get("states") if isinstance(counts, Mapping) else None
        expected_states = {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}
        valid_counts = (
            isinstance(states, Mapping)
            and set(states) == expected_states
            and all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in states.values()
            )
        )
        valid = (
            payload.get("schema_version") == 1
            and payload.get("availability") == "AVAILABLE"
            and isinstance(database, Mapping)
            and database.get("schema_version") == JOBS_SCHEMA_VERSION
            and database.get("integrity") == "PASS"
            and valid_counts
        )
        return _result(
            "jobs_database",
            valid,
            (
                "jobs snapshot schema, integrity, and counts pass"
                if valid
                else "jobs snapshot validation failed"
            ),
            {
                "availability": payload.get("availability"),
                "schema_version": (
                    database.get("schema_version") if isinstance(database, Mapping) else None
                ),
                "integrity": (database.get("integrity") if isinstance(database, Mapping) else None),
                "state_counts": dict(states) if isinstance(states, Mapping) else None,
            },
        )
    except Exception as error:
        return _result("jobs_database", False, f"jobs snapshot unavailable: {type(error).__name__}")


def _quality_check(root: Path, now: datetime) -> dict[str, Any]:
    try:
        payload = _read_bounded_json(root, QUALITY_PATH)
        fresh, age = _freshness(payload.get("generated_at"), now, CHECK_MAX_AGE)
        gate = payload.get("gate")
        valid = (
            payload.get("schema_version") == 3
            and gate in {"check", "check-full"}
            and payload.get("command") == f"make {gate}"
            and payload.get("status") == "PASS"
            and payload.get("includes_dependency_audit") is False
            and fresh
        )
        return _result(
            "quality_gate",
            valid,
            (
                "latest make gate evidence is fresh and passing"
                if valid
                else "make gate evidence is stale or invalid"
            ),
            {"gate": gate, "generated_at": payload.get("generated_at"), "age_seconds": age},
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _result("quality_gate", False, str(error))


def _kill_switch_check(root: Path) -> dict[str, Any]:
    try:
        info = _fixed_entry_info(root, DEMO_KILL_SWITCH_PATH)
    except OSError as error:
        return _result("demo_kill_switch", False, str(error))
    if info is None:
        safe, engaged = True, False
    else:
        safe = stat.S_ISREG(info.st_mode) and info.st_nlink == 1
        engaged = True
    valid = safe and not engaged
    return _result(
        "demo_kill_switch",
        valid,
        (
            "kill switch is available and not engaged"
            if valid
            else "kill switch is engaged or its fixed path is unsafe"
        ),
        {"engaged": engaged, "safe_path_state": safe},
    )


def _demo_check(root: Path, now: datetime, running: bool) -> dict[str, Any]:
    try:
        heartbeat = _read_bounded_json(root, DEMO_HEARTBEAT_PATH)
        state = _read_bounded_json(root, DEMO_STATE_PATH)
        orders = _read_bounded_json_lines(root, DEMO_ORDERS_PATH)
        fresh, age = _freshness(heartbeat.get("at"), now, DEMO_HEARTBEAT_MAX_AGE)
        filled = [order for order in orders if order.get("ok") is True]
        ledger_base = sum(_order_money(dict(order))["base_delta"] for order in filled)
        stop = _operational_disaster_stop(
            dict(state),
            dict(heartbeat),
            running=running,
            ledger_base=ledger_base,
            now=now,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _result("demo_lane", False, str(error))
    stop_freshness = stop.get("freshness") if isinstance(stop, Mapping) else None
    valid = (
        running
        and heartbeat.get("schema_version") == 2
        and heartbeat.get("environment") == "VENUE_DEMO"
        and heartbeat.get("real_money") is False
        and heartbeat.get("promotion_eligible") is False
        and fresh
        and isinstance(stop, Mapping)
        and stop.get("active") is True
        and stop.get("currently_confirmed") is True
        and isinstance(stop_freshness, Mapping)
        and stop_freshness.get("fresh") is True
    )
    return _result(
        "demo_lane",
        valid,
        (
            "demo lane is fresh, fake-money only, unpromotable, and has a currently confirmed "
            "disaster stop"
            if valid
            else "demo lane safety or freshness validation failed"
        ),
        {
            "status": "RUNNING" if running else "DOWN",
            "running": running,
            "real_money": heartbeat.get("real_money"),
            "promotion_eligible": heartbeat.get("promotion_eligible"),
            "heartbeat_at": heartbeat.get("at"),
            "heartbeat_age_seconds": age,
            "disaster_stop_active": stop.get("active") if isinstance(stop, Mapping) else None,
            "disaster_stop_reason": stop.get("reason") if isinstance(stop, Mapping) else None,
        },
    )


def _authority_status() -> Mapping[str, Any]:
    """Probe only an exact safe root-owned future authority binary, if it exists."""
    try:
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | no_follow
        descriptors = [os.open("/", directory_flags)]
        try:
            for component in ("Library", "PrivilegedHelperTools", AUTHORITY_BINARY.parent.name):
                descriptor = os.open(component, directory_flags, dir_fd=descriptors[-1])
                descriptors.append(descriptor)
                ancestor = os.fstat(descriptor)
                if ancestor.st_uid != 0 or stat.S_IMODE(ancestor.st_mode) & 0o022:
                    raise PermissionError("authority ancestor is not root-controlled")
            info = os.stat(
                AUTHORITY_BINARY.name,
                dir_fd=descriptors[-1],
                follow_symlinks=False,
            )
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)
    except FileNotFoundError:
        return {
            "status": "BLOCKED",
            "blockers": ["ROOT_OWNED_ACTIVATION_AUTHORITY_NOT_INSTALLED"],
            "execution_authority": "NONE",
        }
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != 0
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o555
    ):
        return {
            "status": "BLOCKED",
            "blockers": ["ACTIVATION_AUTHORITY_PATH_UNSAFE"],
            "execution_authority": "NONE",
        }
    try:
        raw, _stderr = _run_bounded(
            [str(AUTHORITY_BINARY), "status", "--json"],
            max_stdout=MAX_AUTHORITY_STATUS_BYTES,
            max_stderr=MAX_AUTHORITY_STATUS_BYTES,
            timeout_seconds=5,
        )
        payload = json.loads(raw)
    except (OSError, TimeoutError, ValueError, subprocess.SubprocessError, json.JSONDecodeError):
        return {
            "status": "BLOCKED",
            "blockers": ["ACTIVATION_AUTHORITY_STATUS_UNAVAILABLE"],
            "execution_authority": "NONE",
        }
    if not isinstance(payload, Mapping):
        return {
            "status": "BLOCKED",
            "blockers": ["ACTIVATION_AUTHORITY_STATUS_MALFORMED"],
            "execution_authority": "NONE",
        }
    return payload


def _authority_check(probe: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
    try:
        payload = probe()
        if not isinstance(payload, Mapping):
            raise TypeError("authority status is not an object")
    except Exception as error:
        payload = {
            "status": "BLOCKED",
            "blockers": [f"ACTIVATION_AUTHORITY_PROBE_FAILED_{type(error).__name__.upper()}"],
            "execution_authority": "NONE",
        }
    blockers = payload.get("blockers")
    active = (
        payload.get("schema_version") == 1
        and payload.get("status") == "ACTIVE_NO_DECISIONS"
        and payload.get("snapshot_verified") is True
        and payload.get("execution_authority") == "NONE"
        and blockers == []
    )
    safely_gated = (
        payload.get("status") == "BLOCKED"
        and payload.get("execution_authority") == "NONE"
        and isinstance(blockers, list)
        and bool(blockers)
        and all(isinstance(item, str) and item for item in blockers)
        and not any(
            item
            in {
                "ACTIVATION_AUTHORITY_PATH_UNSAFE",
                "ACTIVATION_AUTHORITY_STATUS_UNAVAILABLE",
                "ACTIVATION_AUTHORITY_STATUS_MALFORMED",
            }
            or item.startswith("ACTIVATION_AUTHORITY_PROBE_FAILED_")
            for item in blockers
        )
    )
    status = "PASS" if active else "GATED" if safely_gated else "FAIL"
    return {
        "id": "external_intake_authority",
        "status": status,
        "detail": (
            "verified empty activation snapshot is active; execution authority remains NONE"
            if active
            else (
                "external intake authority is not activated; demo operation remains allowed"
                if safely_gated
                else "external intake authority reported unsafe or malformed status"
            )
        ),
        "evidence": {
            "authority_status": payload.get("status"),
            "snapshot_verified": payload.get("snapshot_verified") is True,
            "execution_authority": payload.get("execution_authority"),
            "blockers": blockers if isinstance(blockers, list) else [],
        },
    }


def assess_full_demo_readiness(
    root: Path,
    *,
    now: datetime | None = None,
    processes: tuple[ProcessRecord, ...] | None = None,
    dashboard_getter: DashboardGetter = _get_dashboard,
    authority_probe: Callable[[], Mapping[str, Any]] = _authority_status,
) -> dict[str, Any]:
    """Return deterministic readiness JSON for fixed evidence at a supplied observation time."""
    observed = (now or datetime.now(tz=UTC)).astimezone(UTC)
    try:
        observed_processes = _collect_processes(root) if processes is None else processes
        service_counts = _process_counts(root, observed_processes)
        service = _service_check(root, observed_processes)
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        service_counts = {"dashboard": 0, "orchestrator": 0, "jobs": 0, "demo_lane": 0}
        service = _result(
            "fixed_service_processes",
            False,
            f"process table unavailable: {type(error).__name__}",
        )
    dashboard = _dashboard_check(dashboard_getter)
    checks = [
        service,
        dashboard,
        _orchestrator_check(root, observed),
        _jobs_check(root),
        _quality_check(root, observed),
        _kill_switch_check(root),
        _demo_check(root, observed, service_counts["demo_lane"] == 1),
    ]
    authority = _authority_check(authority_probe)
    checks.append(authority)
    operational_checks_pass = all(check["status"] == "PASS" for check in checks[:-1])
    operational = operational_checks_pass and authority["status"] != "FAIL"
    if not operational:
        status, exit_code = "DEGRADED", 1
    elif authority["status"] == "GATED":
        status, exit_code = "AUTHORITY_GATED", 0
    else:
        status, exit_code = "READY", 0
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at": observed.isoformat(),
        "status": status,
        "operational": operational,
        "exit_code": exit_code,
        "execution_authority": "NONE",
        "checks": checks,
        "safety": {
            "network": "FIXED_LOOPBACK_GET_ONLY",
            "mutations": "NONE",
            "preregistered_prospective_or_sealed_outcomes_read": False,
            "historical_or_operational_evidence_may_be_read": True,
            "orders_or_campaigns_started": False,
        },
    }


def exit_code(report: Mapping[str, Any]) -> int:
    """Exit zero for operational READY/AUTHORITY_GATED, nonzero for DEGRADED."""
    return 0 if report.get("status") in {"READY", "AUTHORITY_GATED"} else 1
