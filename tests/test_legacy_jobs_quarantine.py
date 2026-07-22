from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest

from tios.services.jobs import store as store_module
from tios.services.jobs.store import (
    LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON,
    LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID,
    JobState,
    JobStore,
    JobType,
    LegacyResearchLabV0AuditPublicationError,
    LegacyResearchLabV0QuarantineRefusal,
)


def _store(root: Path, *, version: int = 4) -> JobStore:
    root.mkdir(parents=True, exist_ok=True)
    result = JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root)
    if version == 4:
        result.initialize()
    else:
        with result._connect(create=True) as connection:  # noqa: SLF001
            connection.execute("BEGIN IMMEDIATE")
            for migration_version in range(version):
                store_module._apply_migration(  # noqa: SLF001
                    connection,
                    store_module._MIGRATIONS[migration_version],  # noqa: SLF001
                    migration_version + 1,
                )
            connection.commit()
    return result


def _target(
    store: JobStore,
    *,
    job_type: str = "RESEARCH_LAB_V0",
    payload_json: str = "{}",
    interval_seconds: int = 21_600,
    max_attempts: int = 1,
    timeout_seconds: int = 3_600,
) -> None:
    with store._connect() as connection:  # noqa: SLF001
        connection.execute(
            """INSERT INTO schedules (
                   schedule_id, job_type, payload_json, interval_seconds, next_due,
                   max_attempts, timeout_seconds
               ) VALUES (?, ?, ?, ?, '2026-07-22T00:00:00+00:00', ?, ?)""",
            (
                LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID,
                job_type,
                payload_json,
                interval_seconds,
                max_attempts,
                timeout_seconds,
            ),
        )


def _apply(store: JobStore):  # type: ignore[no-untyped-def]
    plan = store.plan_legacy_research_lab_v0_quarantine()
    return store.apply_legacy_research_lab_v0_quarantine(
        expected_plan_sha256=plan.plan_sha256,
        expected_job_ids=plan.queued_job_ids,
    )


def _database_rows(store: JobStore) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with store._connect(write=False) as connection:  # noqa: SLF001
        jobs = [tuple(row) for row in connection.execute("SELECT * FROM jobs ORDER BY job_id")]
        schedules = [
            tuple(row) for row in connection.execute("SELECT * FROM schedules ORDER BY schedule_id")
        ]
    return jobs, schedules


def test_v2_plan_is_byte_and_mtime_read_only_and_canonical(tmp_path: Path) -> None:
    with _store(tmp_path / "repo", version=2) as store:
        _target(store)
        job = store.enqueue(JobType.RESEARCH_LAB_V0, "legacy-new")
        before = store.path.read_bytes()
        before_mtime = store.path.stat().st_mtime_ns

        first = store.plan_legacy_research_lab_v0_quarantine()
        second = store.plan_legacy_research_lab_v0_quarantine()

        assert store.path.read_bytes() == before
        assert store.path.stat().st_mtime_ns == before_mtime
        assert first == second
        assert first.db_schema_before == 2
        assert first.schedule is not None
        assert first.schedule["enabled"] is True
        assert first.schedule["enabled_source"] == "implicit_v2"
        assert first.queued_job_ids == (job.job_id,)
        assert first.queued_count == 1
        assert first.new_count == 1
        assert first.retry_count == 0
        assert first.blockers == ()


def test_numbered_v4_migration_and_exact_outbox_schema(tmp_path: Path) -> None:
    with _store(tmp_path / "repo", version=3) as store:
        _target(store)
        assert store.plan_legacy_research_lab_v0_quarantine().db_schema_before == 3
        store.initialize()
        assert store.plan_legacy_research_lab_v0_quarantine().db_schema_before == 4
        with store._connect(write=False) as connection:  # noqa: SLF001
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
            assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 4
            sql = connection.execute(
                """SELECT sql FROM sqlite_master WHERE type = 'table'
                       AND name = 'legacy_research_lab_v0_quarantine_audit_outbox'"""
            ).fetchone()[0]
        assert "temporary_name TEXT NOT NULL UNIQUE" in sql


def test_v4_plan_refuses_noncanonical_outbox_schema(tmp_path: Path) -> None:
    with _store(tmp_path / "repo", version=3) as store:
        _target(store)
        with store._connect() as connection:  # noqa: SLF001
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """CREATE TABLE legacy_research_lab_v0_quarantine_audit_outbox (
                       operation_key INTEGER
                   )"""
            )
            connection.execute("UPDATE schema_version SET version = 4")
            connection.execute("PRAGMA user_version = 4")
            connection.commit()
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="definition is not exact"):
            store.plan_legacy_research_lab_v0_quarantine()


