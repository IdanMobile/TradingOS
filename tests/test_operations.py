"""Checks for the read-only operations projection (data freshness + strategies)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tios.services.dashboard_api import operations
from tios.services.dashboard_api.operations import build_operations, trigger_data_update


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_operations_projects_data_freshness_and_strategy_results(tmp_path: Path) -> None:
    _write(
        tmp_path / "data" / "normalized_multi" / "daily_update_status.json",
        {"last_run_utc": "2026-07-12T09:00:00+00:00", "files_updated": 50, "bars_added": 1200},
    )
    _write(
        tmp_path / "artifacts/research_lab/signal_strategy_search/SIGNAL_STRATEGY_SEARCH.json",
        {
            "strategies": [
                {
                    "strategy_id": "SIG-VOLUME-BREAKOUT",
                    "source": "volume-confirmed Donchian breakout",
                    "approval_status": "NOT_ELIGIBLE",
                    "execution_authority": "NONE",
                    "contexts": [
                        {
                            "dataset": "ETHUSDT_1h",
                            "best_total_return": "1.539",
                            "screen_pass": True,
                        },
                        {
                            "dataset": "BTCUSDT_1h",
                            "best_total_return": "-0.31",
                            "screen_pass": False,
                        },
                    ],
                }
            ]
        },
    )
    ops = build_operations(tmp_path)

    assert ops["data_update"]["last_update_utc"] == "2026-07-12T09:00:00+00:00"
    assert ops["data_update"]["files_updated"] == 50
    assert ops["strategy_count"] == 1
    assert ops["strategies_passing_screen"] == 1
    row = ops["strategies"][0]
    assert row["strategy_id"] == "SIG-VOLUME-BREAKOUT"
    assert row["best_return_pct"] == 153.9  # best of the two contexts, as a percent
    assert row["best_dataset"] == "ETHUSDT_1h"
    assert row["screen_pass"] is True and row["contexts_passed"] == 1
    assert row["last_tested_utc"] is not None  # from the artifact file mtime
    assert ops["execution_authority"] == "NONE"


def test_operations_handles_missing_files(tmp_path: Path) -> None:
    ops = build_operations(tmp_path)
    assert ops["data_update"]["last_update_utc"] is None
    assert ops["strategies"] == [] and ops["strategy_count"] == 0


def test_data_update_trigger_is_idempotent_and_audited(tmp_path: Path, monkeypatch) -> None:
    launches: list[object] = []

    def launch(*args, **kwargs):
        launches.append((args, kwargs))
        return object()

    monkeypatch.setattr(operations.subprocess, "Popen", launch)

    first = trigger_data_update(tmp_path, "data-refresh-1")
    second = trigger_data_update(tmp_path, "data-refresh-1")

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert len(launches) == 1
    records = [
        json.loads(line)
        for line in (tmp_path / "artifacts/operations/data_update_triggers.jsonl")
        .read_text()
        .splitlines()
    ]
    assert [record["phase"] for record in records] == ["PREPARED", "COMPLETED"]


def test_data_update_launch_failure_replays_failure_without_false_success(
    tmp_path: Path, monkeypatch
) -> None:
    launches = 0

    def launch(*args, **kwargs):
        nonlocal launches
        launches += 1
        if launches == 1:
            raise OSError("injected launch failure")
        return object()

    monkeypatch.setattr(operations.subprocess, "Popen", launch)

    with pytest.raises(ValueError, match="launch failed") as first:
        trigger_data_update(tmp_path, "failed-refresh")
    with pytest.raises(ValueError, match="launch failed") as replay:
        trigger_data_update(tmp_path, "failed-refresh")
    assert str(first.value) == str(replay.value)
    assert launches == 1

    recovered = trigger_data_update(tmp_path, "new-refresh-key")
    assert recovered["status"] == "started"
    assert launches == 2
    records = [
        json.loads(line)
        for line in (tmp_path / "artifacts/operations/data_update_triggers.jsonl")
        .read_text()
        .splitlines()
        if "failed-refresh" in line
    ]
    assert [record["phase"] for record in records] == ["PREPARED", "FAILED"]


def test_data_update_audit_refuses_parent_symlink_escape(tmp_path: Path, monkeypatch) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "operations").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(
        operations.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("unsafe audit must block launch"),
    )

    with pytest.raises(ValueError, match="audit path"):
        trigger_data_update(tmp_path, "symlink-refresh")
    assert not (outside / "data_update_triggers.jsonl").exists()
