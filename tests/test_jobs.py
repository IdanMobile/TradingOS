from __future__ import annotations

import gc
import hashlib
import json
import multiprocessing
import os
import signal
import sqlite3
import sys
import weakref
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tios.services.jobs import (
    JobState,
    JobStore,
    JobType,
    Worker,
    build_jobs_projection,
    runner,
)
from tios.services.jobs import store as store_module

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_job_worker as jobs_cli  # noqa: E402

NOW = datetime(2026, 7, 10, tzinfo=UTC)


def _initialize_in_process(root: str, path: str) -> None:
    with JobStore(Path(path), root=Path(root)) as store:
        store.initialize()


def _paused_write_writer(
    root: str,
    path: str,
    ready: Any,
    replacement_done: Any,
    results: Any,
) -> None:
    with JobStore(Path(path), root=Path(root)) as store:
        original = store._write_file  # noqa: SLF001

        def pause_at_write_entry(parent_fd: int, payload: bytes) -> None:
            ready.set()
            if not replacement_done.wait(10):
                raise RuntimeError("replacement writer timed out")
            original(parent_fd, payload)

        store._write_file = pause_at_write_entry  # type: ignore[method-assign]  # noqa: SLF001
        try:
            store.enqueue(JobType.RESEARCH_LAB_V0, "stale-writer")
        except Exception as error:
            results.put(f"{type(error).__name__}: {error}")
        else:
            results.put("paused writer success")


def _lock_path_replacement_writer(
    root: str,
    path: str,
    ready: Any,
    replacement_done: Any,
    results: Any,
) -> None:
    if not ready.wait(10):
        results.put("replacement did not start")
        replacement_done.set()
        return
    lock = Path(path).parent / ".jobs.lock"
    lock.unlink()
    lock.write_text("replacement", encoding="utf-8")
    replacement_done.set()
    try:
        with JobStore(Path(path), root=Path(root)) as store:
            store.enqueue(JobType.RESEARCH_LAB_V0, "replacement-writer")
    except Exception as error:
        results.put(f"replacement {type(error).__name__}: {error}")
    else:
        results.put("replacement success")


def _directory_replacement_writer(
    root: str,
    path: str,
    ready: Any,
    replacement_done: Any,
    results: Any,
) -> None:
    if not ready.wait(10):
        results.put("directory replacement did not start")
        replacement_done.set()
        return
    jobs = Path(path).parent
    jobs.rename(jobs.with_name("jobs-detached"))
    jobs.mkdir()
    try:
        with JobStore(Path(path), root=Path(root)) as store:
            store.initialize()
            store.enqueue(JobType.RESEARCH_LAB_V0, "visible-writer")
    except Exception as error:
        results.put(f"replacement {type(error).__name__}: {error}")
    else:
        results.put("replacement success")
    finally:
        replacement_done.set()


class FakeProcess:
    def __init__(self, stdout: str = "", *, running: bool = False) -> None:
        self.pid = 424242
        self.returncode: int | None = None if running else 0
        self.stdout = stdout

    def poll(self) -> int | None:
        return self.returncode

    def communicate(self) -> tuple[str, str]:
        return self.stdout, ""

    def wait(self, timeout: float | None = None) -> int:
        assert timeout is None or timeout > 0
        return self.returncode or 0


def _store(root: Path) -> JobStore:
    root.mkdir(parents=True, exist_ok=True)
    store = JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root)
    store.initialize()
    return store