@pytest.mark.parametrize(
    "unexpected_sql",
    [
        """CREATE TRIGGER malicious_outbox_insert
               AFTER INSERT ON legacy_research_lab_v0_quarantine_audit_outbox
               BEGIN UPDATE schedules SET enabled = 1; END""",
        "CREATE VIEW malicious_jobs_view AS SELECT * FROM jobs",
        "CREATE INDEX malicious_schedule_index ON schedules(next_due)",
    ],
)
def test_v4_plan_refuses_unexpected_master_objects(tmp_path: Path, unexpected_sql: str) -> None:
    with _store(tmp_path / unexpected_sql.split()[1]) as store:
        _target(store)
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(unexpected_sql)
        before = store.path.read_bytes()
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="sqlite_master"):
            store.plan_legacy_research_lab_v0_quarantine()
        assert store.path.read_bytes() == before


def test_apply_rolls_back_malicious_after_outbox_insert_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _store(tmp_path / "repo", version=3) as store:
        _target(store)
        store.enqueue(JobType.RESEARCH_LAB_V0, "queued")
        plan = store.plan_legacy_research_lab_v0_quarantine()
        before = store.path.read_bytes()
        original = store_module._quarantine_audit_outbox_row  # noqa: SLF001
        injected = False

        def inject_after_v4_validation(
            connection: sqlite3.Connection,
        ) -> sqlite3.Row | None:
            nonlocal injected
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version == 4 and not injected:
                connection.execute(
                    """CREATE TRIGGER malicious_after_outbox_insert
                           AFTER INSERT ON legacy_research_lab_v0_quarantine_audit_outbox
                           BEGIN UPDATE schedules SET enabled = 1
                               WHERE schedule_id =
                                   's2-production-offline-research-lab-v0-every-6h-v1';
                           END"""
                )
                injected = True
            return original(connection)

        monkeypatch.setattr(
            store_module, "_quarantine_audit_outbox_row", inject_after_v4_validation
        )
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="sqlite_master"):
            store.apply_legacy_research_lab_v0_quarantine(
                expected_plan_sha256=plan.plan_sha256,
                expected_job_ids=plan.queued_job_ids,
            )
        assert injected is True
        assert store.path.read_bytes() == before
        assert store.plan_legacy_research_lab_v0_quarantine() == plan


def test_v2_apply_atomically_migrates_disables_and_cancels_fresh_and_retry(
    tmp_path: Path,
) -> None:
    with _store(tmp_path / "repo", version=2) as store:
        _target(store)
        fresh = store.enqueue(JobType.RESEARCH_LAB_V0, "fresh")
        retry = store.enqueue(JobType.RESEARCH_LAB_V0, "retry")
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                "UPDATE jobs SET attempt_count = 1, error = 'old failure' WHERE job_id = ?",
                (retry.job_id,),
            )

        plan = store.plan_legacy_research_lab_v0_quarantine()
        assert plan.new_count == 1
        assert plan.retry_count == 1
        result = _apply(store)

        assert result.status == "APPLIED"
        assert result.cancelled_job_ids == tuple(sorted((fresh.job_id, retry.job_id)))
        assert result.audit_artifact_ref is not None
        audit = store.root / result.audit_artifact_ref
        assert audit.is_file()
        assert json.loads(audit.read_text())["plan"]["plan_sha256"] == plan.plan_sha256
        with store._connect(write=False) as connection:  # noqa: SLF001
            assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
            assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 4
            assert (
                connection.execute(
                    "SELECT enabled FROM schedules WHERE schedule_id = ?",
                    (LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID,),
                ).fetchone()[0]
                == 0
            )
            rows = {
                row["job_id"]: row for row in connection.execute("SELECT * FROM jobs").fetchall()
            }
        assert rows[fresh.job_id]["state"] == JobState.CANCELLED
        assert rows[fresh.job_id]["error"] == LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON
        assert rows[retry.job_id]["error"] == (
            f"old failure\n{LEGACY_RESEARCH_LAB_V0_QUARANTINE_REASON}"
        )
        assert rows[fresh.job_id]["finished_at"] == rows[retry.job_id]["finished_at"]


