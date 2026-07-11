"""External DCA replay stays local, reproducible, and non-executable."""

from __future__ import annotations

import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_external_dca_replay.py"
ARTIFACT_ROOT = ROOT / "artifacts" / "external_replay" / "3commas_dca"

spec = importlib.util.spec_from_file_location("external_dca_replay", SCRIPT)
assert spec is not None and spec.loader is not None
dca = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = dca
spec.loader.exec_module(dca)


def test_synthetic_dca_replay_enters_adds_and_exits_without_execution_authority() -> None:
    config = dca.DcaConfig(
        strategy_id="STRAT-EXT-3COMMAS-DCA-CONFIG",
        rsi_window=14,
        rsi_threshold=Decimal("35"),
        sma_window=20,
        start_fraction=Decimal("0.25"),
        add_fraction=Decimal("0.25"),
        max_position_fraction=Decimal("1.0"),
        add_steps=(Decimal("-0.03"), Decimal("-0.06"), Decimal("-0.09")),
        stop_loss=Decimal("0.12"),
    )
    closes = [
        Decimal(value)
        for value in (
            "100",
            "99",
            "98",
            "97",
            "96",
            "95",
            "94",
            "93",
            "92",
            "91",
            "90",
            "89",
            "88",
            "87",
            "86",
            "85",
            "84",
            "83",
            "82",
            "81",
            "78",
            "76",
            "75",
            "77",
            "80",
            "84",
            "88",
            "91",
            "94",
            "98",
        )
    ]
    candles = {
        "open": closes.copy(),
        "high": closes.copy(),
        "low": closes.copy(),
        "close": closes,
    }

    trial, events = dca.simulate_dca(candles, config)

    assert trial.status == "COMPLETED"
    assert trial.entries == 1
    assert trial.adds >= 1
    assert trial.exits == 1
    assert {event.event_type for event in events} >= {"ENTRY", "ADD", "EXIT"}
    assert all(event.execution_index == event.signal_index + 1 for event in events)


def test_retained_external_dca_replay_artifact_is_research_only() -> None:
    runs = sorted(ARTIFACT_ROOT.glob("EXTDCA-*/replay_run.json"))
    assert runs, "run scripts/run_external_dca_replay.py to retain the replay artifact"
    run = json.loads(runs[-1].read_text(encoding="utf-8"))
    scorecard = json.loads((ROOT / run["scorecard_path"]).read_text(encoding="utf-8"))

    assert run["mode"] == "OFFLINE_RESEARCH_ONLY"
    assert run["execution_authority"] == "NONE"
    assert run["paper_orders"] == "DISABLED"
    assert run["live_orders"] == "DISABLED"
    assert run["counts"]["datasets"] == 6
    assert run["counts"]["trials"] == 6
    assert scorecard["validation_state"] == "UNVALIDATED"
    assert scorecard["promotion_eligible"] is False
    assert scorecard["execution_authority"] == "NONE"
    assert scorecard["paper_demo_live"] == "DISABLED"
    assert "order_routing" in scorecard["prohibited"]
    assert "platform_bot_execution" in scorecard["prohibited"]
