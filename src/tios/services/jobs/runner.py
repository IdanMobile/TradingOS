"""Bounded, network-isolated execution for local jobs."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import signal
import stat
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Any, Protocol, cast

from tios.services.jobs.store import Job, JobState, JobStore, JobType

SANDBOX_EXEC = Path("/usr/bin/sandbox-exec")
SANDBOX_PROFILE = "(version 1)(allow default)(deny network*)"


class Process(Protocol):
    pid: int
    returncode: int | None

    def poll(self) -> int | None: ...

    def communicate(self) -> tuple[str, str]: ...

    def wait(self, timeout: float | None = None) -> int: ...


PopenFactory = Callable[..., Process]


class JobCancelled(RuntimeError):
    pass


class JobTimedOut(TimeoutError):
    pass


@dataclass(frozen=True)
class JobResult:
    artifact_ref: str
    digest: str
    reused: bool


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_database(root: Path | None = None) -> Path:
    return (root or repository_root()).resolve() / "artifacts/jobs/jobs.sqlite3"


def _confined(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"path must remain within {root}")
    return resolved


def _safe_environment(root: Path) -> dict[str, str]:
    jobs_root = _confined(root / "artifacts/jobs", root)
    temporary = _confined(jobs_root / "tmp", jobs_root)
    temporary.mkdir(parents=True, exist_ok=True)
    return {
        "HOME": str(root),
        "LANG": "C",
        "PATH": "/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "TIOS_AI_MODE": "mock",
        "TMPDIR": str(temporary),
        "TZ": "UTC",
    }


def research_lab_command(root: Path) -> list[str]:
    script = _confined(root / "scripts/run_research_lab_v0.py", root)
    if platform.system() != "Darwin" or not SANDBOX_EXEC.is_file():
        raise RuntimeError("network isolation is unavailable; refusing job execution")
    return [str(SANDBOX_EXEC), "-p", SANDBOX_PROFILE, sys.executable, str(script)]


def _open_directory(parent_fd: int, name: str) -> int:
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    opened = os.fstat(descriptor)
    linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(linked.st_mode) or (opened.st_dev, opened.st_ino) != (
        linked.st_dev,
        linked.st_ino,
    ):
        os.close(descriptor)
        raise RuntimeError(f"artifact directory changed while opening: {name}")
    return descriptor


def _open_artifact_directory(root: Path, *components: str) -> int:
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for component in components:
            child = _open_directory(descriptor, component)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_descriptor(descriptor: int, heartbeat: Callable[[], None]) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while chunk := os.read(descriptor, 1024 * 1024):
        heartbeat()
        chunks.append(chunk)
    return b"".join(chunks)


def _stable_bytes_at(parent_fd: int, name: str, heartbeat: Callable[[], None]) -> tuple[bytes, str]:
    heartbeat()
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        before = os.fstat(descriptor)
        linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (
            linked.st_dev,
            linked.st_ino,
        ):
            raise RuntimeError(f"artifact inode changed while opening: {name}")
        first = _read_descriptor(descriptor, heartbeat)
        middle = os.fstat(descriptor)
        second = _read_descriptor(descriptor, heartbeat)
        after = os.fstat(descriptor)
        linked_after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    finally:
        os.close(descriptor)
    first_digest = hashlib.sha256(first).hexdigest()
    signatures = [
        (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
        for value in (before, middle, after, linked_after)
    ]
    if len(set(signatures)) != 1 or first_digest != hashlib.sha256(second).hexdigest():
        raise RuntimeError(f"artifact changed while being verified: {name}")
    heartbeat()
    return first, first_digest


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _read_lab_file(
    root: Path, lab_id: str, name: str, heartbeat: Callable[[], None]
) -> tuple[bytes, str]:
    batch_fd = _open_artifact_directory(root, "artifacts", "research_lab", "v0", lab_id)
    try:
        return _stable_bytes_at(batch_fd, name, heartbeat)
    finally:
        os.close(batch_fd)


def _verify_artifacts(
    root: Path,
    response: dict[str, Any],
    heartbeat: Callable[[], None] = lambda: None,
) -> JobResult:
    lab_id = response.get("lab_id")
    if not isinstance(lab_id, str) or not lab_id.startswith("LAB-") or Path(lab_id).name != lab_id:
        raise RuntimeError("research lab returned an invalid artifact identity")
    batch_fd = _open_artifact_directory(root, "artifacts", "research_lab", "v0", lab_id)
    try:
        result_raw, result_digest = _stable_bytes_at(batch_fd, "lab_run.json", heartbeat)
        manifest_raw, manifest_digest = _stable_bytes_at(batch_fd, "manifest.json", heartbeat)
    finally:
        os.close(batch_fd)
    retained = _json_object(result_raw, "lab result")
    manifest = _json_object(manifest_raw, "lab manifest")
    retained_content = {
        key: value for key, value in retained.items() if key not in {"content_sha256", "reused"}
    }
    response_content = {key: value for key, value in response.items() if key != "reused"}
    retained_response = {key: value for key, value in retained.items() if key != "reused"}
    if (
        retained.get("status") != "COMPLETED"
        or retained.get("lab_id") != lab_id
        or retained.get("reused") is not False
        or retained.get("content_sha256") != _canonical_digest(retained_content)
        or response_content != retained_response
    ):
        raise RuntimeError("research lab result integrity failure")
    if (
        manifest.get("status") != "COMPLETED"
        or manifest.get("lab_id") != lab_id
        or manifest.get("hashes") != retained.get("hashes")
        or retained.get("artifact_manifest_sha256") != manifest_digest
    ):
        raise RuntimeError("research lab manifest integrity failure")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise RuntimeError("research lab manifest has no artifact inventory")
    for name, expected in artifacts.items():
        if not isinstance(name, str) or Path(name).name != name or not isinstance(expected, str):
            raise RuntimeError("research lab manifest artifact entry is invalid")
        _, actual = _read_lab_file(root, lab_id, name, heartbeat)
        if actual != expected:
            raise RuntimeError(f"research lab artifact digest mismatch: {name}")
    return JobResult(
        artifact_ref=f"artifacts/research_lab/v0/{lab_id}/lab_run.json",
        digest=result_digest,
        reused=response.get("reused") is True,
    )


def _stop_process_group(process: Process, *, grace_seconds: float = 1.0) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    if process.poll() is not None:
        process.wait(timeout=1)
        return
    deadline = time.monotonic() + grace_seconds
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def run_research_lab(
    root: Path,
    job: Job,
    *,
    popen: PopenFactory = subprocess.Popen,
    cancelled: Callable[[], bool] = lambda: False,
    heartbeat: Callable[[], None] = lambda: None,
    poll_seconds: float = 0.1,
) -> JobResult:
    root = root.resolve()
    if job.payload:
        raise ValueError("RESEARCH_LAB_V0 does not accept path or command overrides")
    command = research_lab_command(root)
    if cancelled():
        raise JobCancelled("cancelled before process start")
    process = popen(
        command,
        cwd=root,
        env=_safe_environment(root),
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + job.timeout_seconds
    while process.poll() is None:
        try:
            heartbeat()
        except BaseException:
            _stop_process_group(process)
            raise
        if cancelled():
            _stop_process_group(process)
            raise JobCancelled("cancelled by operator")
        if time.monotonic() >= deadline:
            _stop_process_group(process)
            raise JobTimedOut(f"job exceeded {job.timeout_seconds}s timeout")
        time.sleep(poll_seconds)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"research lab exited {process.returncode}: {stderr[-2000:]}")
    response = _json_object(stdout.encode(), "research lab response")
    heartbeat()
    return _verify_artifacts(root, response, heartbeat)


class Worker:
    def __init__(
        self,
        store: JobStore,
        *,
        root: Path | None = None,
        owner: str | None = None,
        popen: PopenFactory = subprocess.Popen,
        lease_seconds: int = 60,
        retry_backoff_seconds: int = 30,
    ) -> None:
        self.store = store
        self.root = (root or repository_root()).resolve()
        self.owner = owner or f"worker-{uuid.uuid4().hex}"
        self.popen = popen
        self.lease_seconds = lease_seconds
        self.retry_backoff_seconds = retry_backoff_seconds

    def __enter__(self) -> Worker:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    def run_once(self) -> Job | None:
        self.store.materialize_due()
        job = self.store.claim(self.owner, lease_seconds=self.lease_seconds)
        if job is None:
            return None
        heartbeat = self._heartbeat(job)
        try:
            result = self._execute(job, heartbeat)
            self._confirm_result(result, heartbeat)
        except JobCancelled as error:
            return self.store.finish_cancelled(job.job_id, self.owner, str(error))
        except Exception as error:
            try:
                return self.store.fail(
                    job.job_id,
                    self.owner,
                    f"{type(error).__name__}: {error}",
                    backoff_seconds=self.retry_backoff_seconds,
                )
            except RuntimeError:
                return self.store.get(job.job_id)
        return self.store.succeed(
            job.job_id,
            self.owner,
            artifact_ref=result.artifact_ref,
            digest=result.digest,
            reused=result.reused,
        )

    def run_loop(self, stop: Event, *, poll_seconds: float = 1.0) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        while not stop.is_set():
            job = self.run_once()
            if job is None or job.state is JobState.QUEUED:
                stop.wait(poll_seconds)

    def _execute(self, job: Job, heartbeat: Callable[[], None]) -> JobResult:
        if job.job_type is JobType.RESEARCH_LAB_V0:
            return run_research_lab(
                self.root,
                job,
                popen=self.popen,
                cancelled=lambda: self.store.is_cancel_requested(job.job_id, self.owner),
                heartbeat=heartbeat,
            )
        raise RuntimeError(f"no safe handler is configured for {job.job_type.value}")

    def _heartbeat(self, job: Job) -> Callable[[], None]:
        next_renewal = 0.0
        interval = max(0.5, min(30.0, self.lease_seconds / 3))

        def renew() -> None:
            nonlocal next_renewal
            now = time.monotonic()
            if now >= next_renewal:
                self.store.renew_lease(job.job_id, self.owner, lease_seconds=self.lease_seconds)
                next_renewal = now + interval

        return renew

    def _confirm_result(self, result: JobResult, heartbeat: Callable[[], None]) -> None:
        parts = Path(result.artifact_ref).parts
        if parts[:3] != ("artifacts", "research_lab", "v0") or len(parts) != 5:
            raise RuntimeError("research lab result reference is invalid")
        lab_id, name = parts[3:]
        if name != "lab_run.json":
            raise RuntimeError("research lab result reference is invalid")
        raw, _ = _read_lab_file(self.root, lab_id, name, heartbeat)
        retained = _json_object(raw, "lab result")
        verified = _verify_artifacts(self.root, {**retained, "reused": result.reused}, heartbeat)
        if verified != result:
            raise RuntimeError("research lab result changed before recording")


def run_loop_until_interrupted(worker: Worker, *, poll_seconds: float = 1.0) -> None:
    stop = Event()
    previous = {
        signum: signal.signal(signum, lambda _signum, _frame: stop.set())
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        worker.run_loop(stop, poll_seconds=poll_seconds)
    except KeyboardInterrupt:
        stop.set()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        worker.close()