def test_terminal_results_and_other_job_types_are_preserved_exactly(tmp_path: Path) -> None:
    with _store(tmp_path / "repo") as store:
        _target(store)
        terminal = [
            store.enqueue(JobType.RESEARCH_LAB_V0, f"terminal-{state}")
            for state in ("SUCCEEDED", "FAILED", "CANCELLED")
        ]
        other = store.enqueue(JobType.DATA_QUALITY, "other-queued", {"fixed": True})
        with store._connect() as connection:  # noqa: SLF001
            for job, state in zip(terminal, ("SUCCEEDED", "FAILED", "CANCELLED"), strict=True):
                connection.execute(
                    """UPDATE jobs SET state = ?, finished_at = '2026-07-20T00:00:00+00:00',
                           result_artifact_ref = ?, result_digest = ?, result_reused = 1,
                           cancel_requested = ?, error = ? WHERE job_id = ?""",
                    (
                        state,
                        f"artifacts/fixed/{state}",
                        state.lower(),
                        int(state == "CANCELLED"),
                        f"fixed-{state}",
                        job.job_id,
                    ),
                )
        before, _ = _database_rows(store)
        plan = store.plan_legacy_research_lab_v0_quarantine()
        assert plan.preserved_terminal_counts == {"SUCCEEDED": 1, "FAILED": 1, "CANCELLED": 1}

        _apply(store)
        after, _ = _database_rows(store)

        assert after == before
        assert store.get(other.job_id) == other


@pytest.mark.parametrize(
    ("overrides", "blocker"),
    [
        ({"job_type": "DATA_QUALITY"}, "job_type"),
        ({"payload_json": '{"unexpected":true}'}, "payload"),
        ({"interval_seconds": 60}, "interval_seconds"),
        ({"max_attempts": 2}, "max_attempts"),
        ({"timeout_seconds": 60}, "timeout_seconds"),
    ],
)
def test_target_metadata_drift_refuses(
    tmp_path: Path, overrides: dict[str, object], blocker: str
) -> None:
    with _store(tmp_path / blocker) as store:
        _target(store, **overrides)  # type: ignore[arg-type]
        plan = store.plan_legacy_research_lab_v0_quarantine()
        assert any(blocker in item for item in plan.blockers)
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="blockers"):
            _apply(store)


def test_missing_target_extra_schedule_and_running_job_refuse(tmp_path: Path) -> None:
    with _store(tmp_path / "missing") as store:
        plan = store.plan_legacy_research_lab_v0_quarantine()
        assert any("missing" in blocker for blocker in plan.blockers)

    with _store(tmp_path / "extra") as store:
        _target(store)
        store.add_schedule(
            "unexpected-research", JobType.RESEARCH_LAB_V0, 60, store_module.utc_now()
        )
        plan = store.plan_legacy_research_lab_v0_quarantine()
        assert any("unexpected RESEARCH_LAB_V0 schedules" in blocker for blocker in plan.blockers)

    with _store(tmp_path / "running") as store:
        _target(store)
        job = store.enqueue(JobType.RESEARCH_LAB_V0, "running")
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                """UPDATE jobs SET state = 'RUNNING', attempt_count = 1,
                       lease_owner = 'worker', lease_expires_at = '2099-01-01T00:00:00+00:00'
                       WHERE job_id = ?""",
                (job.job_id,),
            )
        before = store.path.read_bytes()
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="RUNNING"):
            _apply(store)
        assert store.path.read_bytes() == before


def test_malformed_or_unsupported_schema_refuses(tmp_path: Path) -> None:
    with _store(tmp_path / "unsupported", version=2) as store:
        with store._connect() as connection:  # noqa: SLF001
            connection.execute("PRAGMA user_version = 1")
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="disagree"):
            store.plan_legacy_research_lab_v0_quarantine()

    root = tmp_path / "malformed"
    path = root / "artifacts/jobs/jobs.sqlite3"
    path.parent.mkdir(parents=True)
    sqlite3.connect(path).close()
    with JobStore(path, root=root) as store:
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="malformed"):
            store.plan_legacy_research_lab_v0_quarantine()


