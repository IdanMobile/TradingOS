import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_s2_restore_replay import verify_sqlite_restore  # noqa: E402


def test_sqlite_restore_verifies_integrity_and_succeeded_jobs(tmp_path: Path) -> None:
    source = tmp_path / "jobs.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_version(version) VALUES (2)")
        connection.execute("CREATE TABLE schedules (schedule_id TEXT PRIMARY KEY)")
        connection.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, state TEXT NOT NULL)")
        for index in range(3):
            connection.execute(
                "INSERT INTO jobs(job_id, state) VALUES (?, 'SUCCEEDED')", (f"JOB-{index}",)
            )

    result = verify_sqlite_restore(source, tmp_path / "restore.sqlite3")

    assert result["status"] == "PASS"
    assert result["integrity"] == "ok"
    assert result["jobs_by_state"] == {"SUCCEEDED": 3}
    assert result["schema_version"] == 2
