import subprocess
from argparse import Namespace
from decimal import Decimal
from pathlib import Path

from tios.adapters.hummingbot import lane
from tios.core_types.engine import FeeSlippageScenario


def test_selected_window_supports_bounded_and_custom_ranges() -> None:
    start, end, label = lane.selected_window(
        Namespace(start_date=None, end_date="2026-07-01", window_days=60)
    )

    assert label == "last_60_days"
    assert start.isoformat() == "2026-05-02T00:00:00+00:00"
    assert end.isoformat() == "2026-07-01T00:00:00+00:00"

    start, end, label = lane.selected_window(
        Namespace(start_date="2025-01-01", end_date="2025-02-01", window_days=None)
    )

    assert label == "custom"
    assert start.isoformat() == "2025-01-01T00:00:00+00:00"
    assert end.isoformat() == "2025-02-01T00:00:00+00:00"


def test_hummingbot_timeout_stops_named_container_and_writes_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[list[str]] = []

    class StopResult:
        returncode = 0
        stdout = "stopped\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd, timeout=7, output="partial", stderr="busy")
        return StopResult()

    monkeypatch.setattr(lane, "ARTIFACTS", tmp_path / "artifacts")
    monkeypatch.setattr(lane, "LANE", tmp_path / "lane")
    monkeypatch.setattr(lane, "ENGINE_DIR", tmp_path / "engine")
    monkeypatch.setattr(subprocess, "run", fake_run)

    manifest = lane.run_backtest(
        "B2",
        "BTCUSDT",
        FeeSlippageScenario("F1/S1", Decimal("0.001"), Decimal("1")),
        "run-timeout",
        lane.parse_date("2026-05-01"),
        lane.parse_date("2026-06-01"),
        "custom",
        7,
    )

    assert manifest["status"] == "TIMEOUT"
    assert manifest["timed_out"] is True
    assert manifest["stopped_container"] is True
    assert calls[0][0:2] == ["docker", "run"]
    assert "--name" in calls[0]
    assert calls[1] == ["docker", "stop", "tios-hb-b2-btcusdt-f1-s1-run-timeout"]
    manifest_path = (
        tmp_path / "artifacts" / "B2" / "BTCUSDT" / "F1_S1" / "run-timeout" / "manifest.json"
    )
    assert manifest_path.exists()
    assert "TIMEOUT after 7s" in manifest_path.with_name("stderr.log").read_text()