def test_stale_digest_or_job_ids_refuse_without_writes(tmp_path: Path) -> None:
    with _store(tmp_path / "repo") as store:
        _target(store)
        first = store.enqueue(JobType.RESEARCH_LAB_V0, "first")
        plan = store.plan_legacy_research_lab_v0_quarantine()
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="job IDs"):
            store.apply_legacy_research_lab_v0_quarantine(
                expected_plan_sha256=plan.plan_sha256,
                expected_job_ids=(),
            )
        store.enqueue(JobType.RESEARCH_LAB_V0, "raced")
        before = store.path.read_bytes()
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="digest changed"):
            store.apply_legacy_research_lab_v0_quarantine(
                expected_plan_sha256=plan.plan_sha256,
                expected_job_ids=(first.job_id,),
            )
        assert store.path.read_bytes() == before


def test_interrupted_v2_migration_rolls_back_database_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _store(tmp_path / "repo", version=2) as store:
        _target(store)
        store.enqueue(JobType.RESEARCH_LAB_V0, "queued")
        plan = store.plan_legacy_research_lab_v0_quarantine()
        before = store.path.read_bytes()
        original = store_module._apply_migration  # noqa: SLF001

        def interrupted(
            connection: sqlite3.Connection, statements: tuple[str, ...], version: int
        ) -> None:
            if version == 4:
                connection.execute(statements[0])
                raise RuntimeError("interrupted migration")
            original(connection, statements, version)

        monkeypatch.setattr(store_module, "_apply_migration", interrupted)
        with pytest.raises(RuntimeError, match="interrupted migration"):
            store.apply_legacy_research_lab_v0_quarantine(
                expected_plan_sha256=plan.plan_sha256,
                expected_job_ids=plan.queued_job_ids,
            )
        assert store.path.read_bytes() == before


def test_v3_apply_is_idempotent_without_second_database_rewrite(tmp_path: Path) -> None:
    with _store(tmp_path / "repo", version=3) as store:
        _target(store)
        store.enqueue(JobType.RESEARCH_LAB_V0, "queued")
        _apply(store)
        current = store.plan_legacy_research_lab_v0_quarantine()
        before = store.path.read_bytes()
        before_mtime = store.path.stat().st_mtime_ns

        result = store.apply_legacy_research_lab_v0_quarantine(
            expected_plan_sha256=current.plan_sha256,
            expected_job_ids=(),
        )

        assert result.status == "ALREADY_QUARANTINED"
        assert store.path.read_bytes() == before
        assert store.path.stat().st_mtime_ns == before_mtime


def test_apply_does_not_claim_or_materialize_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _store(tmp_path / "repo") as store:
        _target(store)
        store.enqueue(JobType.RESEARCH_LAB_V0, "queued")

        def forbidden(*args: object, **kwargs: object) -> None:
            raise AssertionError("execution API must not be called")

        monkeypatch.setattr(JobStore, "claim", forbidden)
        monkeypatch.setattr(JobStore, "materialize_due", forbidden)
        assert _apply(store).status == "APPLIED"


def test_audit_failure_reports_committed_state_and_supports_exact_repair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _store(tmp_path / "repo") as store:
        _target(store)
        job = store.enqueue(JobType.RESEARCH_LAB_V0, "queued")
        original = store._publish_legacy_quarantine_audit  # noqa: SLF001
        monkeypatch.setattr(
            store,
            "_publish_legacy_quarantine_audit",
            lambda *_: (_ for _ in ()).throw(OSError("audit disk unavailable")),
        )
        with pytest.raises(LegacyResearchLabV0AuditPublicationError) as caught:
            _apply(store)
        assert store.get(job.job_id).state == JobState.CANCELLED  # type: ignore[union-attr]
        assert "commit succeeded" in str(caught.value)
        monkeypatch.setattr(store, "_publish_legacy_quarantine_audit", original)
        repaired = store.repair_legacy_research_lab_v0_quarantine_audit(
            expected_audit_sha256=caught.value.result.audit_sha256 or "",
            expected_plan_sha256=caught.value.result.plan.plan_sha256,
        )
        assert repaired.status == "AUDIT_REPAIRED"
        assert repaired.audit_publication_state == "PUBLISHED"
        assert (store.root / caught.value.audit_artifact_ref).read_bytes() == (
            caught.value.audit_payload
        )


