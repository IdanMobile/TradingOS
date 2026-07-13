"""Persistent prospective status stays bounded, atomic, and order-inert."""

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_prospective_liquidation_checkpoints.py"
SOURCE = ROOT / "artifacts/prospective/BTC-LIQUIDATION-STRESS-V1"
CONTRACT = ROOT / "research/PROSPECTIVE_BTC_LIQUIDATION_PERSISTENT_OBSERVATION_V1.yaml"
AUTHORITY = {
    "execution_authority": "NONE",
    "venue_connection": "NONE",
    "market_data_transport": "PUBLIC_READ_ONLY",
    "paper_orders": "DISABLED",
    "live_orders": "DISABLED",
    "credentials_used": False,
}

START = datetime(2026, 7, 13, 18, 0, tzinfo=UTC)


def verify(directory: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--verify-only", "--output-dir", str(directory)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_persistent_status_verifies_and_rejects_authority_drift(tmp_path: Path) -> None:
    target = tmp_path / "prospective"
    shutil.copytree(SOURCE, target)
    status = {
        "schema_version": 1,
        "operations_contract_sha256": hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
        "run_commit": "0" * 40,
        "process_started_at": "2026-07-13T20:00:00+00:00",
        "heartbeat_at": "2026-07-13T20:00:30+00:00",
        "state": "COMPLETED",
        "connection_epoch": 1,
        "continuity_epoch": 1,
        "finalized_window_count": 2,
        "last_finalized_window_start": "2026-07-13T20:05:00+00:00",
        "last_failure_ref": None,
        "authority": AUTHORITY.copy(),
    }
    operations = target / "operations"
    operations.mkdir(exist_ok=True)
    (operations / "status.json").write_text(json.dumps(status))
    assert verify(target).returncode == 0

    status["authority"]["paper_orders"] = "ENABLED"
    (operations / "status.json").write_text(json.dumps(status))
    drift = verify(target)
    assert drift.returncode != 0
    assert "authority boundary changed" in drift.stderr


def checkpoint_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    return importlib.import_module("run_prospective_liquidation_checkpoints")


class FakeWebSocket:
    def __init__(self, clock: list[datetime], *, disconnect_after: int | None = None) -> None:
        self.clock = clock
        self.disconnect_after = disconnect_after
        self.received = 0

    async def recv(self) -> str:
        if self.disconnect_after == self.received:
            raise ConnectionError("synthetic disconnect")
        self.received += 1
        self.clock[0] += timedelta(minutes=10 if self.received == 1 else 5)
        event_time = self.clock[0] - timedelta(seconds=1)
        timestamp = int(event_time.timestamp() * 1000)
        return json.dumps(
            {
                "e": "forceOrder",
                "E": timestamp,
                "o": {
                    "s": "BTCUSD_PERP",
                    "ps": "BTCUSD",
                    "S": "SELL",
                    "z": "1",
                    "ap": "100000",
                    "T": timestamp - 1,
                    "st": 2,
                },
            }
        )

    async def close(self) -> None:
        return None


@pytest.mark.parametrize("scenario", ["continuous", "disconnect", "rotation"])
def test_checkpoint_loop_preserves_finalized_windows_and_continuity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    module = checkpoint_module()
    clock = [START]
    opened = 0
    raw = b"{}\n"
    raw_hash = hashlib.sha256(raw).hexdigest()

    async def fake_open_source(directory: Path, connection_epoch: int):
        nonlocal opened
        opened += 1
        websocket = FakeWebSocket(
            clock,
            disconnect_after=1 if scenario == "disconnect" and opened == 1 else None,
        )
        module.write_bytes_content_addressed(directory / "raw", "exchange_info", raw)
        return module.SourceConnection(
            websocket,
            clock[0],
            connection_epoch,
            raw_hash,
            Decimal(100),
        )

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(module, "utc_now", lambda: clock[0])
    monkeypatch.setattr(module, "open_source", fake_open_source)
    monkeypatch.setattr(module.asyncio, "sleep", no_sleep)
    if scenario == "rotation":
        monkeypatch.setattr(module, "ROTATE_AFTER", timedelta(minutes=9))

    requested = 3 if scenario == "rotation" else 2
    assert module.asyncio.run(module.run_checkpoints(tmp_path, requested)) == 0
    sessions = [json.loads(path.read_text()) for path in tmp_path.glob("session_*.json")]
    complete = sorted(
        (item for item in sessions if item["source"]["status"] == "COMPLETE"),
        key=lambda item: item["started_at"],
    )
    assert len(complete) == requested
    assert [item["persistent_observation"]["checkpoint_index"] for item in complete] == list(
        range(1, requested + 1)
    )
    starts = [datetime.fromisoformat(item["started_at"]) for item in complete]
    expected_step = timedelta(minutes=10 if scenario == "disconnect" else 5)
    assert starts[1] - starts[0] == expected_step
    assert opened == (1 if scenario == "continuous" else 2)
    assert [item["persistent_observation"]["continuity_epoch"] for item in complete] == (
        [1, 2] if scenario == "disconnect" else [1] * requested
    )
    if scenario == "rotation":
        assert complete[-1]["persistent_observation"]["planned_handoff"] == {
            "from_connection_epoch": 1,
            "overlap_started_at": (START + timedelta(minutes=10)).isoformat(),
            "handoff_boundary": (START + timedelta(minutes=15)).isoformat(),
        }
    failed = [item for item in sessions if item["source"]["status"] != "COMPLETE"]
    assert len(failed) == (1 if scenario == "disconnect" else 0)
    status = json.loads((tmp_path / "operations/status.json").read_text())
    assert status["state"] == "COMPLETED"
    assert status["authority"] == AUTHORITY
