"""Checks for the read-only operations projection (data freshness + strategies)."""

from __future__ import annotations

import json
from pathlib import Path

from tios.services.dashboard_api.operations import build_operations


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