def _leave_committed_audit_pending(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> LegacyResearchLabV0AuditPublicationError:
    with _store(root) as store:
        _target(store)
        store.enqueue(JobType.RESEARCH_LAB_V0, "pending-audit")
        with monkeypatch.context() as scoped:
            scoped.setattr(
                store,
                "_publish_legacy_quarantine_audit",
                lambda *_: (_ for _ in ()).throw(OSError("simulated crash after DB commit")),
            )
            with pytest.raises(LegacyResearchLabV0AuditPublicationError) as caught:
                _apply(store)
        with store._connect(write=False) as connection:  # noqa: SLF001
            outbox = connection.execute(
                "SELECT * FROM legacy_research_lab_v0_quarantine_audit_outbox"
            ).fetchone()
        assert outbox is not None
        assert outbox["published_at"] is None
        assert bytes(outbox["payload"]) == caught.value.audit_payload
        assert outbox["temporary_name"] == f".{outbox['artifact_name']}.pending"
        return caught.value


def test_restart_repairs_durable_outbox_and_already_quarantined_surfaces_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    failure = _leave_committed_audit_pending(root, monkeypatch)
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="audit digest changed"):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256="0" * 64,
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
        current = restarted.plan_legacy_research_lab_v0_quarantine()
        result = restarted.apply_legacy_research_lab_v0_quarantine(
            expected_plan_sha256=current.plan_sha256,
            expected_job_ids=(),
        )
        assert result.status == "ALREADY_QUARANTINED"
        assert result.audit_sha256 == failure.result.audit_sha256
        assert result.audit_publication_state == "PUBLISHED"
        with restarted._connect(write=False) as connection:  # noqa: SLF001
            published_at = connection.execute(
                "SELECT published_at FROM legacy_research_lab_v0_quarantine_audit_outbox"
            ).fetchone()[0]
        assert published_at is not None


def test_repair_rolls_back_malicious_after_published_update_trigger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    failure = _leave_committed_audit_pending(root, monkeypatch)
    database = root / "artifacts/jobs/jobs.sqlite3"
    before = database.read_bytes()
    with JobStore(database, root=root) as restarted:
        original = store_module._quarantine_audit_outbox_row  # noqa: SLF001
        calls = 0

        def inject_before_update(connection: sqlite3.Connection) -> sqlite3.Row | None:
            nonlocal calls
            calls += 1
            if calls == 2:
                connection.execute(
                    """CREATE TRIGGER malicious_after_published_update
                           AFTER UPDATE OF published_at
                           ON legacy_research_lab_v0_quarantine_audit_outbox
                           BEGIN UPDATE jobs SET error = 'malicious mutation'
                               WHERE job_type = 'RESEARCH_LAB_V0';
                           END"""
                )
            return original(connection)

        monkeypatch.setattr(store_module, "_quarantine_audit_outbox_row", inject_before_update)
        with pytest.raises(
            LegacyResearchLabV0QuarantineRefusal,
            match="publication acknowledgement caused an operational table mutation",
        ):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
    assert calls >= 2
    assert database.read_bytes() == before
    with JobStore(database, root=root) as check:
        with check._connect(write=False) as connection:  # noqa: SLF001
            row = connection.execute(
                """SELECT published_at, error FROM
                       legacy_research_lab_v0_quarantine_audit_outbox
                       CROSS JOIN jobs WHERE job_type = 'RESEARCH_LAB_V0' LIMIT 1"""
            ).fetchone()
            assert row["published_at"] is None
            assert row["error"] != "malicious mutation"


def _evolve_unrelated_jobs_and_schedules(store: JobStore) -> str:
    job = store.enqueue(JobType.DATA_QUALITY, "legitimate-non-research", {"version": 2})
    store.add_schedule(
        "legitimate-data-quality-schedule",
        JobType.DATA_QUALITY,
        3_600,
        store_module.utc_now(),
        {"scope": "public-data"},
    )
    with store._connect() as connection:  # noqa: SLF001
        connection.execute(
            """UPDATE jobs SET state = 'SUCCEEDED',
                   finished_at = '2026-07-22T00:00:00+00:00',
                   result_artifact_ref = 'artifacts/jobs/non-research-result',
                   result_digest = 'non-research-digest'
                   WHERE job_id = ?""",
            (job.job_id,),
        )
        connection.execute(
            """UPDATE schedules SET next_due = '2030-01-01T00:00:00+00:00'
                   WHERE schedule_id = 'legitimate-data-quality-schedule'"""
        )
    store.enqueue(JobType.REPORT_REFRESH, "legitimate-added-report-refresh")
    return job.job_id


