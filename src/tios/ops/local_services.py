"""Bounded local-service rendering, installation, and read-only health inspection.

``render`` and install ``--dry-run`` write plist files but never mutate launchd service state.
Real installation is explicit, TCC-aware, and refuses to replace unmanaged matching processes.
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import shlex
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from tios.ops.orchestrator import REPORT_DIR, SITUATION_FILENAME
from tios.services.dashboard_api.demo_lane import build_demo_lane

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FRESH_SECONDS = 1_800
DASHBOARD_PORT = 8765


@dataclass(frozen=True)
class Service:
    name: str
    label: str
    wrapper: str
    restart_on_failure: bool


SERVICES = (
    Service("dashboard", "com.tios.dashboard", "run_dashboard.sh", True),
    Service("orchestrator", "com.tios.orchestrator", "run_orchestrator.sh", True),
    Service("jobs", "com.tios.jobs", "run_jobs.sh", True),
)


def _service(name: str) -> Service:
    return next(item for item in SERVICES if item.name == name)


def plist_payload(service: Service, root: Path = ROOT) -> dict[str, Any]:
    """Return a launchd payload whose executable and arguments are all fixed."""
    log = Path.home() / "Library" / "Logs" / f"tios_{service.name}.log"
    payload: dict[str, Any] = {
        "Label": service.label,
        "ProgramArguments": [str(root / "ops" / "local_services" / service.wrapper)],
        "WorkingDirectory": str(root),
        "EnvironmentVariables": {"PYTHONPATH": str(root / "src")},
        "RunAtLoad": True,
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
    }
    if service.restart_on_failure:
        payload["KeepAlive"] = {"SuccessfulExit": False}
    return payload


def render(output_dir: Path, root: Path = ROOT) -> list[Path]:
    """Write plist files without loading, unloading, starting, or stopping any service."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for service in SERVICES:
        target = output_dir / f"{service.label}.plist"
        target.write_bytes(plistlib.dumps(plist_payload(service, root), sort_keys=True))
        rendered.append(target)
    return rendered


def tcc_protected(root: Path, home: Path | None = None) -> bool:
    home = (home or Path.home()).resolve()
    resolved = root.resolve()
    return any(
        resolved.is_relative_to(home / folder) for folder in ("Downloads", "Desktop", "Documents")
    )


def _matching_processes(root: Path) -> dict[str, list[int]]:
    """Find only exact fixed service argv suffixes using the system process table."""
    result = subprocess.run(
        ["ps", "-axo", "pid=,args="],
        check=True,
        capture_output=True,
        text=True,
    )
    script = root / "scripts"
    manager = root / "ops/local_services/manage.py"
    signatures: dict[str, tuple[tuple[str, ...], ...]] = {
        "dashboard": (
            (
                "-m",
                "tios.services.dashboard_ui.server",
                "--host",
                "127.0.0.1",
                "--port",
                "8765",
            ),
            ("-m", "tios.services.dashboard_ui.server"),
        ),
        "orchestrator": (
            (str(script / "run_orchestrator.py"), "--loop", "--interval", "900"),
            (str(script / "run_orchestrator.py"), "--loop"),
            ("scripts/run_orchestrator.py", "--loop", "--interval", "900"),
            ("scripts/run_orchestrator.py", "--loop"),
            (str(manager), "run-orchestrator"),
        ),
        "jobs": (
            (str(script / "run_job_worker.py"), "run-loop", "--poll", "1.0"),
            ("scripts/run_job_worker.py", "run-loop", "--poll", "1.0"),
        ),
    }
    matches: dict[str, list[int]] = {service.name: [] for service in SERVICES}
    for line in result.stdout.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2 or not fields[0].isdigit():
            continue
        try:
            argv = tuple(shlex.split(fields[1]))
        except ValueError:
            continue
        for name, candidates in signatures.items():
            if any(
                len(argv) >= len(candidate) and argv[-len(candidate) :] == candidate
                for candidate in candidates
            ):
                matches[name].append(int(fields[0]))
    return matches


def _dashboard_port_occupied() -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("127.0.0.1", DASHBOARD_PORT))
    except OSError:
        return True
    finally:
        probe.close()
    return False


def installation_conflicts(root: Path = ROOT) -> list[str]:
    """Return unmanaged service conflicts; launchd reads are non-mutating."""
    states = {service.name: launchd_state(service.label) for service in SERVICES}
    matches = _matching_processes(root)
    dashboard_port_occupied = _dashboard_port_occupied()
    conflicts: list[str] = []
    for service in SERVICES:
        state = states[service.name]
        owned_pid = state.get("pid") if state["loaded"] and state["running"] else None
        unattributed = [pid for pid in matches[service.name] if pid != owned_pid]
        if unattributed:
            conflicts.append(
                f"{service.name}: matching unmanaged process PID(s) "
                + ",".join(map(str, unattributed))
            )
        dashboard_owned = (
            service.name == "dashboard"
            and state["loaded"]
            and state["running"]
            and isinstance(owned_pid, int)
            and owned_pid in matches["dashboard"]
        )
        if service.name == "dashboard" and dashboard_port_occupied and not dashboard_owned:
            conflicts.append(f"dashboard: 127.0.0.1:{DASHBOARD_PORT} is already occupied")
    return conflicts


