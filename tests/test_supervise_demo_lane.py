"""Offline tests for the supervised auto-start wrapper. No lane is ever launched.

`_launch` is monkeypatched in every test, so the real `os.execv` never runs. These prove the three
rails that stand between launchd and the order path: KILL_SWITCH is absolute, the crash-loop guard
bounds restarts, and every supervised start (accepted or refused) is audited in the operator's own
human-decisions ledger. Demo/fake money, execution authority NONE.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.supervise_demo_lane as sup  # noqa: E402

LEDGER_KEYS = {
    "schema_version",
    "decided_at",
    "source",
    "action",
    "idempotency_key",
    "detail",
    "environment",
    "real_money",
}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repo root. monkeypatch.chdir restores the real cwd after main() chdirs."""
    (tmp_path / sup.LANE_DIR).mkdir(parents=True)
    monkeypatch.setattr(sup, "REPO_ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def launched(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def fake_launch() -> int:
        calls.append(sup.LANE_ARGV)
        return 0

    monkeypatch.setattr(sup, "_launch", fake_launch)
    return calls


def ledger(repo: Path) -> list[dict[str, object]]:
    path = repo / sup.AUDIT_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def seed_history(repo: Path, stamps: list[datetime]) -> None:
    (repo / sup.START_HISTORY).write_text(
        json.dumps([stamp.isoformat() for stamp in stamps]), encoding="utf-8"
    )


def test_kill_switch_refuses_and_stays_down(
    repo: Path, launched: list[tuple[str, ...]], capsys: pytest.CaptureFixture[str]
) -> None:
    """Rail 1: a lane the operator stopped is never resurrected by a supervised restart."""
    (repo / sup.KILL_SWITCH).write_text("{}", encoding="utf-8")

    assert sup.main() == sup.REFUSED_STAY_DOWN == 0  # clean exit; KeepAlive keeps it down
    assert launched == []
    assert "KILL_SWITCH" in capsys.readouterr().out

    records = ledger(repo)
    assert len(records) == 1
    assert records[0]["action"] == "SUPERVISED_START"
    assert "refused" in str(records[0]["detail"])
    # A refusal must not consume a crash-loop slot, or repeated stops would wedge the guard.
    assert not (repo / sup.START_HISTORY).exists()


def test_clean_start_launches_the_fixed_argv_and_audits_once(
    repo: Path, launched: list[tuple[str, ...]]
) -> None:
    """Rail 4: the exact documented command, built only from constants."""
    assert sup.main() == 0
    assert launched == [
        (
            "/Users/user/.local/bin/uv",
            "run",
            "python",
            "scripts/demo_eth_lane.py",
            "--activity",
            "--loop",
            "--interval",
            "5m",
        )
    ]

    records = ledger(repo)
    assert len(records) == 1
    assert records[0]["source"] == "launchd_supervisor"
    assert "accepted" in str(records[0]["detail"])


def test_crash_loop_guard_trips_inside_the_window(
    repo: Path, launched: list[tuple[str, ...]], capsys: pytest.CaptureFixture[str]
) -> None:
    """Rail 2: MAX_STARTS starts inside WINDOW refuses the next one, without launching."""
    now = datetime.now(tz=UTC)
    seed_history(repo, [now - timedelta(seconds=30 * n) for n in range(sup.MAX_STARTS)])

    assert sup.main() == sup.REFUSED_STAY_DOWN
    assert launched == []
    assert "crash-loop guard" in capsys.readouterr().out
    assert "refused: crash-loop guard" in str(ledger(repo)[0]["detail"])


def test_starts_outside_the_window_do_not_trip_the_guard(
    repo: Path, launched: list[tuple[str, ...]]
) -> None:
    now = datetime.now(tz=UTC)
    old = now - sup.WINDOW - timedelta(minutes=1)
    seed_history(repo, [old - timedelta(seconds=30 * n) for n in range(sup.MAX_STARTS * 2)])

    assert sup.main() == 0
    assert len(launched) == 1


def test_guard_clearing_path_restores_starting(repo: Path, launched: list[tuple[str, ...]]) -> None:
    """`make lane-supervise-clear-guard` deletes START_HISTORY; that must be enough."""
    now = datetime.now(tz=UTC)
    seed_history(repo, [now for _ in range(sup.MAX_STARTS)])
    assert sup.main() == sup.REFUSED_STAY_DOWN
    assert launched == []

    (repo / sup.START_HISTORY).unlink()  # exactly what the make target does

    assert sup.main() == 0
    assert len(launched) == 1


def test_history_is_bounded_and_written_atomically(
    repo: Path, launched: list[tuple[str, ...]], monkeypatch: pytest.MonkeyPatch
) -> None:
    old = datetime.now(tz=UTC) - sup.WINDOW - timedelta(hours=1)
    seed_history(repo, [old + timedelta(seconds=n) for n in range(sup.MAX_HISTORY * 3)])

    replaced: list[tuple[str, str]] = []
    real_replace = sup.os.replace

    def spy(source: Any, target: Any) -> None:
        replaced.append((str(source), str(target)))
        real_replace(source, target)

    monkeypatch.setattr(sup.os, "replace", spy)

    assert sup.main() == 0
    stamps = json.loads((repo / sup.START_HISTORY).read_text(encoding="utf-8"))
    assert len(stamps) == sup.MAX_HISTORY
    assert len(replaced) == 1
    assert ".tmp." in replaced[0][0] and replaced[0][1].endswith("supervisor_starts.json")
    assert not list((repo / sup.LANE_DIR).glob("*.tmp.*"))


def test_corrupt_history_does_not_block_a_start(
    repo: Path, launched: list[tuple[str, ...]]
) -> None:
    (repo / sup.START_HISTORY).write_text("{not json", encoding="utf-8")
    assert sup.main() == 0
    assert len(launched) == 1


def test_audit_record_matches_the_ledger_shape_and_leaks_nothing(
    repo: Path, launched: list[tuple[str, ...]]
) -> None:
    """Same keys and types the dashboard writes, so the operator's audit trail stays one stream."""
    assert sup.main() == 0
    record = ledger(repo)[0]

    assert set(record) == LEDGER_KEYS
    assert record["schema_version"] == 1
    assert record["environment"] == "VENUE_DEMO"
    assert record["real_money"] is False
    assert isinstance(record["idempotency_key"], str)
    datetime.fromisoformat(str(record["decided_at"]))

    blob = json.dumps(record).lower()
    for marker in ("api_key", "apikey", "secret", "token", "password", "bybit", "/users/"):
        assert marker not in blob


def test_supervisor_source_has_no_credentials_and_a_constant_argv() -> None:
    """The wrapper is the whole trust boundary; read it as data and prove it stays boring."""
    source = Path(sup.__file__).read_text(encoding="utf-8")

    for marker in ("API_KEY", "SECRET", "PASSWORD", "TOKEN", "os.environ", "getenv", "shell=True"):
        assert marker not in source
    assert "urllib" not in source and "requests" not in source and "socket" not in source

    # argv is a module constant of plain strings — nothing derived from input at call time.
    assert isinstance(sup.LANE_ARGV, tuple)
    assert all(isinstance(part, str) for part in sup.LANE_ARGV)
    assert sup.LANE_ARGV[0] == sup.UV_BIN


def test_unrecordable_start_refuses_instead_of_launching_blind(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the start cannot be written to the crash-loop history, refuse rather than launch.

    A start the guard cannot count is a start that never contributes to the crash-loop bound, so a
    persistent write failure would otherwise relaunch every ThrottleInterval forever, unbounded.
    """
    launched: list[object] = []
    monkeypatch.setattr(sup, "_launch", lambda: launched.append(1))
    monkeypatch.setattr(
        sup, "_write_history", lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk full"))
    )
    assert sup.main() == sup.REFUSED_STAY_DOWN
    assert launched == []


def test_unauditable_start_refuses_instead_of_starting_invisibly(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the audit record cannot be written, refuse: an unattended start must never be invisible.

    The operator-facing claim is a guarantee, not best effort — so the failure mode is 'does not
    trade', never 'trades with no trace'.
    """
    launched: list[object] = []
    monkeypatch.setattr(sup, "_launch", lambda: launched.append(1))
    monkeypatch.setattr(sup, "_audit", lambda _detail: False)
    assert sup.main() == sup.REFUSED_STAY_DOWN
    assert launched == []


def test_audit_reports_whether_the_record_landed(repo: Path) -> None:
    """_audit's return value is the signal the accept path gates on, so it must be truthful."""
    assert sup._audit("accepted: probe") is True
    assert sup.AUDIT_PATH.exists() or (repo / sup.AUDIT_PATH).exists()