def test_pending_audit_repair_allows_unrelated_job_and_schedule_evolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    failure = _leave_committed_audit_pending(root, monkeypatch)
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        evolved_job_id = _evolve_unrelated_jobs_and_schedules(restarted)
        result = restarted.repair_legacy_research_lab_v0_quarantine_audit(
            expected_audit_sha256=failure.result.audit_sha256 or "",
            expected_plan_sha256=failure.result.plan.plan_sha256,
        )
        assert result.status == "AUDIT_REPAIRED"
        evolved = restarted.get(evolved_job_id)
        assert evolved is not None and evolved.state == JobState.SUCCEEDED
        with restarted._connect(write=False) as connection:  # noqa: SLF001
            assert (
                connection.execute(
                    """SELECT next_due FROM schedules
                           WHERE schedule_id = 'legitimate-data-quality-schedule'"""
                ).fetchone()[0]
                == "2030-01-01T00:00:00+00:00"
            )


def test_published_already_quarantined_allows_unrelated_evolution_idempotently(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    with _store(root) as store:
        _target(store)
        store.enqueue(JobType.RESEARCH_LAB_V0, "quarantined")
        first = _apply(store)
        assert first.audit_publication_state == "PUBLISHED"
        evolved_job_id = _evolve_unrelated_jobs_and_schedules(store)
        current = store.plan_legacy_research_lab_v0_quarantine()
        before = store.path.read_bytes()
        before_mtime = store.path.stat().st_mtime_ns

        repeated = store.apply_legacy_research_lab_v0_quarantine(
            expected_plan_sha256=current.plan_sha256,
            expected_job_ids=(),
        )

        assert repeated.status == "ALREADY_QUARANTINED"
        assert repeated.audit_publication_state == "PUBLISHED"
        assert store.path.read_bytes() == before
        assert store.path.stat().st_mtime_ns == before_mtime
        evolved = store.get(evolved_job_id)
        assert evolved is not None and evolved.state == JobState.SUCCEEDED


@pytest.mark.parametrize("mutation", ["research_job", "target_schedule"])
def test_pending_audit_repair_refuses_quarantined_research_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    root = tmp_path / mutation
    failure = _leave_committed_audit_pending(root, monkeypatch)
    database = root / "artifacts/jobs/jobs.sqlite3"
    with JobStore(database, root=root) as restarted:
        with restarted._connect() as connection:  # noqa: SLF001
            if mutation == "research_job":
                connection.execute(
                    """UPDATE jobs SET error = 'mutated after quarantine'
                           WHERE job_type = 'RESEARCH_LAB_V0'"""
                )
            else:
                connection.execute(
                    """UPDATE schedules SET payload_json = '{"mutated":true}'
                           WHERE schedule_id =
                               's2-production-offline-research-lab-v0-every-6h-v1'"""
                )
        before = database.read_bytes()
        with pytest.raises(
            LegacyResearchLabV0QuarantineRefusal,
            match="persistent research quarantine state",
        ):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
        assert database.read_bytes() == before
        with restarted._connect(write=False) as connection:  # noqa: SLF001
            assert (
                connection.execute(
                    "SELECT published_at FROM legacy_research_lab_v0_quarantine_audit_outbox"
                ).fetchone()[0]
                is None
            )


def test_restart_repair_refuses_partial_final_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    failure = _leave_committed_audit_pending(root, monkeypatch)
    assert failure.result.audit_artifact_ref is not None
    final = root / failure.result.audit_artifact_ref
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_bytes(b"partial")
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        with pytest.raises(RuntimeError, match="content-address collision"):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
        assert final.read_bytes() == b"partial"
        with restarted._connect(write=False) as connection:  # noqa: SLF001
            assert (
                connection.execute(
                    "SELECT published_at FROM legacy_research_lab_v0_quarantine_audit_outbox"
                ).fetchone()[0]
                is None
            )


@pytest.mark.parametrize("entry_kind", ["symlink", "hardlink"])
def test_restart_repair_refuses_final_symlink_or_hardlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    entry_kind: str,
) -> None:
    root = tmp_path / entry_kind
    failure = _leave_committed_audit_pending(root, monkeypatch)
    assert failure.result.audit_artifact_ref is not None
    final = root / failure.result.audit_artifact_ref
    final.parent.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / f"{entry_kind}-outside"
    outside.write_bytes(failure.audit_payload)
    if entry_kind == "symlink":
        final.symlink_to(outside)
    else:
        os.link(outside, final)
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        with pytest.raises((OSError, RuntimeError), match="symlink or hardlink|Too many"):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
    assert outside.read_bytes() == failure.audit_payload