def install(*, force: bool, dry_run: bool, root: Path = ROOT) -> list[Path]:
    """Write LaunchAgent plists and, except in dry-run, bootstrap after safe preflight."""
    python = root / ".venv" / "bin" / "python"
    if not python.is_file() or not os.access(python, os.X_OK):
        raise RuntimeError(f"venv python not found at {python}")
    if tcc_protected(root) and not (force or dry_run):
        base = subprocess.run(
            [str(python), "-c", "import sys; print(sys._base_executable)"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        raise PermissionError(
            "REFUSING: repository is under a macOS TCC-protected folder; move it outside "
            "Downloads/Desktop/Documents, or grant Full Disk Access to "
            f"{base} and retry with --force"
        )
    destination = (
        root / "artifacts" / "local_services" / "rendered"
        if dry_run
        else Path.home() / "Library" / "LaunchAgents"
    )
    if dry_run:
        return render(destination, root)
    conflicts = installation_conflicts(root)
    if conflicts:
        raise RuntimeError("REFUSING unmanaged live service(s): " + "; ".join(conflicts))
    rendered = render(destination, root)
    (Path.home() / "Library" / "Logs").mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    for service, target in zip(SERVICES, rendered, strict=True):
        subprocess.run(
            ["launchctl", "bootout", f"{domain}/{service.label}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    return rendered


def launchd_state(label: str) -> dict[str, Any]:
    result = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return {"loaded": False, "running": False, "state": "NOT_LOADED", "pid": None}
    state = "UNKNOWN"
    pid: int | None = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("state = "):
            state = stripped.removeprefix("state = ").strip()
        elif stripped.startswith("pid = "):
            value = stripped.removeprefix("pid = ").strip()
            pid = int(value) if value.isdigit() else None
    running = state == "running"
    return {
        "loaded": True,
        "running": running,
        "state": state.upper(),
        "pid": pid if running else None,
    }


def dashboard_health(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=2) as response:  # noqa: S310 (local operator-selected URL)
            payload = json.load(response)
        if response.status != 200 or not isinstance(payload, dict):
            raise ValueError("malformed status response")
    except (OSError, URLError, ValueError, json.JSONDecodeError) as error:
        return {"status": "UNREACHABLE", "reachable": False, "detail": str(error)}
    return {"status": "REACHABLE", "reachable": True}


def orchestrator_health(root: Path, now: datetime, fresh_seconds: int) -> dict[str, Any]:
    process = launchd_state(_service("orchestrator").label)
    target = root / REPORT_DIR / SITUATION_FILENAME
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        observed_at = datetime.fromisoformat(str(payload["observed_at"]))
        if observed_at.tzinfo is None:
            raise ValueError("observed_at lacks timezone")
        age = max(0.0, (now.astimezone(UTC) - observed_at.astimezone(UTC)).total_seconds())
        halted = bool(payload["halted"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        evidence: dict[str, Any] = {
            "status": "UNAVAILABLE",
            "available": False,
            "detail": str(error),
        }
    else:
        freshness = "FRESH" if age <= fresh_seconds else "STALE"
        evidence = {
            "status": "HALTED" if halted else freshness,
            "available": True,
            "freshness": freshness,
            "age_seconds": age,
            "observed_at": observed_at.isoformat(),
            "halted": halted,
        }
    if not process["loaded"]:
        status = "NOT_LOADED"
    elif not process["running"]:
        status = "DOWN"
    elif evidence.get("status") == "HALTED":
        status = "HALTED_AWAITING_OPERATOR"
    else:
        status = "RUNNING"
    return {"status": status, "process": process, "evidence": evidence}


def orchestrator_halted(root: Path = ROOT) -> bool:
    try:
        payload = json.loads((root / REPORT_DIR / SITUATION_FILENAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("halted") is True


def run_orchestrator(root: Path = ROOT) -> int:
    """Run fixed orchestrator argv, suppressing restart only for a newly retained halt."""
    target = root / REPORT_DIR / SITUATION_FILENAME
    before = target.stat().st_mtime_ns if target.is_file() else None
    result = subprocess.run(
        [
            str(root / ".venv/bin/python"),
            str(root / "scripts/run_orchestrator.py"),
            "--loop",
            "--interval",
            "900",
        ],
        cwd=root,
        check=False,
    )
    after = target.stat().st_mtime_ns if target.is_file() else None
    if result.returncode == 1 and after != before and orchestrator_halted(root):
        return 0
    return result.returncode


def health(root: Path, dashboard_url: str, fresh_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "observed_at": datetime.now(tz=UTC).isoformat(),
        "dashboard": dashboard_health(dashboard_url),
        "orchestrator": orchestrator_health(root, datetime.now(tz=UTC), fresh_seconds),
        "jobs": launchd_state(_service("jobs").label),
        "demo": {"management": "OBSERVED_ONLY", **build_demo_lane(root)},
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    rendering = commands.add_parser(
        "render", help="write plist files only; do not mutate launchd service state"
    )
    rendering.add_argument("--output-dir", type=Path, required=True)
    installing = commands.add_parser("install")
    installing.add_argument("--force", action="store_true")
    installing.add_argument(
        "--dry-run", action="store_true", help="write plist files only; do not mutate launchd"
    )
    checking = commands.add_parser("health")
    checking.add_argument("--dashboard-url", default="http://127.0.0.1:8765/api/v1/status")
    checking.add_argument("--fresh-seconds", type=int, default=DEFAULT_FRESH_SECONDS)
    commands.add_parser("orchestrator-halted")
    commands.add_parser("run-orchestrator")
    return result


def main(root: Path = ROOT) -> int:
    args = parser().parse_args()
    try:
        if args.command == "render":
            paths = render(args.output_dir, root)
            print("\n".join(map(str, paths)))
        elif args.command == "install":
            paths = install(force=args.force, dry_run=args.dry_run, root=root)
            print("\n".join(map(str, paths)))
        elif args.command == "health":
            print(json.dumps(health(root, args.dashboard_url, args.fresh_seconds), indent=2))
        elif args.command == "orchestrator-halted":
            return 0 if orchestrator_halted(root) else 1
        else:
            return run_orchestrator(root)
    except (OSError, RuntimeError, PermissionError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0