def _sandbox(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    sandbox = root / "fake-sandbox-exec"
    sandbox.parent.mkdir(parents=True, exist_ok=True)
    sandbox.write_text("", encoding="utf-8")
    monkeypatch.setattr(runner.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(runner, "SANDBOX_EXEC", sandbox)
    script = root / "scripts/run_research_lab_v0.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# fake\n", encoding="utf-8")
    return sandbox


def _lab_artifacts(root: Path, *, reused: bool = True) -> tuple[dict[str, Any], Path]:
    batch = root / "artifacts/research_lab/v0/LAB-TEST"
    batch.mkdir(parents=True, exist_ok=True)
    retained_artifact = batch / "retained.txt"
    retained_artifact.write_text("evidence", encoding="utf-8")
    artifact_digest = hashlib.sha256(retained_artifact.read_bytes()).hexdigest()
    manifest = {
        "lab_id": "LAB-TEST",
        "status": "COMPLETED",
        "hashes": {"input": "fixed"},
        "artifacts": {"retained.txt": artifact_digest},
    }
    manifest_path = batch / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    result: dict[str, Any] = {
        "lab_id": "LAB-TEST",
        "status": "COMPLETED",
        "reused": False,
        "hashes": manifest["hashes"],
        "artifact_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    content = {key: value for key, value in result.items() if key != "reused"}
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
    result["content_sha256"] = hashlib.sha256(encoded).hexdigest()
    result_path = batch / "lab_run.json"
    result_path.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    return {**result, "reused": reused}, result_path


def test_database_path_and_symlink_confinement(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    allowed = root / "artifacts/jobs"
    allowed.mkdir(parents=True)
    assert (
        JobStore(Path("artifacts/jobs/local.sqlite3"), root=root).path
        == (allowed / "local.sqlite3").resolve()
    )
    with pytest.raises(ValueError, match="must remain"):
        JobStore(tmp_path / "outside.sqlite3", root=root)
    with pytest.raises(ValueError, match="must remain"):
        JobStore(Path("../escape.sqlite3"), root=root)

    linked_root = tmp_path / "linked-repo"
    (linked_root / "artifacts").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (linked_root / "artifacts/jobs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="artifacts/jobs"):
        JobStore(Path("artifacts/jobs/jobs.sqlite3"), root=linked_root)

    target = tmp_path / "target.sqlite3"
    target.touch()
    (allowed / "linked.sqlite3").symlink_to(target)
    with pytest.raises(ValueError, match="must remain"):
        JobStore(allowed / "linked.sqlite3", root=root)

    raced_root = tmp_path / "raced-repo"
    raced_root.mkdir()
    raced = JobStore(Path("artifacts/jobs/jobs.sqlite3"), root=raced_root)
    (raced_root / "artifacts").mkdir(parents=True)
    (raced_root / "artifacts/jobs").symlink_to(outside, target_is_directory=True)
    with pytest.raises(OSError):
        raced.initialize()


def test_database_directory_swap_stays_on_fixed_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    store = JobStore(Path("artifacts/jobs/jobs.sqlite3"), root=root)
    original = store._open_parent_anchor  # noqa: SLF001
    swapped = False

    def swap_after_open(*, create: bool) -> tuple[int, int, str]:
        nonlocal swapped
        descriptors = original(create=create)
        if not swapped:
            jobs = root / "artifacts/jobs"
            jobs.rename(root / "artifacts/jobs-held")
            jobs.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptors

    monkeypatch.setattr(store, "_open_parent_anchor", swap_after_open)
    with pytest.raises(RuntimeError, match="jobs directory identity changed"):
        store.initialize()
    assert list(outside.iterdir()) == []
    store.close()


def test_database_file_swap_never_follows_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    store = _store(root)
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"outside")
    original = store._read_file  # noqa: SLF001
    swapped = False

    def swap_file(parent_fd: int, name: str) -> bytes:
        nonlocal swapped
        if not swapped:
            os.unlink(name, dir_fd=parent_fd)
            os.symlink(outside, name, dir_fd=parent_fd)
            swapped = True
        return original(parent_fd, name)

    monkeypatch.setattr(store, "_read_file", swap_file)
    with pytest.raises(OSError):
        store.list()
    assert outside.read_bytes() == b"outside"


def test_realpath_alias_is_allowed_but_escape_is_not(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    alias = Path(str(root).replace("/private/var/", "/var/"))
    candidate = alias / "artifacts/jobs/jobs.sqlite3"
    store = JobStore(candidate, root=alias)
    assert store.path == root / "artifacts/jobs/jobs.sqlite3"
    store.close()


def test_store_close_context_and_finalizer_release_root_fd(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    store = JobStore(Path("artifacts/jobs/jobs.sqlite3"), root=root)
    descriptor = store._root_fd  # noqa: SLF001
    with store:
        store.initialize()
    with pytest.raises(OSError):
        os.fstat(descriptor)
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.list()

    finalized = JobStore(Path("artifacts/jobs/finalized.sqlite3"), root=root)
    finalized_descriptor = finalized._root_fd  # noqa: SLF001
    reference = weakref.ref(finalized)
    del finalized
    gc.collect()
    assert reference() is None
    with pytest.raises(OSError):
        os.fstat(finalized_descriptor)


def test_database_image_capacity_guard(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    path = root / "artifacts/jobs/jobs.sqlite3"
    path.parent.mkdir(parents=True)
    with path.open("wb") as stream:
        stream.truncate(store_module.MAX_DB_IMAGE_BYTES + 1)
    with JobStore(path, root=root) as store:
        with pytest.raises(RuntimeError, match="capacity limit"):
            store.initialize()


def test_jobs_projection_is_complete_json_safe_and_read_only(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    store = _store(root)
    successful = store.enqueue(JobType.RESEARCH_LAB_V0, "projection-success")
    claimed = store.claim("projection-worker")
    assert claimed is not None and claimed.job_id == successful.job_id
    store.succeed(
        successful.job_id,
        "projection-worker",
        artifact_ref="artifacts/research_lab/v0/LAB-PROJECTION/lab_run.json",
        digest="a" * 64,
        reused=True,
    )
    failed = store.enqueue(
        JobType.RESEARCH_LAB_V0,
        "projection-failure",
        {"private_note": "payload-must-not-appear"},
    )
    claimed = store.claim("projection-worker")
    assert claimed is not None and claimed.job_id == failed.job_id
    store.fail(
        failed.job_id,
        "projection-worker",
        "exchange returned sk_live_error-must-not-appear",
    )
    store.enqueue(JobType.DATA_QUALITY, "projection-queued")
    store.add_schedule(
        "projection-schedule",
        JobType.REPORT_REFRESH,
        300,
        NOW,
        {"private_note": "schedule-payload-must-not-appear"},
    )
    store.close()

    database = root / "artifacts/jobs/jobs.sqlite3"
    before = (database.read_bytes(), database.stat().st_mtime_ns)
    projection = build_jobs_projection(root)
    after = (database.read_bytes(), database.stat().st_mtime_ns)

    assert before == after
    assert projection["schema_version"] == 1
    assert projection["availability"] == "AVAILABLE"
    assert projection["database"]["integrity"] == "PASS"
    assert projection["database"]["capacity"]["bytes"] == len(before[0])
    assert projection["counts"]["states"] == {
        "CANCELLED": 0,
        "FAILED": 1,
        "QUEUED": 1,
        "RUNNING": 0,
        "SUCCEEDED": 1,
    }
    assert projection["counts"]["types"]["RESEARCH_LAB_V0"] == 2
    assert len(projection["latest_jobs"]) == 3
    completed = next(job for job in projection["latest_jobs"] if job["state"] == "SUCCEEDED")
    assert completed["result"] == {
        "artifact_ref": "artifacts/research_lab/v0/LAB-PROJECTION/lab_run.json",
        "digest": "a" * 64,
        "reused": True,
    }
    retained_error = next(job for job in projection["latest_jobs"] if job["state"] == "FAILED")
    assert retained_error["error"] == "[REDACTED]"
    assert projection["schedules"] == [
        {
            "schedule_id": "projection-schedule",
            "type": "REPORT_REFRESH",
            "interval_seconds": 300,
            "next_due": NOW.isoformat(),
            "max_attempts": 1,
            "timeout_seconds": 3600,
        }
    ]
    assert projection["worker"]["mode"] == "LOCAL_OPERATOR_CLI_ONLY"
    assert projection["worker"]["http_endpoint"] is False
    assert "ORDER_EXECUTION" in projection["capabilities"]["prohibited"]
    encoded = json.dumps(projection, sort_keys=True)
    assert "payload-must-not-appear" not in encoded
    assert "schedule-payload-must-not-appear" not in encoded
    assert "error-must-not-appear" not in encoded


def test_jobs_projection_does_not_materialize_due_schedules(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    store = _store(root)
    store.add_schedule("due-now", JobType.RESEARCH_LAB_V0, 60, NOW)
    store.close()
    database = root / "artifacts/jobs/jobs.sqlite3"
    before = (database.read_bytes(), database.stat().st_mtime_ns)

    projection = build_jobs_projection(root)

    assert projection["availability"] == "AVAILABLE"
    assert projection["latest_jobs"] == []
    assert projection["counts"]["states"]["QUEUED"] == 0
    assert projection["schedules"][0]["schedule_id"] == "due-now"
    assert (database.read_bytes(), database.stat().st_mtime_ns) == before


def test_jobs_projection_fails_closed_for_missing_malformed_and_tampered_db(
    tmp_path: Path,
) -> None:
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    missing = build_jobs_projection(missing_root)
    assert missing["availability"] == "MISSING"
    assert missing["latest_jobs"] == []

    malformed_root = tmp_path / "malformed"
    database = malformed_root / "artifacts/jobs/jobs.sqlite3"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"not sqlite and must remain unchanged")
    before = (database.read_bytes(), database.stat().st_mtime_ns)
    malformed = build_jobs_projection(malformed_root)
    assert malformed["availability"] == "ERROR"
    assert malformed["database"]["integrity"] == "UNAVAILABLE"
    assert (database.read_bytes(), database.stat().st_mtime_ns) == before

    tampered_root = tmp_path / "tampered"
    store = _store(tampered_root)
    store.close()
    tampered_database = tampered_root / "artifacts/jobs/jobs.sqlite3"
    with sqlite3.connect(tampered_database) as connection:
        connection.execute("UPDATE schema_version SET version = 999")
    tampered = build_jobs_projection(tampered_root)
    assert tampered["availability"] == "ERROR"
    assert tampered["latest_jobs"] == []


def test_jobs_projection_rejects_symlink_escape_without_reading_it(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_store = _store(outside)
    outside_store.enqueue(JobType.RESEARCH_LAB_V0, "outside-secret-id")
    outside_store.close()
    outside_database = outside / "artifacts/jobs/jobs.sqlite3"
    before = (outside_database.read_bytes(), outside_database.stat().st_mtime_ns)

    root = tmp_path / "repo"
    (root / "artifacts").mkdir(parents=True)
    (root / "artifacts/jobs").symlink_to(outside / "artifacts/jobs", target_is_directory=True)
    projection = build_jobs_projection(root)

    assert projection["availability"] == "ERROR"
    assert projection["latest_jobs"] == []
    assert "outside-secret-id" not in json.dumps(projection)
    assert (outside_database.read_bytes(), outside_database.stat().st_mtime_ns) == before


def test_migration_is_atomic_and_restartable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    path = root / "artifacts/jobs/jobs.sqlite3"
    path.parent.mkdir(parents=True)
    original = store_module._apply_migration  # noqa: SLF001
    with sqlite3.connect(path, isolation_level=None) as connection:
        connection.execute("BEGIN IMMEDIATE")
        original(connection, store_module._MIGRATIONS[0], 1)  # noqa: SLF001
        connection.commit()

    def interrupted(
        connection: sqlite3.Connection, statements: tuple[str, ...], version: int
    ) -> None:
        connection.execute(statements[0])
        raise RuntimeError(f"interrupted migration {version}")

    monkeypatch.setattr(store_module, "_apply_migration", interrupted)
    store = JobStore(path, root=root)
    with pytest.raises(RuntimeError, match="interrupted migration 2"):
        store.initialize()
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        assert "cancel_requested" not in columns
        assert connection.execute("PRAGMA user_version").fetchone() == (1,)
        assert connection.execute("SELECT version FROM schema_version").fetchone() == (1,)

    monkeypatch.setattr(store_module, "_apply_migration", original)
    store.initialize()
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)")}
        assert "cancel_requested" in columns
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert connection.execute("SELECT version FROM schema_version").fetchone() == (2,)


def test_concurrent_initialization_is_safe_across_threads_and_processes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    path = root / "artifacts/jobs/jobs.sqlite3"

    def initialize(_: int) -> None:
        JobStore(path, root=root).initialize()

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(initialize, range(16)))
    processes = [
        multiprocessing.Process(target=_initialize_in_process, args=(str(root), str(path)))
        for _ in range(4)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
        assert process.exitcode == 0
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)


def test_write_entry_lock_path_replacement_does_not_split_serialization(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    path = root / "artifacts/jobs/jobs.sqlite3"
    with JobStore(path, root=root) as store:
        store.initialize()
    (path.parent / ".jobs.lock").write_text("legacy", encoding="utf-8")
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    replacement_done = context.Event()
    results = context.Queue()
    stale = context.Process(
        target=_paused_write_writer,
        args=(str(root), str(path), ready, replacement_done, results),
    )
    replacement = context.Process(
        target=_lock_path_replacement_writer,
        args=(str(root), str(path), ready, replacement_done, results),
    )
    stale.start()
    replacement.start()
    stale.join(15)
    replacement.join(15)
    assert stale.exitcode == replacement.exitcode == 0
    messages = {results.get(timeout=2), results.get(timeout=2)}
    assert messages == {"paused writer success", "replacement success"}
    with JobStore(path, root=root) as store:
        keys = {job.idempotency_key for job in store.list()}
    assert keys == {"stale-writer", "replacement-writer"}


def test_jobs_directory_replacement_rejects_detached_writer(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    path = root / "artifacts/jobs/jobs.sqlite3"
    with JobStore(path, root=root) as store:
        store.initialize()
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    replacement_done = context.Event()
    results = context.Queue()
    stale = context.Process(
        target=_paused_write_writer,
        args=(str(root), str(path), ready, replacement_done, results),
    )
    replacement = context.Process(
        target=_directory_replacement_writer,
        args=(str(root), str(path), ready, replacement_done, results),
    )
    stale.start()
    replacement.start()
    stale.join(15)
    replacement.join(15)
    assert stale.exitcode == replacement.exitcode == 0
    messages = {results.get(timeout=2), results.get(timeout=2)}
    assert "replacement success" in messages
    assert any("jobs directory identity changed" in message for message in messages)
    with JobStore(path, root=root) as store:
        keys = {job.idempotency_key for job in store.list()}
    assert keys == {"visible-writer"}


def test_clean_closed_wal_database_is_securely_converted(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    path = root / "artifacts/jobs/jobs.sqlite3"
    with JobStore(path, root=root) as store:
        store.initialize()
        store.enqueue(JobType.RESEARCH_LAB_V0, "retained-before-wal")
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    assert path.read_bytes()[18:20] == b"\x02\x02"
    assert not (path.parent / f"{path.name}-wal").exists()

    with JobStore(path, root=root) as store:
        store.initialize()
        assert store.list()[0].idempotency_key == "retained-before-wal"
    assert path.read_bytes()[18:20] == b"\x01\x01"
    assert not list(path.parent.glob(".jobs-convert-*"))


def test_active_wal_database_fails_with_checkpoint_instruction(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    path = root / "artifacts/jobs/jobs.sqlite3"
    with JobStore(path, root=root) as store:
        store.initialize()
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        connection.execute("CREATE TABLE active_wal_probe(value INTEGER)")
        connection.execute("INSERT INTO active_wal_probe VALUES (1)")
        connection.commit()
        assert (path.parent / f"{path.name}-wal").stat().st_size > 0
        with JobStore(path, root=root) as store:
            with pytest.raises(RuntimeError, match="close all SQLite users.*wal_checkpoint"):
                store.initialize()
    finally:
        connection.close()


def test_schema_identity_and_idempotency(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.enqueue(JobType.RESEARCH_LAB_V0, "same")
    second = store.enqueue(JobType.RESEARCH_LAB_V0, "same", {"different": True})
    assert first == second
    assert first.payload == {}
    with sqlite3.connect(store.path) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE jobs SET idempotency_key = 'changed' WHERE job_id = ?", (first.job_id,)
            )


def test_claim_is_atomic_across_connections(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.enqueue(JobType.RESEARCH_LAB_V0, "one", due_at=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(pool.map(lambda owner: store.claim(owner, now=NOW), ("a", "b")))
    assert sum(job is not None for job in claimed) == 1
    assert next(job for job in claimed if job is not None).attempt_count == 1


def test_failure_is_retained_and_retries_are_bounded(tmp_path: Path) -> None:
    store = _store(tmp_path)
    queued = store.enqueue(
        JobType.RESEARCH_LAB_V0, "retry", due_at=NOW, max_attempts=2, timeout_seconds=1
    )
    first = store.claim("worker", now=NOW)
    assert first is not None
    retry = store.fail(first.job_id, "worker", "first failure", now=NOW, backoff_seconds=2)
    assert retry.state is JobState.QUEUED and retry.error == "first failure"
    assert store.claim("worker", now=NOW + timedelta(seconds=1)) is None
    second = store.claim("worker", now=NOW + timedelta(seconds=2))
    assert second is not None
    failed = store.fail(second.job_id, "worker", "final failure", now=NOW + timedelta(seconds=2))
    assert failed.state is JobState.FAILED and failed.attempt_count == 2
    assert failed.error == "final failure" and failed.finished_at is not None
    assert store.claim("worker", now=NOW + timedelta(days=1)) is None
    assert store.get(queued.job_id) == failed


def test_recurring_occurrences_have_deterministic_keys(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_schedule("daily-lab", JobType.RESEARCH_LAB_V0, 60, NOW)
    occurrences = store.materialize_due(now=NOW + timedelta(seconds=120))
    assert [job.due_at for job in occurrences] == [
        NOW,
        NOW + timedelta(seconds=60),
        NOW + timedelta(seconds=120),
    ]
    assert [job.idempotency_key for job in occurrences] == [
        f"schedule:daily-lab:{job.due_at.isoformat()}" for job in occurrences
    ]
    assert store.materialize_due(now=NOW + timedelta(seconds=120)) == []


@pytest.mark.parametrize("limit", [-100, -1, 0, 1001, 10_000])
def test_list_limit_is_bounded(tmp_path: Path, limit: int) -> None:
    store = _store(tmp_path)
    with pytest.raises(ValueError, match="between 1 and 1000"):
        store.list(limit=limit)


@pytest.mark.parametrize("limit", ["-1", "0", "1001"])
def test_cli_rejects_unbounded_list_limits(limit: str) -> None:
    with pytest.raises(SystemExit):
        jobs_cli.parser().parse_args(["list", "--limit", limit])


def test_fixed_command_safe_environment_and_verified_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    sandbox = _sandbox(root, monkeypatch)
    response, result_path = _lab_artifacts(root)
    calls: list[tuple[list[str], dict[str, Any]]] = []
    monkeypatch.setenv("SHOULD_NOT_LEAK", "secret")

    def popen(command: list[str], **kwargs: Any) -> FakeProcess:
        calls.append((command, kwargs))
        return FakeProcess(json.dumps(response))

    store = _store(root)
    queued = store.enqueue(JobType.RESEARCH_LAB_V0, "lab")
    finished = Worker(store, root=root, owner="test", popen=popen).run_once()
    assert finished is not None and finished.state is JobState.SUCCEEDED
    assert finished.result_digest == hashlib.sha256(result_path.read_bytes()).hexdigest()
    assert finished.result_reused is True
    command, kwargs = calls[0]
    assert command[:3] == [str(sandbox), "-p", runner.SANDBOX_PROFILE]
    assert command[-1] == str(root / "scripts/run_research_lab_v0.py")
    assert kwargs["start_new_session"] is True and "shell" not in kwargs
    assert kwargs["env"]["TIOS_AI_MODE"] == "mock"
    assert "SHOULD_NOT_LEAK" not in kwargs["env"]
    assert set(kwargs["env"]) == {
        "HOME",
        "LANG",
        "PATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONHASHSEED",
        "PYTHONNOUSERSITE",
        "TIOS_AI_MODE",
        "TMPDIR",
        "TZ",
    }
    assert store.get(queued.job_id) == finished
    assert {member.value for member in JobType} == {
        "RESEARCH_LAB_V0",
        "DATA_QUALITY",
        "REPORT_REFRESH",
    }


@pytest.mark.parametrize("system", ["Linux", "Windows", "FreeBSD"])
def test_execution_fails_closed_without_network_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, system: str
) -> None:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/run_research_lab_v0.py").write_text("# fake\n", encoding="utf-8")
    monkeypatch.setattr(runner.platform, "system", lambda: system)
    called = False

    def popen(*_: Any, **__: Any) -> FakeProcess:
        nonlocal called
        called = True
        return FakeProcess()

    store = _store(root)
    store.enqueue(JobType.RESEARCH_LAB_V0, "isolated")
    failed = Worker(store, root=root, popen=popen).run_once()
    assert failed is not None and failed.state is JobState.FAILED
    assert "network isolation is unavailable" in (failed.error or "")
    assert not called


def test_queued_and_running_cancellation_terminate_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    store = _store(root)
    queued = store.enqueue(JobType.RESEARCH_LAB_V0, "queued")
    cancelled = store.cancel(queued.job_id)
    assert cancelled.state is JobState.CANCELLED and cancelled.cancel_requested

    running = store.enqueue(JobType.RESEARCH_LAB_V0, "running")
    process = FakeProcess(running=True)
    signals: list[int] = []

    def popen(*_: Any, **__: Any) -> FakeProcess:
        store.cancel(running.job_id)
        return process

    def kill_group(pid: int, signum: int) -> None:
        assert pid == process.pid
        signals.append(signum)
        process.returncode = -signum

    monkeypatch.setattr(runner.os, "killpg", kill_group)
    result = Worker(store, root=root, owner="worker", popen=popen).run_once()
    assert result is not None and result.state is JobState.CANCELLED
    assert result.cancel_requested and result.result_artifact_ref is None
    assert signals == [signal.SIGTERM]


def test_completion_cancellation_race_records_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    response, _ = _lab_artifacts(root)
    store = _store(root)
    queued = store.enqueue(JobType.RESEARCH_LAB_V0, "race")

    def popen(*_: Any, **__: Any) -> FakeProcess:
        store.cancel(queued.job_id)
        return FakeProcess(json.dumps(response))

    result = Worker(store, root=root, owner="worker", popen=popen).run_once()
    assert result is not None and result.state is JobState.CANCELLED
    assert result.result_digest is None and result.error == "cancelled by operator"


def test_timeout_kills_process_group_and_retains_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    store = _store(root)
    store.enqueue(JobType.RESEARCH_LAB_V0, "timeout", timeout_seconds=1)
    process = FakeProcess(running=True)
    signals: list[int] = []
    ticks = iter((0.0, 0.0, 2.0))
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(runner.time, "sleep", lambda _: None)

    def kill_group(_: int, signum: int) -> None:
        signals.append(signum)
        process.returncode = -signum

    monkeypatch.setattr(runner.os, "killpg", kill_group)
    result = Worker(store, root=root, popen=lambda *_args, **_kwargs: process).run_once()
    assert result is not None and result.state is JobState.FAILED
    assert "JobTimedOut" in (result.error or "")
    assert signals == [signal.SIGTERM] and process.poll() is not None


def test_artifact_mutation_and_unconfined_identity_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    response, result_path = _lab_artifacts(root)
    original = runner._read_descriptor  # noqa: SLF001
    reads = 0

    def mutating(descriptor: int, heartbeat: Any) -> bytes:
        nonlocal reads
        data = original(descriptor, heartbeat)
        if reads == 0:
            reads += 1
            result_path.write_bytes(data + b" ")
        return data

    monkeypatch.setattr(runner, "_read_descriptor", mutating)
    store = _store(root)
    store.enqueue(JobType.RESEARCH_LAB_V0, "mutation")
    failed = Worker(
        store,
        root=root,
        popen=lambda *_args, **_kwargs: FakeProcess(json.dumps(response)),
    ).run_once()
    assert failed is not None and failed.state is JobState.FAILED
    assert "changed while being verified" in (failed.error or "")

    monkeypatch.setattr(runner, "_read_descriptor", original)
    store.enqueue(JobType.RESEARCH_LAB_V0, "escape")
    escaped = Worker(
        store,
        root=root,
        popen=lambda *_args, **_kwargs: FakeProcess(
            json.dumps({"status": "COMPLETED", "lab_id": "../escape"})
        ),
    ).run_once()
    assert escaped is not None and escaped.state is JobState.FAILED
    assert "invalid artifact identity" in (escaped.error or "")


def test_artifact_directory_swap_never_reads_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    response, _ = _lab_artifacts(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "lab_run.json").write_text(json.dumps(response), encoding="utf-8")
    (outside / "manifest.json").write_text("{}", encoding="utf-8")
    original = runner._open_artifact_directory  # noqa: SLF001
    swapped = False

    def swap_after_open(repo: Path, *components: str) -> int:
        nonlocal swapped
        descriptor = original(repo, *components)
        if not swapped and components[-1] == "LAB-TEST":
            batch = root / "artifacts/research_lab/v0/LAB-TEST"
            batch.rename(root / "artifacts/research_lab/v0/LAB-HELD")
            batch.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptor

    monkeypatch.setattr(runner, "_open_artifact_directory", swap_after_open)
    store = _store(root)
    store.enqueue(JobType.RESEARCH_LAB_V0, "swap")
    failed = Worker(
        store,
        root=root,
        popen=lambda *_args, **_kwargs: FakeProcess(json.dumps(response)),
    ).run_once()
    assert failed is not None and failed.state is JobState.FAILED
    assert failed.result_artifact_ref is None


def test_artifact_file_swap_never_follows_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    response, _ = _lab_artifacts(root)
    outside = tmp_path / "outside-result.json"
    outside.write_text(json.dumps(response), encoding="utf-8")
    original = runner._stable_bytes_at  # noqa: SLF001
    swapped = False

    def swap_file(parent_fd: int, name: str, heartbeat: Any) -> tuple[bytes, str]:
        nonlocal swapped
        if name == "lab_run.json" and not swapped:
            os.unlink(name, dir_fd=parent_fd)
            os.symlink(outside, name, dir_fd=parent_fd)
            swapped = True
        return original(parent_fd, name, heartbeat)

    monkeypatch.setattr(runner, "_stable_bytes_at", swap_file)
    store = _store(root)
    store.enqueue(JobType.RESEARCH_LAB_V0, "file-swap")
    failed = Worker(
        store,
        root=root,
        popen=lambda *_args, **_kwargs: FakeProcess(json.dumps(response)),
    ).run_once()
    assert failed is not None and failed.state is JobState.FAILED
    assert outside.read_text(encoding="utf-8") == json.dumps(response)


def test_lease_renews_during_slow_artifact_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    response, _ = _lab_artifacts(root)
    store = _store(root)
    clock = [NOW]
    ticks = iter(float(index) for index in range(100))
    monkeypatch.setattr(store_module, "utc_now", lambda: clock[0])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    queued = store.enqueue(JobType.RESEARCH_LAB_V0, "slow", timeout_seconds=20)
    original = runner._read_descriptor  # noqa: SLF001
    reclaim_attempts: list[object] = []

    def slow_read(descriptor: int, heartbeat: Any) -> bytes:
        clock[0] = NOW + timedelta(seconds=4)
        payload = original(descriptor, heartbeat)
        reclaim_attempts.append(
            store.claim("contender", now=NOW + timedelta(seconds=6), lease_seconds=1)
        )
        return payload

    monkeypatch.setattr(runner, "_read_descriptor", slow_read)
    finished = Worker(
        store,
        root=root,
        owner="worker",
        popen=lambda *_args, **_kwargs: FakeProcess(json.dumps(response)),
        lease_seconds=1,
    ).run_once()
    assert finished is not None and finished.state is JobState.SUCCEEDED
    assert reclaim_attempts and all(attempt is None for attempt in reclaim_attempts)
    assert store.get(queued.job_id) == finished


def test_lease_renews_while_subprocess_is_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    _sandbox(root, monkeypatch)
    response, _ = _lab_artifacts(root)
    store = _store(root)
    clock = [NOW]
    ticks = iter(float(index) for index in range(100))
    monkeypatch.setattr(store_module, "utc_now", lambda: clock[0])
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(ticks))
    queued = store.enqueue(JobType.RESEARCH_LAB_V0, "waiting", timeout_seconds=20)
    process = FakeProcess(json.dumps(response), running=True)
    polls = 0
    reclaim_attempts: list[object] = []

    def poll() -> int | None:
        nonlocal polls
        polls += 1
        if polls == 4:
            process.returncode = 0
        return process.returncode

    def advance(_: float) -> None:
        clock[0] += timedelta(seconds=2)
        if clock[0] == NOW + timedelta(seconds=6):
            reclaim_attempts.append(store.claim("contender", now=clock[0], lease_seconds=1))

    monkeypatch.setattr(process, "poll", poll)
    monkeypatch.setattr(runner.time, "sleep", advance)
    finished = Worker(
        store,
        root=root,
        owner="worker",
        popen=lambda *_args, **_kwargs: process,
        lease_seconds=1,
    ).run_once()
    assert finished is not None and finished.state is JobState.SUCCEEDED
    assert reclaim_attempts == [None]
    assert store.get(queued.job_id) == finished


def test_expired_cancelled_lease_is_recovered_as_cancelled(tmp_path: Path) -> None:
    store = _store(tmp_path)
    queued = store.enqueue(
        JobType.RESEARCH_LAB_V0, "recover", due_at=NOW, max_attempts=1, timeout_seconds=1
    )
    claimed = store.claim("gone", now=NOW, lease_seconds=1)
    assert claimed is not None
    store.cancel(queued.job_id, now=NOW)
    assert store.claim("new", now=NOW + timedelta(seconds=32), lease_seconds=1) is None
    retained = store.get(queued.job_id)
    assert retained is not None and retained.state is JobState.CANCELLED
    assert retained.error == "cancelled after worker lease expired"