def test_restart_repair_refuses_parent_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    failure = _leave_committed_audit_pending(root, monkeypatch)
    outside = tmp_path / "outside-quarantine"
    outside.mkdir()
    (root / "artifacts/jobs/quarantine").symlink_to(outside, target_is_directory=True)
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        with pytest.raises(OSError):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
    assert list(outside.iterdir()) == []


def test_parent_swap_after_publish_is_detected_and_anchored_cleanup_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    failure = _leave_committed_audit_pending(root, monkeypatch)
    quarantine = root / "artifacts/jobs/quarantine"
    quarantine.mkdir(parents=True)
    detached = root / "artifacts/jobs/quarantine-detached"
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        original = restarted._verify_quarantine_audit_chain  # noqa: SLF001
        calls = 0

        def swap_then_verify(descriptors: tuple[int, ...], names: tuple[str, ...]) -> None:
            nonlocal calls
            calls += 1
            if calls == 4:
                quarantine.rename(detached)
                quarantine.mkdir()
            original(descriptors, names)

        monkeypatch.setattr(restarted, "_verify_quarantine_audit_chain", swap_then_verify)
        with pytest.raises(RuntimeError, match="identity changed"):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
    assert list(quarantine.iterdir()) == []
    assert list(detached.iterdir()) == []


@pytest.mark.parametrize("crash_window", ["pre_link", "post_link_pre_unlink"])
def test_cli_restart_repair_recovers_deterministic_link_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    crash_window: str,
) -> None:
    root = tmp_path / crash_window
    failure = _leave_committed_audit_pending(root, monkeypatch)
    assert failure.result.audit_artifact_ref is not None
    final = root / failure.result.audit_artifact_ref
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.pending"
    temporary.write_bytes(failure.audit_payload)
    if crash_window == "post_link_pre_unlink":
        os.link(temporary, final)
        assert temporary.stat().st_nlink == 2

    cli = _load_cli()
    monkeypatch.setattr(cli, "repository_root", lambda: root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "quarantine",
            "repair-audit",
            "--expect-audit-sha256",
            failure.result.audit_sha256 or "",
            "--expect-plan-sha256",
            failure.result.plan.plan_sha256,
        ],
    )
    cli.main()
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "AUDIT_REPAIRED"
    assert output["audit_publication_state"] == "PUBLISHED"
    assert final.read_bytes() == failure.audit_payload
    assert final.stat().st_nlink == 1
    assert not temporary.exists()


@pytest.mark.parametrize("collision", ["corrupt_temp", "different_inodes"])
def test_restart_repair_refuses_deterministic_temp_collision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    collision: str,
) -> None:
    root = tmp_path / collision
    failure = _leave_committed_audit_pending(root, monkeypatch)
    assert failure.result.audit_artifact_ref is not None
    final = root / failure.result.audit_artifact_ref
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.pending"
    if collision == "corrupt_temp":
        temporary.write_bytes(b"corrupt orphan")
    else:
        temporary.write_bytes(failure.audit_payload)
        final.write_bytes(failure.audit_payload)
    with JobStore(root / "artifacts/jobs/jobs.sqlite3", root=root) as restarted:
        with pytest.raises(RuntimeError, match="collision|symlink or hardlink"):
            restarted.repair_legacy_research_lab_v0_quarantine_audit(
                expected_audit_sha256=failure.result.audit_sha256 or "",
                expected_plan_sha256=failure.result.plan.plan_sha256,
            )
    assert temporary.exists()
    if collision == "different_inodes":
        assert final.exists()


def test_plan_fingerprint_distinguishes_same_visual_text_and_blob(tmp_path: Path) -> None:
    with _store(tmp_path / "repo") as store:
        _target(store)
        job = store.enqueue(JobType.RESEARCH_LAB_V0, "typed-row")
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                "UPDATE jobs SET error = 'same-visual' WHERE job_id = ?", (job.job_id,)
            )
        text_plan = store.plan_legacy_research_lab_v0_quarantine()
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                "UPDATE jobs SET error = CAST(error AS BLOB) WHERE job_id = ?", (job.job_id,)
            )
            assert (
                connection.execute(
                    "SELECT typeof(error) FROM jobs WHERE job_id = ?", (job.job_id,)
                ).fetchone()[0]
                == "blob"
            )
        blob_plan = store.plan_legacy_research_lab_v0_quarantine()
        assert blob_plan.queued_job_ids == text_plan.queued_job_ids
        assert blob_plan.plan_sha256 != text_plan.plan_sha256
        assert blob_plan.research_job_fingerprints != text_plan.research_job_fingerprints


@pytest.mark.parametrize(
    "mutation",
    [
        "payload_json = '{\"mutated\":true}'",
        "due_at = '2027-01-01T00:00:00+00:00'",
        "attempt_count = 1",
        "max_attempts = 2",
        "timeout_seconds = 99",
        "created_at = '2025-01-01T00:00:00+00:00'",
        "error = 'same-id mutation'",
        "result_artifact_ref = 'artifacts/replaced'",
        "result_digest = 'replaced-digest'",
    ],
)
def test_same_job_id_material_mutation_changes_plan_and_refuses_stale_apply(
    tmp_path: Path, mutation: str
) -> None:
    with _store(tmp_path / mutation.split()[0]) as store:
        _target(store)
        job = store.enqueue(JobType.RESEARCH_LAB_V0, "same-id")
        plan = store.plan_legacy_research_lab_v0_quarantine()
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(f"UPDATE jobs SET {mutation} WHERE job_id = ?", (job.job_id,))
        changed = store.plan_legacy_research_lab_v0_quarantine()
        assert changed.queued_job_ids == plan.queued_job_ids
        assert changed.plan_sha256 != plan.plan_sha256
        with pytest.raises(LegacyResearchLabV0QuarantineRefusal, match="digest changed"):
            store.apply_legacy_research_lab_v0_quarantine(
                expected_plan_sha256=plan.plan_sha256,
                expected_job_ids=plan.queued_job_ids,
            )


def test_terminal_evidence_and_non_target_mutations_change_plan_digest(tmp_path: Path) -> None:
    with _store(tmp_path / "repo") as store:
        _target(store)
        terminal = store.enqueue(JobType.RESEARCH_LAB_V0, "terminal")
        other = store.enqueue(JobType.DATA_QUALITY, "other")
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                """UPDATE jobs SET state = 'SUCCEEDED', finished_at = ?,
                       result_artifact_ref = 'artifact-a', result_digest = 'digest-a'
                       WHERE job_id = ?""",
                (store_module._stamp(store_module.utc_now()), terminal.job_id),  # noqa: SLF001
            )
        first = store.plan_legacy_research_lab_v0_quarantine()
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                "UPDATE jobs SET result_digest = 'digest-b' WHERE job_id = ?",
                (terminal.job_id,),
            )
        terminal_changed = store.plan_legacy_research_lab_v0_quarantine()
        assert terminal_changed.plan_sha256 != first.plan_sha256
        assert terminal_changed.terminal_evidence[0]["result_digest"] == "digest-b"
        with store._connect() as connection:  # noqa: SLF001
            connection.execute(
                "UPDATE jobs SET due_at = '2027-01-01T00:00:00+00:00' WHERE job_id = ?",
                (other.job_id,),
            )
        non_target_changed = store.plan_legacy_research_lab_v0_quarantine()
        assert non_target_changed.non_target_jobs_sha256 != (
            terminal_changed.non_target_jobs_sha256
        )
        assert non_target_changed.plan_sha256 != terminal_changed.plan_sha256


def _load_cli() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/quarantine_legacy_research_lab_v0.py"
    spec = importlib.util.spec_from_file_location("legacy_quarantine_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_is_fixed_purpose_and_outputs_canonical_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    with _store(root) as store:
        _target(store)
    cli = _load_cli()
    monkeypatch.setattr(cli, "repository_root", lambda: root)
    monkeypatch.setattr(os, "environ", os.environ.copy())
    parser = cli.parser()
    help_text = parser.format_help()
    assert "--db" not in help_text
    assert "payload" not in help_text
    assert "schedule" not in help_text
    assert "repair-audit" in help_text
    with pytest.raises(SystemExit):
        parser.parse_args(["plan", "--db", "elsewhere.sqlite3"])
    repaired = parser.parse_args(
        [
            "repair-audit",
            "--expect-audit-sha256",
            "a" * 64,
            "--expect-plan-sha256",
            "b" * 64,
        ]
    )
    assert repaired.command == "repair-audit"
    monkeypatch.setattr("sys.argv", ["quarantine", "plan"])
    cli.main()
    output = json.loads(capsys.readouterr().out)
    assert output["schedule"]["schedule_id"] == LEGACY_RESEARCH_LAB_V0_SCHEDULE_ID
    assert len(output["plan_sha256"]) == 64
