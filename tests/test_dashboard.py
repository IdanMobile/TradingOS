import functools
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from tios.services.dashboard_api.market import build_market_snapshot
from tios.services.dashboard_api.search import build_search_results
from tios.services.dashboard_api.status import (
    _s3_s4_control_plane_report,
    build_dashboard_data,
    build_stage_gate_readiness,
    build_status,
    record_workspace_decision,
)
from tios.services.dashboard_ui.server import Handler, is_loopback_host


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_s3_s4_control_plane_projection_fails_closed_on_bad_hash(tmp_path: Path) -> None:
    report = tmp_path / "artifacts/reports/S3_S4_CONTROL_PLANE_READINESS_2026_07_11.json"
    report.parent.mkdir(parents=True)
    report.write_text(
        json.dumps({"status": "READY", "content_sha256": "not-the-payload-hash"}),
        encoding="utf-8",
    )
    projection = _s3_s4_control_plane_report(tmp_path)
    assert projection["status"] == "INVALID_ARTIFACT"
    assert projection["execution_authority"] == "NONE"
    assert projection["active_record_counts"] == {}
    assert projection["s3_blockers"] == ["readiness artifact integrity check failed"]
    readiness = build_stage_gate_readiness(tmp_path)
    assert readiness["status"] == "INVALID_ARTIFACT"
    assert readiness["evidence_artifact"]["status"] == "INVALID_ARTIFACT"
    assert "readiness artifact integrity check failed" in readiness["s4_live"]["blocked_by"]


def _write_market_fixture(root: Path, fills: int | None = 1, candles: int = 60) -> None:
    candle_path = root / "data/normalized/BTCUSDT_5m.parquet"
    candle_path.parent.mkdir(parents=True)
    connection = duckdb.connect()
    connection.sql(
        f"""
        SELECT TIMESTAMPTZ '2026-01-01 00:00:00+00:00' + i * INTERVAL 5 MINUTE
                   AS timestamp_open_utc,
               100.0 + i AS open, 102.0 + i AS high, 99.0 + i AS low,
               101.0 + i AS close, 10.0 + i AS volume_base
        FROM range(60) AS rows(i)
        WHERE i < {candles}
        """
    ).write_parquet(str(candle_path))
    manifest_path = root / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_id": "DS-FIXTURE",
                "source": "Fixture Exchange frozen data",
                "frozen_utc": "2026-01-02T00:00:00+00:00",
                "tables": {
                    "BTCUSDT_5m": {
                        "parquet": candle_path.name,
                        "parquet_sha256": _sha256(candle_path),
                    }
                },
            }
        )
    )
    if fills is None:
        connection.close()
        return
    fill_root = root / "artifacts/validation/B2_F0_S0/runs/holdout"
    fill_root.mkdir(parents=True)
    fill_path = fill_root / "trades.parquet"
    where = "" if fills else "WHERE false"
    connection.sql(
        f"""
        SELECT TIMESTAMPTZ '2026-01-01 04:00:00+00:00' AS ts_fill,
               'buy' AS side, 150.0 AS price, 1.0 AS qty,
               'trade-1' AS trade_id, 'BTC/USDT' AS pair
        {where}
        """
    ).write_parquet(str(fill_path))
    (fill_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "OK",
                "dataset_id": "DS-FIXTURE",
                "files": [{"path": fill_path.name, "sha256": _sha256(fill_path)}],
            }
        )
    )
    connection.close()


def test_dashboard_status_is_read_only_projection() -> None:
    root = Path(__file__).resolve().parents[1]
    status = build_status(root)
    assert status["project"] == "Trading Intelligence OS"
    assert status["schema_version"] == 1
    assert status["summary"]["total"] > 0
    assert status["summary"]["open"] == len(status["open_tasks"])
    assert status["summary"]["gated"] == len(status["gated_tasks"])
    assert status["summary"]["recurring"] == len(status["recurring_tasks"])
    assert status["open_tasks"] == []
    assert status["gated_tasks"]
    assert status["recurring_tasks"]
    assert status["workspace_actions"]
    assert status["workspace_decisions"]["artifact"] == (
        "artifacts/human_decisions/workspace_decisions.jsonl"
    )
    assert all(task["bucket"] == "gated" for task in status["gated_tasks"])
    assert all(task["bucket"] == "recurring" for task in status["recurring_tasks"])
    assert any(task["status"].startswith("DEFERRED") for task in status["gated_tasks"])
    assert any(task["status"].startswith("ONGOING") for task in status["recurring_tasks"])
    # Structural property, not a task-ID pin: pinning specific IDs went stale twice in
    # two days as tasks completed. What must always hold: cards exist only for tasks
    # still awaiting a decision (gated or recurring), never for completed ones, and
    # every card carries a non-empty option set.
    open_ids = {t["id"] for t in status["gated_tasks"]} | {
        t["id"] for t in status["recurring_tasks"]
    }
    assert status["workspace_actions"], "some gated/recurring work always needs a card"
    for action in status["workspace_actions"]:
        assert action["id"] in open_ids, f"{action['id']} has a card but is not open"
        assert action["options"], f"{action['id']} card has no options"
    assert any(item["file"] == "14_dashboard.md" for item in status["initiatives"])
    assert status["checks"]["status"] in {"PASS", "UNKNOWN"}
    assert status["checks"]["known_passing"] is (status["checks"]["status"] == "PASS")
    assert status["checks"]["includes_dependency_audit"] is False
    assert status["observation"]["capabilities"]["execution_authority"] == "NONE"
    assert status["observation"]["capabilities"]["http_process_control"] is False
    assert status["risk_signal_flow"]["flow_state"] == "RISK_BLOCKED"
    assert status["risk_signal_flow"]["signal"]["side"] == "FLAT"
    assert status["risk_signal_flow"]["risk_decision"]["decision"] == "BLOCK"
    assert status["risk_signal_flow"]["risk_decision"]["independent"] is True
    assert status["risk_signal_flow"]["capabilities"]["order_creation"] is False
    assert status["strategy_eligibility"]["subject_ref"] == (
        "PROSPECTIVE-BTC-LIQUIDATION-STRESS-V1"
    )
    assert status["strategy_eligibility"]["metric_eligible"] is False
    assert status["strategy_eligibility"]["scorecard_eligible"] is False
    assert status["strategy_eligibility"]["promotion_eligible"] is False
    assert status["strategy_eligibility"]["execution_authority"] == "NONE"


def test_dashboard_evidence_surface_reads_real_project_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    data = build_dashboard_data(root)
    assert data["schema_version"] == 1
    assert data["datasets"][0]["id"] == "DS-CRYPTO-SPOT-BAKEOFF-V1"
    assert data["datasets"][0]["rows"] > 1_000_000
    assert len(data["strategies"]) == 5
    external = next(
        item for item in data["strategies"] if item["id"] == "STRAT-EXT-3COMMAS-DCA-CONFIG"
    )
    assert external["family"] == "external_replay"
    assert external["status"] == "LOCAL_REPLAY_RETAINED"
    assert external["validation_state"] == "UNVALIDATED"
    assert external["promotion_eligible"] is False
    assert external["execution_authority"] == "NONE"
    assert len(data["engines"]) == 5
    assert data["validation"]["status"] == "INCOMPLETE_NOT_APPROVABLE"
    assert data["validation"]["risk_preconditions"]["no_live_capability"] is True
    assert data["validation"]["risk_preconditions"]["promotion_eligible"] is False
    assert data["stage"] == "S2_OFFLINE_RESEARCH_OPERATIONS"
    assert data["observation"]["managed_flow_id"] == ("PROSPECTIVE-OBSERVATION-MANAGED-FLOW-V1")
    assert data["observation"]["capabilities"]["paper_orders"] == "DISABLED"
    assert data["risk_signal_flow"]["availability"] == "AVAILABLE"
    assert data["risk_signal_flow"]["signal"]["promotion_eligible"] is False
    assert data["risk_signal_flow"]["capabilities"]["execution_authority"] == "NONE"
    assert data["strategy_eligibility"]["state"] == "NOT_ELIGIBLE"
    assert "SCORECARD_INELIGIBLE" in data["strategy_eligibility"]["promotion_blockers"]
    assert data["readiness"] == {
        "status": "CONSTRAINED",
        "scope": "S2 OFFLINE RESEARCH ONLY",
        "report": "artifacts/reports/PROTOTYPE_READINESS_REPORT.md",
    }


def test_dashboard_projects_inert_trading_domain_read_model() -> None:
    root = Path(__file__).resolve().parents[1]
    data = build_dashboard_data(root)
    trading = data["trading_domain"]
    assert trading["schema_version"] == 1
    assert trading["environment"] == "HISTORICAL_RESEARCH"
    assert trading["mode"] == "INERT_READ_MODEL"
    assert trading["execution_authority"] == "NONE"
    assert trading["venue_connection"] == "NONE"
    assert trading["capabilities"] == {
        "credential_access": "ABSENT",
        "order_endpoint": "ABSENT",
        "account_mutation": "DISABLED",
        "synthetic_wallet": "ABSENT",
        "demo_orders": "DISABLED",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "risk_engine": "VALIDATION_PRECONDITIONS_ONLY",
        "s3_s4_contracts": "MODELED_INERT",
    }
    assert trading["counts"]["retained_run_artifacts"] == len(data["runs"])
    assert trading["counts"]["retained_backtest_fills"] > 0
    assert trading["counts"]["order_intents"] == 0
    assert trading["counts"]["order_states"] == 0
    assert trading["counts"]["accounts"] == 0
    assert trading["counts"]["portfolios"] == 0
    assert trading["counts"]["positions"] == 0
    assert trading["counts"]["stage_gate_records"] == 0
    assert trading["counts"]["paper_lane_proposals"] == 0
    assert trading["counts"]["paper_divergence_reports"] == 0
    assert trading["counts"]["paper_fill_policies"] == 0
    assert trading["counts"]["operational_drill_records"] == 0
    assert trading["counts"]["synthetic_ledgers"] == 0
    assert trading["counts"]["synthetic_accounts"] == 0
    assert trading["counts"]["synthetic_portfolios"] == 0
    assert trading["counts"]["runtime_risk_policies"] == 0
    assert trading["counts"]["portfolio_risk_policies"] == 0
    assert trading["counts"]["strategy_budget_policies"] == 0
    assert trading["counts"]["market_condition_policies"] == 0
    assert trading["counts"]["restricted_credential_policies"] == 0
    assert trading["counts"]["paper_operations_runbooks"] == 0
    assert trading["counts"]["paper_operations_events"] == 0
    assert trading["counts"]["operational_incidents"] == 0
    assert trading["counts"]["durable_evidence_events"] == 0
    assert trading["counts"]["paper_stability_reports"] == 0
    assert trading["counts"]["limited_live_risk_packages"] == 0
    assert trading["counts"]["live_operations_runbooks"] == 0
    assert trading["counts"]["live_operations_events"] == 0
    assert trading["counts"]["live_readiness_proposals"] == 0
    assert trading["risk_preconditions"]["promotion_eligible"] is False
    demo_wallet = trading["demo_wallet_design"]
    assert demo_wallet["status"] == "DESIGN_ONLY_NOT_ACTIVATED"
    assert demo_wallet["ledger_state"] == "ABSENT"
    assert demo_wallet["synthetic_capital"] == "NOT_CREATED"
    assert demo_wallet["mutation_api"] == "ABSENT"
    assert demo_wallet["order_route"] == "ABSENT"
    assert demo_wallet["execution_authority"] == "NONE"
    assert "HG_3_APPROVED" in demo_wallet["required_gates"]
    assert "paper_lane_architecture_decision" in demo_wallet["required_gates"]
    assert "exchange credential" in demo_wallet["must_never_include"]
    assert "venue order routing" in demo_wallet["must_never_include"]
    assert "real-money balance" in demo_wallet["must_never_include"]
    assert (
        "synthetic wallets cannot be constructed in current domain contracts"
        in demo_wallet["invariants"]
    )
    assert "HG_3_APPROVED" in trading["activation_predicate"]
    control_plane = trading["s3_s4_control_plane_report"]
    assert control_plane["status"] == "BLOCKED_BY_GATES"
    assert control_plane["artifact_ref"] == (
        "artifacts/reports/S3_S4_CONTROL_PLANE_READINESS_2026_07_11.json"
    )
    assert control_plane["mode"] == "CONTROL_PLANE_PROBE_ONLY"
    assert control_plane["execution_authority"] == "NONE"
    assert control_plane["paper_orders"] == "DISABLED"
    assert control_plane["live_orders"] == "DISABLED"
    assert control_plane["active_record_counts"] == {
        "live_readiness_proposals": 0,
        "operational_drill_records": 0,
        "paper_divergence_reports": 0,
        "paper_fill_policies": 0,
        "paper_lane_proposals": 0,
        "paper_operations_runbooks": 0,
        "paper_operations_events": 0,
        "operational_incidents": 0,
        "durable_evidence_events": 0,
        "paper_stability_reports": 0,
        "limited_live_risk_packages": 0,
        "live_operations_runbooks": 0,
        "live_operations_events": 0,
        "runtime_risk_policies": 0,
        "portfolio_risk_policies": 0,
        "strategy_budget_policies": 0,
        "market_condition_policies": 0,
        "restricted_credential_policies": 0,
        "stage_gate_records": 0,
        "synthetic_accounts": 0,
        "synthetic_ledgers": 0,
        "synthetic_portfolios": 0,
    }
    assert "no candidate is validated or promotion eligible" in control_plane["s3_blockers"]
    assert "no venue credential is requested or configured" in control_plane["s4_blockers"]
    readiness = trading["stage_gate_readiness"]
    assert readiness["status"] == "BLOCKED_BY_GATES"
    assert readiness["execution_authority"] == "NONE"
    assert readiness["s3_paper_demo"]["status"] == "NOT_READY"
    assert readiness["s4_live"]["status"] == "NOT_READY"
    assert "S2_EXIT_PASS" in readiness["s3_paper_demo"]["blocked_by"]
    assert "inert S3/S4 readiness contracts implemented" in readiness["s3_paper_demo"]["satisfied"]
    assert "one COMPLETE_APPROVABLE strategy context" in readiness["s3_paper_demo"]["blocked_by"]
    assert "HG_5_OPERATOR_APPROVAL" in readiness["s4_live"]["blocked_by"]
    assert "synthetic_wallet_mutation" in trading["prohibited"]
    assert "venue_order_routing" in trading["prohibited"]
    assert "live_order_capability" in trading["prohibited"]
    assert any(
        row["name"] == "S3/S4 readiness control plane" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Backtest-versus-paper divergence" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Operational drills" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic demo ledger" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic paper fill policy" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic execution reducers" and row["status"] == "AVAILABLE_OFFLINE_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Canonical signal evaluator" and row["status"] == "AVAILABLE_OFFLINE_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Durable synthetic evidence ledger"
        and row["status"] == "AVAILABLE_OFFLINE_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic account and portfolio" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic runtime risk policy" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic portfolio risk policy" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic strategy budget policy" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Synthetic market-condition policy" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Restricted credential policy" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Paper operations runbook" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Paper operations event log" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Operational incident lifecycle" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Paper stability report" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Limited live risk package" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Live operations runbook" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )
    assert any(
        row["name"] == "Live operations event log" and row["status"] == "MODELED_INERT"
        for row in trading["read_models"]
    )


def test_stage_gate_readiness_is_read_only_and_blocked() -> None:
    payload = build_stage_gate_readiness()
    assert payload["schema_version"] == 1
    assert payload["mode"] == "LOCAL_READ_ONLY"
    assert payload["status"] == "BLOCKED_BY_GATES"
    assert payload["execution_authority"] == "NONE"
    assert payload["capabilities"] == {
        "writes": "DISABLED",
        "credential_access": "ABSENT",
        "order_endpoint": "ABSENT",
        "venue_connection": "NONE",
        "demo_paper_control": "ABSENT",
        "live_control": "ABSENT",
    }
    assert payload["s3_paper_demo"]["status"] == "NOT_READY"
    assert payload["s4_live"]["status"] == "NOT_READY"
    assert "S2_EXIT_PASS" in payload["s3_paper_demo"]["blocked_by"]
    assert "inert S3/S4 readiness contracts implemented" in payload["s3_paper_demo"]["satisfied"]
    assert "HG_5_OPERATOR_APPROVAL" in payload["s4_live"]["blocked_by"]


def test_dashboard_projects_read_only_comparison_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    data = build_dashboard_data(root)
    comparisons = data["comparisons"]
    assert comparisons["schema_version"] == 1
    assert comparisons["mode"] == "LOCAL_READ_ONLY"
    assert comparisons["status"] == "NO_PROMOTION_CANDIDATE"
    assert comparisons["execution_authority"] == "NONE"
    assert comparisons["winner_selected"] is False
    assert comparisons["capabilities"] == {
        "writes": "DISABLED",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "approval_mutation": "DISABLED",
    }
    candidate = next(row for row in comparisons["candidate_rows"] if row["candidate_id"] == "B2")
    assert candidate["validation_state"] == "UNVALIDATED"
    assert candidate["approval_state"] == "NOT_ELIGIBLE"
    assert candidate["dimensions"]["multiple_testing_selection_bias_control"] == "FAIL"
    assert candidate["dimensions"]["cross_engine_reproduction"] == "PASS_WITH_SCOPE_NOTE"
    assert any(
        row["gate"] == "G10" and row["status"] == "METHOD_BLOCKED"
        for row in comparisons["validation_gates"]
    )
    assert any(
        row["family"] == "B2" and row["verdict"] == "FAIL" for row in comparisons["g10_rows"]
    )
    assert comparisons["cross_engine"]["verdict"] == "PASS_WITH_SCOPE_NOTE"
    assert comparisons["cross_engine"]["economic_direction_agreement"] is True
    assert comparisons["seed_g10"]["status"] == "METHOD_BLOCKED"
    assert comparisons["seed_contexts"]
    assert all(ref.startswith("artifacts/") for ref in comparisons["evidence_refs"])


def test_dashboard_search_projects_registry_and_report_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = build_search_results(root, "DCA risk", limit=20)
    assert payload["schema_version"] == 1
    assert payload["mode"] == "LOCAL_READ_ONLY"
    assert payload["capabilities"] == {
        "writes": "DISABLED",
        "credential_access": "ABSENT",
        "order_endpoint": "ABSENT",
        "venue_connection": "NONE",
        "execution_authority": "NONE",
    }
    assert payload["counts"]["returned"] == len(payload["results"])
    kinds = {row["kind"] for row in payload["results"]}
    assert {"research_source", "strategy", "report"} <= kinds
    assert any(row["id"] == "SRC-3COMMAS-DCA-BOT" for row in payload["results"])
    assert any(row["id"] == "STRAT-EXT-3COMMAS-DCA-CONFIG" for row in payload["results"])
    assert all(row["path"] and row["score"] > 0 for row in payload["results"])
    assert all("secret" not in row["snippet"].casefold() for row in payload["results"])


def test_dashboard_search_projects_tradingview_candidate_batch() -> None:
    root = Path(__file__).resolve().parents[1]
    payload = build_search_results(root, "TVPINE Kivanc SuperTrend", limit=10)
    assert payload["capabilities"]["writes"] == "DISABLED"
    assert payload["capabilities"]["order_endpoint"] == "ABSENT"
    row = next(item for item in payload["results"] if item["id"] == "TVPINE-KIVANC-SUPERTREND")
    assert row["kind"] == "tradingview_candidate"
    assert row["status"] == "STRATEGY_REPORT_AVAILABLE_NOT_CAPTURED"
    assert row["path"] == (
        "artifacts/source_intake/tradingview_public_strategies/selected_candidates_2026_07_11.json"
    )


def test_research_lab_projection_is_stable_before_a_batch_exists(tmp_path: Path) -> None:
    lab = build_dashboard_data(tmp_path)["research_lab"]
    assert lab == {
        "mode": "OFFLINE_RESEARCH_ONLY",
        "state": "NO_BATCH",
        "latest_batch_id": None,
        "started_at": None,
        "completed_at": None,
        "experiments": 0,
        "runs": 0,
        "completed": 0,
        "failed": 0,
        "all_trials_retained": False,
        "winner_selected": False,
        "validation_status": "UNVALIDATED",
        "approval_status": "NOT_APPROVED",
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "demo_orders": "DISABLED",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "blockers": [],
        "score_dimensions": {},
        "artifact_refs": [],
        "latest_seed_cycle": None,
        "next_work": (
            "Run uv run python scripts/run_research_lab_v0.py when the next evidence cycle "
            "is requested."
        ),
    }


def test_research_lab_projects_latest_complete_batch_and_retained_trials(
    tmp_path: Path,
) -> None:
    lab_root = tmp_path / "artifacts/research_lab/v0"
    older = lab_root / "LAB-001"
    latest = lab_root / "LAB-002"
    older.mkdir(parents=True)
    latest.mkdir()
    (older / "lab_run.json").write_text(json.dumps({"status": "FAILED"}))
    payload = {
        "lab_id": "LAB-002",
        "status": "COMPLETED",
        "started_at_utc": "2026-07-10T10:00:00+00:00",
        "finished_at_utc": "2026-07-10T10:05:00+00:00",
        "counts": {
            "experiments": 3,
            "trials": 66,
            "completed_trials": 65,
            "failed_trials": 1,
        },
        "winner_selected": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "blockers": ["walk-forward stability is not run"],
        "score_states": {"temporal_walk_forward_stability": "BLOCKED"},
    }
    (latest / "lab_run.json").write_text(json.dumps(payload))
    (latest / "manifest.json").write_text("{}")

    lab = build_dashboard_data(tmp_path)["research_lab"]
    assert lab["state"] == "COMPLETE"
    assert lab["latest_batch_id"] == "LAB-002"
    assert (lab["experiments"], lab["runs"], lab["completed"], lab["failed"]) == (
        3,
        66,
        65,
        1,
    )
    assert lab["all_trials_retained"] is True
    assert lab["winner_selected"] is False
    assert lab["score_dimensions"]["temporal_walk_forward_stability"] == "BLOCKED"
    assert lab["artifact_refs"] == [
        "artifacts/research_lab/v0/LAB-002/lab_run.json",
        "artifacts/research_lab/v0/LAB-002/manifest.json",
    ]
    assert lab["latest_seed_cycle"] is None


def test_research_lab_projects_latest_seed_cycle(tmp_path: Path) -> None:
    cycle = tmp_path / "artifacts/research_lab/seed_cycle_v0/SEEDCYCLE-001"
    cycle.mkdir(parents=True)
    (cycle / "cycle_run.json").write_text(
        json.dumps(
            {
                "status": "COMPLETED",
                "mode": "OFFLINE_RESEARCH_ONLY",
                "winner_selected": False,
                "counts": {"candidates": 2, "trials": 16},
            }
        )
    )

    seed = build_dashboard_data(tmp_path)["research_lab"]["latest_seed_cycle"]
    assert seed == {
        "cycle_id": "SEEDCYCLE-001",
        "status": "COMPLETED",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "trials": 16,
        "candidates": 2,
        "winner_selected": False,
        "approval_status": "NOT_ELIGIBLE",
        "artifact_ref": "artifacts/research_lab/seed_cycle_v0/SEEDCYCLE-001/cycle_run.json",
    }


def test_research_lab_selects_latest_artifact_timestamp_not_batch_name(tmp_path: Path) -> None:
    lab_root = tmp_path / "artifacts/research_lab/v0"
    lexical_last = lab_root / "LAB-ZZZ"
    chronological_last = lab_root / "LAB-2392-real"
    lexical_last.mkdir(parents=True)
    chronological_last.mkdir()
    (lexical_last / "lab_run.json").write_text(
        json.dumps({"status": "COMPLETED", "finished_at_utc": "2026-07-09T00:00:00+00:00"})
    )
    (chronological_last / "lab_run.json").write_text(
        json.dumps(
            {
                "status": "COMPLETED",
                "finished_at_utc": "2026-07-10T00:00:00+00:00",
                "counts": {"trials": 1, "completed_trials": 1},
            }
        )
    )

    lab = build_dashboard_data(tmp_path)["research_lab"]
    assert lab["latest_batch_id"] == "LAB-2392-real"
    assert lab["runs"] == lab["completed"] == 1


def test_real_research_lab_batch_is_projected_automatically() -> None:
    root = Path(__file__).resolve().parents[1]
    lab = build_dashboard_data(root)["research_lab"]
    assert lab["latest_batch_id"].startswith("LAB-f04ef5")
    assert lab["runs"] == 66
    assert lab["completed"] == 66
    # Payload-derived (not base-default) safety facts of the retained batch.
    assert lab["state"] == "COMPLETE"
    assert lab["winner_selected"] is False
    assert lab["all_trials_retained"] is True
    assert lab["latest_seed_cycle"]["cycle_id"].startswith("SEEDCYCLE-9b1652")
    assert lab["latest_seed_cycle"]["trials"] == 258
    assert lab["latest_seed_cycle"]["candidates"] == 5


@pytest.mark.parametrize(
    ("contents", "blocker"),
    [
        ("{not json", "malformed or incomplete"),
        (
            json.dumps({"status": "FAILED", "error": "RuntimeError: retained failure"}),
            "retained failure",
        ),
    ],
)
def test_research_lab_malformed_or_failed_batch_fails_closed(
    tmp_path: Path, contents: str, blocker: str
) -> None:
    batch = tmp_path / "artifacts/research_lab/v0/LAB-FAIL"
    batch.mkdir(parents=True)
    (batch / "lab_run.json").write_text(contents)

    lab = build_dashboard_data(tmp_path)["research_lab"]
    assert lab["state"] == "FAILED"
    assert blocker in lab["blockers"][0]
    assert lab["execution_authority"] == "NONE"
    assert lab["venue_connection"] == "NONE"
    assert lab["demo_orders"] == lab["paper_orders"] == lab["live_orders"] == "DISABLED"
    assert lab["approval_status"] == "NOT_APPROVED"


def test_dashboard_projects_typed_research_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = build_dashboard_data(root)["research_sources"]
    assert sources["source_count"] == 15
    assert sources["hypothesis_only_count"] == 15
    assert sources["noneligible_count"] == 15
    assert sources["intake_plans"] == {
        "plan_count": 5,
        "ready_count": 4,
        "design_only_count": 1,
    }
    assert sources["replay_hypotheses"] == {
        "hypothesis_count": 5,
        "spec_candidate_count": 3,
        "replay_candidate_count": 1,
        "non_reconstructable_count": 1,
        "noneligible_count": 5,
    }
    tv_batch = sources["tradingview_public_strategy_batch"]
    assert tv_batch["candidate_count"] == 8
    assert tv_batch["status"] == "CANDIDATE_URLS_SELECTED_METADATA_ONLY"
    assert tv_batch["artifact_ref"] == (
        "artifacts/source_intake/tradingview_public_strategies/selected_candidates_2026_07_11.json"
    )
    assert tv_batch["execution_authority"] == "NONE"
    assert tv_batch["approval_eligible"] is False
    tv_replay = tv_batch["latest_replay"]
    assert tv_replay["status"] == "COMPLETED"
    assert tv_replay["mode"] == "OFFLINE_RESEARCH_ONLY"
    assert tv_replay["execution_authority"] == "NONE"
    assert tv_replay["paper_orders"] == "DISABLED"
    assert tv_replay["live_orders"] == "DISABLED"
    assert tv_replay["counts"]["trials"] == 12
    assert tv_replay["scorecard_path"].endswith("/scorecard.json")
    assert [row["candidate_id"] for row in tv_batch["rows"]] == [
        "TVPINE-KIVANC-SUPERTREND",
        "TVPINE-RAGINGPORRA-RSI-MEAN-REVERSION",
        "TVPINE-SKYREXIO-BB-ENHANCED",
        "TVPINE-PINEINDICATORS-TSI-BTC-2H",
        "TVPINE-FREE990-RSI-TP-SL",
        "TVPINE-FAYTTERRO-RSI-DIVERGENCE",
        "TVPINE-ASSASSINSGRID-SUPER8-BTC",
        "TVPINE-PRESENTTRADING-AI-SUPERTREND-PIVOT",
    ]
    assert sources["checked_date"] == "2026-07-13"
    assert len(sources["digest"]) == 64
    assert sources["family_counts"]["multiple_testing_controls"] == 4
    assert sources["family_counts"]["exchange_bot_replay"] == 1
    assert sources["family_counts"]["copy_trading_replay"] == 1
    assert sources["family_counts"]["signal_replay"] == 1
    assert sources["family_counts"]["public_strategy_reproduction"] == 1
    assert sources["family_counts"]["bot_platform_replay"] == 1
    paper = next(row for row in sources["rows"] if row["source_id"] == "SRC-PAPER1")
    assert paper["year"] == 1993
    assert paper["doi"] == "10.1111/j.1540-6261.1993.tb04702.x"
    assert paper["canonical_url"].startswith("https://")
    assert paper["families"] == ["cross_sectional_momentum"]
    assert paper["reproduction"] == "NOT_REPRODUCED"
    assert paper["eligibility"] == "NOT_ELIGIBLE"
    bot_source = next(
        row for row in sources["rows"] if row["source_id"] == "SRC-BINANCE-TRADING-BOTS"
    )
    assert bot_source["doi"] is None
    assert bot_source["families"] == ["exchange_bot_replay"]
    assert bot_source["eligibility"] == "NOT_ELIGIBLE"


def test_dashboard_projects_dictionary_concepts() -> None:
    root = Path(__file__).resolve().parents[1]
    concepts = build_dashboard_data(root)["dictionary_concepts"]

    assert concepts["concept_count"] == 16
    assert concepts["fibo_provenance_count"] >= 3
    assert concepts["categories"]["trading_domain"] >= 3
    assert concepts["gaps"]
    dataset = next(row for row in concepts["rows"] if row["concept_id"] == "CON-DATASET")
    assert "canonical dataset" in dataset["aliases"]
    assert dataset["evidence_status"] == "LOCAL_CONTRACT"
    assert dataset["freshness"] == "CURRENT"


def test_dashboard_includes_read_only_tradingview_market_monitor() -> None:
    html = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "tios"
        / "services"
        / "dashboard_ui"
        / "dashboard.html"
    ).read_text()
    assert "['market','Market monitor']" in html
    assert "external-embedding/embed-widget-advanced-chart.js" in html
    assert "NO ORDERS" in html
    assert "tradingview-widget-copyright" in html
    assert "https://www.tradingview.com/chart/?symbol=BINANCE%3ABTCUSDT" in html
    assert "The embedded chart's selector is indicator-only" in html
    assert 'data-market-research-view="comparisons"' in html
    assert 'data-market-research-view="strategies"' in html
    assert "showWorkspace('research');showView(button.dataset.marketResearchView" in html
    for label in (
        "Research Lab",
        "Autonomous evidence cycle",
        "All trials retained",
        "Seed candidate cycle",
        "Independent score dimensions",
        "Source provenance",
        "Demo trading",
        "Paper trading",
        "Live trading",
        "Trading Domain",
        "Orders, portfolio & risk",
        "Simulator boundary",
        "Synthetic paper readiness",
        "Live readiness",
        "gate-bound activation chain",
        "human-only future stage",
        "Legacy demo-wallet contract",
        "Demo-wallet invariants",
        "DESIGN_ONLY_NOT_ACTIVATED",
        "separate from the confined paper simulator",
        "Dictionary",
        "Concept registry",
        "Ontology boundary",
        "Strategy comparisons",
        "Candidate dimension matrix",
        "Comparison boundary",
        "comparison is not approval",
        "Registry & artifact search",
        "No write or execution path",
        "/api/v1/search",
        "search API response is malformed or unsafe",
        "Next command / work",
        "No POST or write control",
        "Actionable open",
        "Gated / recurring",
        "No actionable open tasks are projected",
        "Deferred or human/credential/stage-gated tasks",
        "Recurring governance discipline",
        "Human decisions",
        "data-workspace-task",
        "/api/v1/workspace-actions/decision",
    ):
        assert label in html
    assert "Changed files" not in html
    assert "Research automation cannot control the gate-bound simulator" in html


def test_todos_page_has_copy_session_prompt_button() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    todos_section = html[html.index('id="todos"') : html.index('id="todosBody"')]
    assert 'id="copySessionPrompt"' in todos_section
    assert 'onclick="copySessionPrompt(this)">Copy session prompt</button>' in todos_section
    # Structural property, not the whole prompt blob: the button copies a
    # version-agnostic kickoff prompt pointing at the live SSOT, not a
    # snapshot of today's specific open items.
    assert "function copySessionPrompt(button)" in html
    assert "navigator.clipboard?.writeText" in html
    assert "document.execCommand('copy')" in html
    assert "Copied ✓" in html
    assert "the single live authority for current state" in html


def test_orchestrator_page_has_status_and_history_markup() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    orch_section = html[
        html.index('id="orchestrator"') : html.index('id="operations"><div class="title-row">')
    ]
    for marker in (
        'id="orchState"',
        'id="orchInterpretation"',
        'id="orchObservedAt"',
        'id="orchStaleWarning"',
        'id="orchEscalations"',
        'id="orchObservations"',
        'id="orchParked"',
        'id="orchJournal"',
        "<th>Parked at</th>",
        "<th>Observed at</th><th>Halted</th><th>Escalations</th><th>Actions</th>",
        # Static explainer: the 8 domains, the 15-min cadence, and the kill switch,
        # so an operator can understand the loop without reading source.
        "checks 8 domains",
        "integrity, statistical, evidence, strategy, blockers, execution, parked, "
        "prospective_observation",
        "Every 15 minutes",
        "artifacts/orchestrator/KILL_SWITCH",
    ):
        assert marker in orch_section
    assert "async function loadOrchestrator" in html
    assert "/api/v1/orchestrator" in html
    # Collapsible pretty-printed JSON detail per observation domain.
    assert "JSON.stringify(o.detail,null,2)" in html
    assert '"OPEN ITEMS" section is the live task list' in html
    assert "PROJECT_STATE.md" in html
    assert "never run two pytest suites concurrently" in html


def test_dashboard_activity_maps_one_to_one_to_real_artifacts() -> None:
    root = Path(__file__).resolve().parents[1]
    data = build_dashboard_data(root)
    run_activity = [row for row in data["activity"] if row["kind"] == "RUN_ARTIFACT"]
    assert len(run_activity) == len(data["runs"])
    runs_by_artifact = {row["artifact"]: row for row in data["runs"]}
    for activity in run_activity:
        run = runs_by_artifact[activity["artifact"]]
        assert activity["timestamp"] == run["artifact_modified_at"]
        assert activity["runs"] == activity["count"] == 1
        assert activity["fills"] == run["fills"]


def test_dashboard_ui_a11y_responsive_and_state_contracts() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    for contract in (
        'class="skip-link"',
        'aria-current="page"',
        'aria-live="polite"',
        'aria-busy="true"',
        "min-height:44px",
        "body{font-size:16px}",
        "prefers-reduced-motion:reduce",
        'id="navToggle"',
        'id="activityTable"',
        'id="candleTable"',
        'id="marketProvenance"',
        'aria-describedby="marketProvenance candleTable"',
        'aria-details="candleTable"',
        'id="refreshRate"',
        '<option value="15000" selected>15s</option>',
        "networkTimer=setInterval(()=>sharedRefresh(false),Number(value))",
        "document.addEventListener('visibilitychange'",
        "showing last-good snapshot",
        "marketLoading=true",
        "Last updated",
        "returned malformed JSON",
        'id="retry"',
        "crypto.randomUUID()",
        "idempotency_key:idempotencyKey",
        "dataUpdateKey||(dataUpdateKey=crypto.randomUUID())",
        'id="runEthSignal"',
        'id="ethSignalResult"',
        "fetchJson('/api/v1/eth-signal')",
        "button.disabled=true",
        "historical reproduction only",
    ):
        assert contract in html
    # Provider-logo data: URIs are base64 noise and can coincidentally contain
    # substrings like "S1"; scope the stale-reference checks to real markup/copy.
    text_html = re.sub(r"base64,[A-Za-z0-9+/=]+", "base64,<omitted>", html)
    assert "POLL_MS=5000" not in text_html
    assert "MARKET_POLL_MS=15000" not in text_html
    assert "Array.from({length:24}" not in text_html
    assert "HG-2" not in text_html
    assert "S1" not in text_html


def test_watch_and_lab_workspaces_keep_every_page_and_live_is_default() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()

    # Watch group first (Live, Wallet), then the collapsed Lab group: the ten pre-existing
    # developer pages plus the read-only Automation control map.
    assert re.findall(r'<button[^>]+data-workspace="([^"]+)"', html) == [
        "live",
        "wallets",
        "now",
        "signals",
        "trading",
        "testing",
        "research",
        "operations",
        "automation-map",
        "library",
        "skills",
        "todos",
        "settings",
    ]
    assert '<button class="active" data-workspace="live" aria-current="page">Live</button>' in html
    assert '<span id="crumb">LIVE</span>' in html
    assert 'id="workspaceTools" aria-label="Live tools" hidden' in html
    assert '<section id="live" class="view active"' in html
    assert '<section id="now" class="view" aria-labelledby="nowHeadline"' in html
    assert "showWorkspace('live')" in html
    assert "live:[['live','Live']]" in html
    assert "now:[['now','Overview']]" in html
    assert "['ArrowDown','ArrowUp','Home','End']" in html
    assert "workspaceButtons[index].focus()" in html
    for preserved_view in (
        "market",
        "research-lab",
        "strategies",
        "comparisons",
        "validation",
        "automation",
        "operations",
        "workspace",
        "datasets",
        "runs",
        "engines",
        "dictionary",
        "search",
        "evidence",
    ):
        assert f'<section id="{preserved_view}"' in html or f'id="{preserved_view}"' in html


def test_single_child_workspace_has_no_subtab_but_multi_child_workspaces_do() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    navigation = html[html.index("const WORKSPACES=") : html.index("const workspaceButtons=")]
    script = f"""
const classList=()=>{{
  const values=new Set();
  return {{
    toggle(name,force){{if(force)values.add(name);else values.delete(name)}},
    remove(name){{values.delete(name)}},
    contains(name){{return values.has(name)}}
  }};
}};
const button=(workspace,label)=>({{
  dataset:{{workspace}},textContent:label,classList:classList(),attributes:{{}},
  setAttribute(name,value){{this.attributes[name]=value}},
  removeAttribute(name){{delete this.attributes[name]}},
  addEventListener(){{}}
}});
const workspaceButtons=[
  button('now','Overview'),button('trading','Trading'),button('research','Research'),
  button('operations','Operations'),button('library','Library')
];
const views=['now','paper-trading','market'].map(id=>({{id,classList:classList()}}));
const crumb={{textContent:''}};
const toolNav={{
  hidden:false,attributes:{{}},buttons:[],_innerHTML:'',
  setAttribute(name,value){{this.attributes[name]=value}},
  set innerHTML(value){{
    this._innerHTML=value;this.buttons=[];
    for(const match of value.matchAll(/data-view="([^"]+)"[^>]*>([^<]+)<\\/button>/g)){{
      const item=button('',match[2]);item.dataset={{view:match[1]}};this.buttons.push(item);
    }}
  }},
  get innerHTML(){{return this._innerHTML}},
  querySelectorAll(){{return this.buttons}}
}};
const document={{
  body:{{classList:classList()}},
  querySelectorAll(selector){{
    if(selector==='.view')return views;
    if(selector==='#workspaceTools [data-view]')return toolNav.buttons;
    if(selector==='[data-workspace]')return workspaceButtons;
    return [];
  }},
  querySelector(selector){{
    if(selector==='#workspaceTools')return toolNav;
    if(selector==='#crumb')return crumb;
    const match=/^\\[data-workspace="([^"]+)"\\]$/.exec(selector);
    return match?workspaceButtons.find(item=>item.dataset.workspace===match[1]):null;
  }}
}};
const navToggle={{setAttribute(){{}}}},window={{}},initTradingView=()=>{{}},loadMarket=()=>{{}};
const esc=value=>String(value);
{navigation}
showWorkspace('now');
const overview={{
  hidden:toolNav.hidden,html:toolNav.innerHTML,crumb:crumb.textContent,
  label:toolNav.attributes['aria-label'],active:views[0].classList.contains('active')
}};
showWorkspace('trading');
const trading={{
  hidden:toolNav.hidden,html:toolNav.innerHTML,crumb:crumb.textContent,
  label:toolNav.attributes['aria-label'],controls:toolNav.buttons.length,
  firstCurrent:toolNav.buttons[0].attributes['aria-current']
}};
console.log(JSON.stringify({{overview,trading}}));
"""
    state = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert state["overview"] == {
        "hidden": True,
        "html": "",
        "crumb": "OVERVIEW",
        "label": "Overview tools",
        "active": True,
    }
    assert state["trading"]["hidden"] is False
    assert state["trading"]["controls"] == 2
    assert state["trading"]["crumb"] == "TRADING / PORTFOLIO, BOTS & SIGNALS"
    assert state["trading"]["label"] == "Trading tools"
    assert state["trading"]["firstCurrent"] == "page"
    assert 'data-view="paper-trading"' in state["trading"]["html"]
    assert 'data-view="market"' in state["trading"]["html"]


def test_responsive_layout_breakpoints_cover_all_workspaces() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()

    assert (
        "@media(max-width:1180px){.shell{grid-template-columns:200px minmax(0,1fr)}"
        ".grid{grid-template-columns:repeat(2,minmax(0,1fr))}"
        ".layout,.market-grid{grid-template-columns:1fr}}" in html
    )
    assert (
        "@media(max-width:900px){.shell{display:block}.sidebar{height:auto;position:static;" in html
    )
    assert (
        ".topbar{position:static;padding:12px 24px;align-items:flex-start;"
        "flex-direction:column}" in html
    )
    assert ".env{width:100%;justify-content:flex-start}" in html
    assert ".workspace-tools{flex-wrap:wrap;overflow-x:visible}" in html
    assert "@media(max-width:1180px){.cockpit-head{grid-template-columns:1fr}" in html
    assert ".portfolio-main,.section-grid{grid-template-columns:1fr}" in html
    assert "@media(max-width:1000px)" not in html


def test_mobile_tables_chart_and_sidebar_have_bounded_layout_contracts() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    datasets = html[
        html.index("document.querySelector('#datasetsBody')") : html.index(
            "document.querySelector('#strategiesBody')"
        )
    ]
    mount = re.search(r'<div id="tradingviewWidgetMount"[^>]*>', html)

    assert mount is not None
    assert 'style="' not in mount.group()
    assert ".tradingview-widget-container{height:650px;min-height:0}" in html
    assert ".tradingview-widget-container{height:520px;min-height:0}" in html
    assert ".market-grid{grid-template-columns:1fr}" in html
    assert (
        '<div class="table-wrap" tabindex="0" role="region" '
        'aria-label="Frozen data registry table"><table>' in datasets
    )
    assert datasets.index('</table></div><p class="mono">Manifest:') > datasets.index(
        'aria-label="Frozen data registry table"'
    )
    assert ".table-wrap:focus-visible{outline:3px solid var(--cyan)" in html
    assert (
        ".sidebar{border-right:1px solid var(--line);padding:24px 16px;"
        "background:#09101b;position:sticky;top:0;height:100vh;display:flex;"
        "flex-direction:column;overflow-y:auto}" in html
    )
    # Settings sits in its own bottom-pinned nav block above the footer text; that
    # block carries the sticky-to-bottom margin now, not .sidebar-foot directly.
    assert ".nav-bottom{margin-top:auto" in html
    assert ".sidebar-foot{padding:20px 10px 0" in html
    assert ".sidebar-foot{position:absolute" not in html
    assert ".title-row>.action{margin-top:16px}" in html
    assert "}.action{margin-top:16px}" not in html


def test_collapsed_workspace_selection_hands_focus_to_main_only_on_small_screens() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    source = html[html.index("function showWorkspace") : html.index("const workspaceButtons")]
    script = f"""
const classList=()=>{{
  const values=new Set();
  return {{
    add(name){{values.add(name)}},remove(name){{values.delete(name)}},
    contains(name){{return values.has(name)}},
    toggle(name,force){{if(force)values.add(name);else values.delete(name)}}
  }};
}};
const body={{classList:classList()}},main={{calls:[],focus(options){{this.calls.push(options)}}}};
const navToggle={{
  expanded:'true',
  setAttribute(name,value){{if(name==='aria-expanded')this.expanded=value}}
}};
const toolNav={{hidden:false,innerHTML:'',setAttribute(){{}},querySelectorAll(){{return []}}}};
const button=(workspace,label)=>({{
  dataset:{{workspace}},textContent:label,classList:classList(),
  setAttribute(){{}},removeAttribute(){{}}
}});
const buttons=[button('now','Overview'),button('trading','Trading'),button('research','Research')];
const document={{
  body,
  querySelectorAll(selector){{return selector==='[data-workspace]'?buttons:[]}},
  querySelector(selector){{
    if(selector==='#workspaceTools')return toolNav;
    if(selector==='#main-content')return main;
    const match=/^\\[data-workspace="([^"]+)"\\]$/.exec(selector);
    return match?buttons.find(item=>item.dataset.workspace===match[1]):null;
  }}
}};
let matches=true,activeWorkspace='now';
const window={{
  matchMedia(query){{
    if(query!=='(max-width:900px)')throw new Error(query);
    return {{matches}};
  }}
}};
const WORKSPACES={{
  now:[['now','Overview']],
  trading:[['paper-trading','Portfolio, bots & signals'],['market','Market monitor']],
  research:[['research-lab','Research Lab'],['validation','Validation']]
}};
const esc=value=>String(value),showView=()=>{{}};
{source}
body.classList.add('nav-open');showWorkspace('trading');
const mobile={{
  focuses:main.calls.length,
  options:main.calls[0],
  open:body.classList.contains('nav-open'),
  expanded:navToggle.expanded
}};
matches=false;body.classList.add('nav-open');showWorkspace('research');
console.log(JSON.stringify({{mobile,desktopFocuses:main.calls.length}}));
"""
    state = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert state["mobile"] == {
        "focuses": 1,
        "options": {"preventScroll": True},
        "open": False,
        "expanded": "false",
    }
    assert state["desktopFocuses"] == 1


def test_now_screen_order_and_plain_language_boundary_are_static_contracts() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    ordered_ids = [
        'id="environmentHeading"',
        'id="nowHeadline"',
        'id="attentionPanel"',
        'id="portfolioBody"',
        'id="botsList"',
        'id="positionsList"',
        'id="leaderboardBody"',
        'id="signalsList"',
        'id="findingsList"',
        'id="recentActivity"',
    ]
    indexes = [html.index(contract) for contract in ordered_ids]
    assert indexes == sorted(indexes)
    assert "Gate-bound synthetic paper cockpit" in html
    assert "No real money · no venue or live orders" in html
    assert "no real money, account or exchange orders" in html


def test_attention_rows_render_a_vertical_text_hierarchy() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    source = html[html.index("function renderAttention") : html.index("function renderPortfolio")]

    assert ".attention-row>div{display:grid;gap:4px;min-width:0}" in html
    assert ".attention-row strong,.attention-row small{display:block}" in html
    assert ".attention-row small{color:var(--muted);line-height:1.45}" in html
    assert ".attention-row small:first-of-type{color:#b9c7d8}" in html
    assert source.index("<div><strong>") < source.index("<small>${esc(summary)}</small>")
    assert source.index("<small>${esc(summary)}</small>") < source.index(
        "<small>${esc(humanStatus(item.severity"
    )
    assert ".attention-row .action{grid-column:2" in html


def test_cockpit_range_refresh_visibility_and_last_good_contracts() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()

    assert re.findall(r'data-range="([^"]+)"', html) == [
        "24h",
        "1d",
        "3d",
        "7d",
        "1m",
        "all",
    ]
    # Scoped to #refreshRate specifically — the Signals page's #autoPollRate select
    # also has "off" and (coincidentally, 60000ms = 1m there vs 60s here) "60000"
    # options, which an unscoped regex would pick up too.
    refresh_rate_select = html[
        html.index('id="refreshRate"') : html.index("</select>", html.index('id="refreshRate"'))
    ]
    assert re.findall(r'<option value="(off|5000|15000|60000)"', refresh_rate_select) == [
        "off",
        "5000",
        "15000",
        "60000",
    ]
    assert "selectedRange=button.dataset.range" in html
    assert "document.hidden&&!manual" in html
    assert "if(document.hidden||value==='off')return" in html
    assert "if(cockpitLastGood){renderFreshness(cockpitLastGood.freshness,true)" in html
    assert "state==='Delayed'?'Stale':state" in html
    assert "cockpitLastGood=snapshot" in html
    assert "cockpitRefreshQueued=true" in html
    assert "requestedRange!==selectedRange" in html
    assert html.count("networkTimer=setInterval") == 1


def test_cockpit_refresh_queue_keeps_latest_range_and_same_range_follow_up() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    source = html[
        html.index("function refreshCockpitSnapshot") : html.index("async function loadAll")
    ]
    script = f"""
var cockpitRefreshQueued=false,cockpitRefreshPromise=null,cockpitLoading=false;
var cockpitLastGood=null,cockpitLastSuccess=0,cockpitLastError='',cockpitRefreshFailed=false;
var selectedRange='24h',calls=[],renders=[],resolvers=[];
var content={{setAttribute(){{}},removeAttribute(){{}}}};
var refresh={{setAttribute(){{}},removeAttribute(){{}},textContent:''}};
var retry={{hidden:false}};
var fetchJson=async url=>{{
  calls.push(url);return await new Promise(resolve=>resolvers.push(resolve));
}};
var renderCockpit=snapshot=>renders.push(snapshot.tag||snapshot.range);
var renderFreshness=()=>{{}},setHealthIndicator=()=>{{}};
var renderCockpitUnavailable=()=>{{}},updateDisplayStatus=()=>{{}};
{source}
var tick=()=>new Promise(resolve=>setImmediate(resolve));
var first=refreshCockpitSnapshot();await tick();
selectedRange='1d';var latest=refreshCockpitSnapshot();
resolvers.shift()({{range:'24h',tag:'stale-24h'}});await tick();
resolvers.shift()({{range:'1d',tag:'latest-1d'}});await Promise.all([first,latest]);
var sameFirst=refreshCockpitSnapshot();await tick();var sameFollow=refreshCockpitSnapshot();
resolvers.shift()({{range:'1d',tag:'before-action'}});await tick();
resolvers.shift()({{range:'1d',tag:'after-action'}});await Promise.all([sameFirst,sameFollow]);
console.log(JSON.stringify({{calls,renders}}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-"],
        input=script,
        capture_output=True,
        text=True,
        check=True,
    )
    state = json.loads(result.stdout)

    assert state["calls"] == [
        "/api/v1/cockpit?range=24h",
        "/api/v1/cockpit?range=1d",
        "/api/v1/cockpit?range=1d",
        "/api/v1/cockpit?range=1d",
    ]
    assert state["renders"] == ["latest-1d", "before-action", "after-action"]


def test_first_cockpit_failure_renders_explicit_unavailable_state_without_zeros() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    source = html[
        html.index("function renderCockpitUnavailable") : html.index("const cockpitActionIdentity")
    ]
    script = f"""
var nodes=new Map();
var node=()=>({{
  innerHTML:'',textContent:'',className:'',hidden:false,classList:{{remove(){{}}}}
}});
var document={{querySelector:selector=>{{
  if(!nodes.has(selector))nodes.set(selector,node());return nodes.get(selector);
}}}};
var selectedRange='24h',health=null;
var esc=value=>String(value??'').replace(/[&<>\"']/g,char=>({{
  '&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'
}}[char]));
var setHealthIndicator=(state,label)=>health={{state,label}},renderCockpitActionStatus=()=>{{}};
{source}
renderCockpitUnavailable(new Error('offline'));
var selectors=[
  '#nowHeadline','#freshnessList','#attentionList','#portfolioBody','#botsList',
  '#positionsList','#leaderboardBody','#signalsList','#findingsList',
  '#recentActivity','#paperTradingBody'
];
var output=selectors
  .map(selector=>nodes.get(selector).innerHTML||nodes.get(selector).textContent)
  .join(' ');
console.log(JSON.stringify({{output,health,updated:nodes.get('#cockpitUpdated').textContent,retryText:nodes.get('#portfolioBody').innerHTML}}));
"""
    state = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert state["health"] == {"state": "unavailable", "label": "Cockpit unavailable"}
    assert "unavailable" in state["output"].lower()
    assert "offline" in state["output"]
    assert state["updated"] == "No cockpit snapshot has been loaded."
    assert "$0" not in state["output"]
    assert "0 USDT" not in state["output"]
    assert "Loading retained" not in state["output"]
    assert "else renderCockpitUnavailable(error);retry.hidden=false" in html
    assert "if(cockpitRefreshFailed){refresh.textContent=`Cockpit unavailable:" in html


def test_paper_mode_recovers_from_error_color_on_valid_retry() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    function = re.search(r"function setPaperTradingMode\(snapshot\)\{.*?\n", html)
    assert function
    script = f"""
var mode={{className:'badge red',textContent:'UNAVAILABLE'}};
var document={{querySelector:()=>mode}};
{function.group(0)}
setPaperTradingMode({{mode:'SYNTHETIC_LOCAL_SIMULATOR',available:true}});
var synthetic={{...mode}};
mode.className='badge red';mode.textContent='UNAVAILABLE';
setPaperTradingMode({{mode:'RESEARCH_ONLY',available:false}});
console.log(JSON.stringify({{synthetic,research:mode}}));
"""
    state = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert state["synthetic"] == {"className": "badge green", "textContent": "SYNTHETIC PAPER"}
    assert state["research"] == {"className": "badge amber", "textContent": "RESEARCH ONLY"}
    assert "setPaperTradingMode(snapshot);" in html


def test_cockpit_action_retry_reuses_key_and_blocks_opposite_action() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    support = html[
        html.index("const cockpitActionIdentity") : html.index("function renderCockpitActionStatus")
    ]
    action = html[
        html.index("async function performCockpitActionValues") : html.index("let marketSnapshot")
    ]
    script = f"""
var cockpitActionAttempts=new Map(),calls=[],request=0,refreshes=0;
var cockpitLastGood={{capabilities:{{actions:['PAUSE_PAPER_ENTRIES','RESUME_PAPER_ENTRIES']}}}};
var asArray=value=>Array.isArray(value)?value:[],humanStatus=value=>String(value);
var crypto={{randomUUID:()=> 'stable-action-key'}};
var renderCockpitActionStatus=()=>{{}},syncCockpitActionButtons=()=>{{}};
var sharedRefresh=async()=>{{refreshes++}};
var fetch=async(url,options)=>{{
  calls.push(JSON.parse(options.body));
  if(request++===0)throw new Error('network lost');
  return {{ok:true,json:async()=>({{schema_version:1,status:'recorded'}})}};
}};
{support}
{action}
await performCockpitActionValues('PAUSE_PAPER_ENTRIES','bot-1');
var retained=[...cockpitActionAttempts.values()][0],firstError=retained.error;
await performCockpitActionValues('RESUME_PAPER_ENTRIES','bot-1');
var callsAfterOpposite=calls.length;
await performCockpitActionValues('PAUSE_PAPER_ENTRIES','bot-1');
console.log(JSON.stringify({{calls,callsAfterOpposite,firstError,remaining:cockpitActionAttempts.size,refreshes}}));
"""
    state = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert state["callsAfterOpposite"] == 1
    assert [call["idempotency_key"] for call in state["calls"]] == [
        "stable-action-key",
        "stable-action-key",
    ]
    assert "same idempotency key" in state["firstError"]
    assert state["remaining"] == 0
    assert state["refreshes"] == 1
    assert "retry.hidden" not in action


def test_cockpit_unavailable_and_progress_rendering_never_fabricate_values() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    portfolio_source = html[
        html.index("function renderPortfolio") : html.index("function drawEquityChart")
    ]
    bots_source = html[html.index("function renderBots") : html.index("function renderPositions")]

    assert "portfolio.available!==true" in portfolio_source
    assert "Portfolio unavailable" in portfolio_source
    assert "$0" not in portfolio_source
    assert "0 USDT" not in portfolio_source
    assert "no trades" not in portfolio_source.lower()
    assert "completion" not in bots_source.lower()
    assert "conditions_unavailable_reason" in bots_source
    for forbidden_control in ("Force entry", "Close position", "Cancel order", "Stop all"):
        assert f">{forbidden_control}<" not in html


def test_global_pause_action_mode_health_and_empty_table_contracts() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    bots_source = html[html.index("function renderBots") : html.index("function renderPositions")]
    paper_source = html[
        html.index("function renderPaperTrading") : html.index("function renderCockpit")
    ]

    assert "Pause new entries for all paper bots" in bots_source
    assert "Resume new entries for all paper bots" in bots_source
    assert (
        "Open synthetic positions continue following their retained exit and risk rules"
        in bots_source
    )
    assert bots_source.count("data-cockpit-action") == 1
    assert 'id="cockpitActionStatus"' in html
    assert "const cockpitActionAttempts=new Map()" in html
    assert "Retry same action" in html
    assert "No paper execution lane is active" not in html
    assert "no synthetic wallet ledger" not in html
    assert "every execution capability is absent or disabled in S2" not in html
    assert "offline research only" not in html
    assert "demo, paper, and live trading are disabled" not in html
    assert '<span class="dot" id="healthDot"' in html
    assert '<span class="dot live" id="healthDot"' not in html
    assert '<span class="visually-hidden">${esc(detail)}</span>' in html
    assert 'colspan="7">No gate-approved paper bot is retained.' in paper_source
    assert 'colspan="6">No synthetic position is open' in paper_source
    assert 'colspan="6">No retained synthetic signal watch is active.' in paper_source


def test_fraction_percent_formatter_is_exact_and_unavailable_reasons_are_preserved() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    function = re.search(r"function fractionPercent\(value\)\{.*?\n\}", html, re.DOTALL)
    assert function
    script = (
        function.group(0) + "\nconsole.log(JSON.stringify(['0.12345','-0.005','1','bad',null]"
        ".map(fractionPercent)));"
    )
    values = json.loads(
        subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    )

    assert values == ["12.35%", "-0.50%", "100.00%", None, None]
    leaderboard = html[
        html.index("function renderLeaderboard") : html.index("function renderSignals")
    ]
    assert "row.return_unavailable_reason" in leaderboard
    assert "row.allocation_unavailable_reason" in leaderboard
    assert "moneyText(row.allocated_capital,'USDT')" in leaderboard


def test_equity_chart_has_exact_accessible_table_and_chart_only_parses_coordinates() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    portfolio_source = html[
        html.index("function renderPortfolio") : html.index("function renderBots")
    ]

    assert 'id="equityChart"' in portfolio_source
    assert 'role="img"' in portfolio_source
    assert 'aria-describedby="equityTable"' in portfolio_source
    assert 'aria-details="equityTable"' in portfolio_source
    assert "Every retained equity point plotted" in portfolio_source
    assert "points.map(point=>" in portfolio_source
    assert "Number.parseFloat(point?.equity)" in portfolio_source
    assert "Number.parseFloat" not in html[: html.index("function drawEquityChart")]
    assert "Math.min(...values)" not in portfolio_source
    assert "for(const value of values)" in portfolio_source


def test_dashboard_inline_javascript_parses() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    scripts = [
        body
        for attributes, body in re.findall(r"<script([^>]*)>(.*?)</script>", html, re.DOTALL)
        if "src=" not in attributes
    ]
    result = subprocess.run(
        ["node", "--check", "-"],
        input="\n".join(scripts),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_market_success_then_failure_clears_all_prior_evidence_contract() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    clear_start = html.index("function clearMarketEvidence")
    clear_end = html.index("async function loadMarket", clear_start)
    clear_source = html[clear_start:clear_end]
    for contract in (
        "marketSnapshot=undefined",
        "canvas.width=canvas.width",
        "canvas.classList.add('stale')",
        "#candleTable",
        "#marketMarkers",
        "#marketProvenance",
        "setBacktestSignal(status",
    ):
        assert contract in clear_source
    catch_source = html[html.index("}catch(error){const message=`Market evidence unavailable") :]
    assert "clearMarketEvidence(message)" in catch_source


def test_market_canvas_aria_agrees_with_candle_fill_counts_and_capabilities() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    function = re.search(r"function marketCanvasLabel\(data\)\{.*?\n\}", html, re.DOTALL)
    assert function
    script = (
        function.group(0) + "\nconst base={candles:[{},{}],capabilities:{market_chart:'AVAILABLE',"
        "trade_markers:'NOT_AVAILABLE'}};"
        "console.log(JSON.stringify([marketCanvasLabel({...base,markers:[]}),"
        "marketCanvasLabel({...base,markers:[{}],capabilities:{...base.capabilities,"
        "trade_markers:'AVAILABLE'}})]));"
    )
    labels = json.loads(
        subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    )
    assert labels[0].startswith("2 historical candles with no retained fill markers.")
    assert "trade markers NOT_AVAILABLE" in labels[0]
    assert labels[1].startswith("2 historical candles with 1 retained fill marker.")
    assert "trade markers AVAILABLE" in labels[1]
    assert "canvas.setAttribute('aria-label',marketCanvasLabel(marketSnapshot))" in html
    assert "markersAvailable!==Boolean(payload.markers.length)" in html
    assert "!payload.candles.length" in html


def test_dashboard_status_semantics_fail_closed_before_positive_tokens() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    assert "['CONSTRAINED','DISABLED','BLOCKED','FAILED','FAIL','NOT_ELIGIBLE'" in html
    assert "['PASS','READY','VALID','FROZEN','COMPLETE','COMPLETED'" in html
    assert html.index("negative.some") < html.index("positive.some")
    assert "includes('READY')" not in html
    assert "Signal eligibility" in html
    assert "no blended score" in html
    assert "d.strategy_eligibility||{}" in html
    assert "Risk-signal flow" in html
    assert "Typed risk-signal path" in html
    assert "d.risk_signal_flow||{}" in html


def test_market_snapshot_uses_canonical_bars_and_backtest_markers() -> None:
    root = Path(__file__).resolve().parents[1]
    snapshot = build_market_snapshot(root, "BTCUSDT", "5m", 240)
    assert snapshot["schema_version"] == 1
    assert snapshot["generated_at"]
    assert len(snapshot["candles"]) == 240
    assert snapshot["candles"] == sorted(snapshot["candles"], key=lambda row: row["time"])
    assert snapshot["freshness"] == "HISTORICAL_FROZEN"
    assert snapshot["capabilities"]["live_orders"] == "DISABLED"
    assert snapshot["markers"]
    assert all(marker["environment"] == "backtest" for marker in snapshot["markers"])
    assert snapshot["evidence"]["candles"].endswith("BTCUSDT_5m.parquet")
    assert snapshot["capabilities"]["trade_markers"] == "AVAILABLE"
    assert snapshot["provenance"]["dataset_manifest"]["dataset_id"] == snapshot["dataset"]
    assert snapshot["provenance"]["dataset_manifest"]["source"] == snapshot["source"]
    assert snapshot["provenance"]["candle_artifact"]["status"] == "VERIFIED"
    assert snapshot["provenance"]["candle_artifact"]["sha256"] == (
        "d4d6b3306c44e242f3fb7f71c44bacabf9a6af1f1f8d507ca2de0853b6a727d0"
    )
    assert snapshot["provenance"]["fill_artifact"]["status"] == "VERIFIED"
    assert snapshot["provenance"]["fill_artifact"]["sha256"] == (
        "7255e8dcd31f4c1bfe64fe783fb29ef2306ad6db3f69ead7533227f835c60f91"
    )


@pytest.mark.parametrize(
    ("fills", "expected_status"),
    [(0, "VERIFIED_NO_MATCHING_FILLS"), (None, "MISSING")],
)
def test_market_snapshot_never_advertises_zero_or_missing_fills(
    tmp_path: Path, fills: int | None, expected_status: str
) -> None:
    _write_market_fixture(tmp_path, fills)
    snapshot = build_market_snapshot(tmp_path, "BTCUSDT", "5m", 50)
    assert snapshot["markers"] == []
    assert snapshot["capabilities"]["trade_markers"] == "NOT_AVAILABLE"
    assert snapshot["provenance"]["fill_artifact"]["status"] == expected_status
    assert snapshot["provenance"]["fill_artifact"]["matching_fills"] == 0


def test_market_snapshot_marks_empty_candles_unavailable(tmp_path: Path) -> None:
    _write_market_fixture(tmp_path, fills=0, candles=0)
    snapshot = build_market_snapshot(tmp_path, "BTCUSDT", "5m", 50)
    assert snapshot["candles"] == []
    assert snapshot["markers"] == []
    assert snapshot["capabilities"]["market_chart"] == "NOT_AVAILABLE"
    assert snapshot["capabilities"]["trade_markers"] == "NOT_AVAILABLE"


def test_market_snapshot_closes_duckdb_connection_on_query_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_market_fixture(tmp_path, fills=None)

    class BrokenConnection:
        closed = False

        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("retained query failure")

        def close(self) -> None:
            self.closed = True

    connection = BrokenConnection()
    monkeypatch.setattr("tios.services.dashboard_api.market.duckdb.connect", lambda: connection)
    with pytest.raises(RuntimeError, match="retained query failure"):
        build_market_snapshot(tmp_path, "BTCUSDT", "5m", 50)
    assert connection.closed is True


def test_market_snapshot_fails_closed_on_manifest_hash_mismatch(tmp_path: Path) -> None:
    _write_market_fixture(tmp_path)
    manifest_path = tmp_path / "artifacts/datasets/DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["tables"]["BTCUSDT_5m"]["parquet_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="hash does not match"):
        build_market_snapshot(tmp_path, "BTCUSDT", "5m", 50)


def test_market_snapshot_rejects_unapproved_inputs() -> None:
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="unsupported symbol"):
        build_market_snapshot(root, "../../SECRET", "5m", 240)


@pytest.mark.parametrize("age", [timedelta(), timedelta(hours=23, minutes=59)])
def test_dashboard_check_pass_requires_fresh_machine_readable_artifact(
    tmp_path: Path, age: timedelta
) -> None:
    artifact = tmp_path / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "gate": "check",
                "command": "make check",
                "status": "PASS",
                "includes_slow_data_tests": False,
                "includes_dependency_audit": False,
                "generated_at": (datetime.now(tz=UTC) - age).isoformat(),
            }
        )
    )
    checks = build_status(tmp_path)["checks"]
    assert checks["status"] == "PASS"
    assert checks["known_passing"] is True
    assert checks["includes_dependency_audit"] is False
    assert checks["includes_slow_data_tests"] is False
    assert checks["required_gate"] == {"command": "make required", "status": "UNKNOWN"}


def test_dashboard_distinguishes_full_gate_from_fast_gate(tmp_path: Path) -> None:
    """Both gates write the same file; the projection must not conflate their coverage."""
    artifact = tmp_path / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "gate": "check-full",
                "command": "make check-full",
                "status": "PASS",
                "includes_slow_data_tests": True,
                "includes_dependency_audit": False,
                "generated_at": datetime.now(tz=UTC).isoformat(),
            }
        )
    )

    checks = build_status(tmp_path)["checks"]

    assert checks["status"] == "PASS"
    assert checks["gate"] == "check-full"
    assert checks["command"] == "make check-full"
    assert checks["includes_slow_data_tests"] is True


def test_dashboard_rejects_superseded_schema_two_artifact(tmp_path: Path) -> None:
    """A pre-split artifact cannot vouch for the post-split contract."""
    artifact = tmp_path / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "gate": "check",
                "command": "make check",
                "status": "PASS",
                "includes_dependency_audit": False,
                "generated_at": datetime.now(tz=UTC).isoformat(),
            }
        )
    )

    checks = build_status(tmp_path)["checks"]

    assert checks["status"] == "UNKNOWN"
    assert checks["known_passing"] is False


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"schema_version": 2, "gate": "check", "command": "make check", "status": "UNKNOWN"},
        {
            "schema_version": 2,
            "gate": "check",
            "command": "make check",
            "status": "PASS",
            "includes_dependency_audit": False,
            "generated_at": (datetime.now(tz=UTC) - timedelta(days=2)).isoformat(),
        },
        {
            "schema_version": 2,
            "gate": "check",
            "command": "make check",
            "status": "PASS",
            "includes_dependency_audit": False,
            "generated_at": (datetime.now(tz=UTC) + timedelta(days=2)).isoformat(),
        },
    ],
)
def test_dashboard_check_state_fails_closed_to_unknown(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    artifact = tmp_path / "artifacts/quality/check.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(payload))
    checks = build_status(tmp_path)["checks"]
    assert checks["status"] == "UNKNOWN"
    assert checks["known_passing"] is False


def test_workspace_decision_recording_is_validated_and_retained(tmp_path: Path) -> None:
    (tmp_path / "todos").mkdir()
    (tmp_path / "todos/11_ai_agent_eval.md").write_text(
        "# Initiative 11\n\n## T-011-05 First real runs\n- Status: **DEFERRED-CREDENTIALS**.\n"
    )
    result = record_workspace_decision(
        tmp_path,
        {"task_id": "T-011-05", "choice": "keep_deferred"},
    )
    assert result["recorded"]["choice_label"] == "Keep deferred"
    decision_path = tmp_path / "artifacts/human_decisions/workspace_decisions.jsonl"
    assert decision_path.is_file()
    status = build_status(tmp_path)
    action = status["workspace_actions"][0]
    assert action["latest_decision"]["choice"] == "keep_deferred"

    with pytest.raises(ValueError, match="unknown workspace action choice"):
        record_workspace_decision(tmp_path, {"task_id": "T-011-05", "choice": "place_order"})


def test_workspace_decision_audit_refuses_parent_symlink_escape(tmp_path: Path) -> None:
    (tmp_path / "todos").mkdir()
    (tmp_path / "todos/11_ai_agent_eval.md").write_text(
        "# Initiative 11\n\n## T-011-05 First real runs\n- Status: **DEFERRED-CREDENTIALS**.\n"
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "human_decisions").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="audit path"):
        record_workspace_decision(
            tmp_path,
            {
                "task_id": "T-011-05",
                "choice": "keep_deferred",
                "idempotency_key": "decision-symlink",
            },
        )
    assert not (outside / "workspace_decisions.jsonl").exists()


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "::1", "localhost"])
def test_dashboard_accepts_loopback_hosts(host: str) -> None:
    assert is_loopback_host(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", "example.com", ""])
def test_dashboard_refuses_non_loopback_hosts(host: str) -> None:
    assert not is_loopback_host(host)


def _handle_request(raw_request: bytes, root: Path) -> bytes:
    handler = object.__new__(Handler)
    handler.root = root
    handler.html = "dashboard"
    handler.rfile = BytesIO(raw_request)
    handler.wfile = BytesIO()
    handler.client_address = ("127.0.0.1", 1)
    handler.server = SimpleNamespace(server_name="test", server_port=80)
    handler.close_connection = True
    handler.handle_one_request()
    return handler.wfile.getvalue()


def test_live_status_api_contract_without_listening_server(tmp_path: Path) -> None:
    response = _handle_request(b"GET /api/v1/status HTTP/1.1\r\nHost: localhost\r\n\r\n", tmp_path)
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    payload = json.loads(body)
    assert payload["schema_version"] == 1
    assert payload["checks"]["status"] == "UNKNOWN"
    assert payload["observation"]["state"] == "MISSING"


def test_eth_signal_api_runs_fixed_read_only_verifier() -> None:
    root = Path(__file__).resolve().parents[1]
    response = _handle_request(b"GET /api/v1/eth-signal HTTP/1.1\r\nHost: localhost\r\n\r\n", root)
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 200 " in headers
    payload = json.loads(body)
    assert payload["strategy_version_id"] == "SV-418ab5d64825c74b"
    assert payload["signal_count"] == 511
    assert payload["risk_decision"] == "BLOCK"
    assert payload["capabilities"]["order_creation"] is False


def test_eth_signal_api_fails_closed_without_fixed_verifier(tmp_path: Path) -> None:
    response = _handle_request(
        b"GET /api/v1/eth-signal HTTP/1.1\r\nHost: localhost\r\n\r\n", tmp_path
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 503 " in headers
    assert json.loads(body) == {
        "schema_version": 1,
        "error": "ETH signal verifier is unavailable",
    }


def test_live_market_api_schema_contract_without_listening_server(tmp_path: Path) -> None:
    _write_market_fixture(tmp_path)
    response = _handle_request(
        b"GET /api/v1/market?symbol=BTCUSDT&interval=5m&limit=50 HTTP/1.1\r\n"
        b"Host: localhost\r\n\r\n",
        tmp_path,
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    payload = json.loads(body)
    assert payload["schema_version"] == 1
    assert payload["provenance"]["dataset_manifest"]["status"] == "VERIFIED"
    assert payload["capabilities"]["live_orders"] == "DISABLED"


def test_live_market_api_error_schema_contract_without_listening_server(tmp_path: Path) -> None:
    response = _handle_request(
        b"GET /api/v1/market?symbol=BTCUSDT HTTP/1.1\r\nHost: localhost\r\n\r\n",
        tmp_path,
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 400 " in headers
    payload = json.loads(body)
    assert payload["schema_version"] == 1
    assert "manifest" in payload["error"]


def test_live_search_api_schema_contract_without_listening_server() -> None:
    root = Path(__file__).resolve().parents[1]
    response = _handle_request(
        b"GET /api/v1/search?q=DCA&limit=10 HTTP/1.1\r\nHost: localhost\r\n\r\n",
        root,
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    payload = json.loads(body)
    assert payload["schema_version"] == 1
    assert payload["capabilities"]["writes"] == "DISABLED"
    assert payload["capabilities"]["order_endpoint"] == "ABSENT"
    assert payload["results"]
    assert any(row["kind"] == "strategy" for row in payload["results"])


def test_live_search_api_error_schema_contract_without_listening_server() -> None:
    root = Path(__file__).resolve().parents[1]
    response = _handle_request(
        b"GET /api/v1/search?q=toolong&limit=0 HTTP/1.1\r\nHost: localhost\r\n\r\n",
        root,
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 400 " in headers
    payload = json.loads(body)
    assert payload["schema_version"] == 1
    assert "limit" in payload["error"]


def test_live_stage_gates_api_schema_contract_without_listening_server() -> None:
    root = Path(__file__).resolve().parents[1]
    response = _handle_request(
        b"GET /api/v1/stage-gates HTTP/1.1\r\nHost: localhost\r\n\r\n",
        root,
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 200 " in headers
    assert b"Content-Type: application/json" in headers
    payload = json.loads(body)
    assert payload["schema_version"] == 1
    assert payload["status"] == "BLOCKED_BY_GATES"
    assert payload["capabilities"]["writes"] == "DISABLED"
    assert payload["capabilities"]["order_endpoint"] == "ABSENT"
    assert payload["s3_paper_demo"]["status"] == "NOT_READY"
    assert payload["s4_live"]["status"] == "NOT_READY"


def test_legacy_api_paths_are_explicitly_removed(tmp_path: Path) -> None:
    response = _handle_request(b"GET /api/status HTTP/1.1\r\nHost: localhost\r\n\r\n", tmp_path)
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 410 " in headers
    payload = json.loads(body)
    assert payload == {"schema_version": 1, "error": "legacy API removed; use /api/v1"}


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def test_dashboard_api_rejects_prohibited_methods_without_listening_server(
    tmp_path: Path, method: str
) -> None:
    response = _handle_request(
        f"{method} /api/v1/status HTTP/1.1\r\nHost: localhost\r\n\r\n".encode(), tmp_path
    )
    assert response.startswith(b"HTTP/1.0 501")


def test_workspace_decision_post_is_the_only_allowed_write_path(tmp_path: Path) -> None:
    (tmp_path / "todos").mkdir()
    (tmp_path / "todos/11_ai_agent_eval.md").write_text(
        "# Initiative 11\n\n## T-011-05 First real runs\n- Status: **DEFERRED-CREDENTIALS**.\n"
    )
    body = b'{"task_id":"T-011-05","choice":"keep_deferred","idempotency_key":"decision-test-1"}'
    response = _handle_request(
        b"POST /api/v1/workspace-actions/decision HTTP/1.1\r\n"
        b"Host: localhost\r\n"
        b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body,
        tmp_path,
    )
    headers, payload = response.split(b"\r\n\r\n", 1)
    assert b" 201 " in headers
    assert json.loads(payload)["recorded"]["choice"] == "keep_deferred"
    replay = _handle_request(
        b"POST /api/v1/workspace-actions/decision HTTP/1.1\r\n"
        b"Host: localhost\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body,
        tmp_path,
    )
    assert json.loads(replay.split(b"\r\n\r\n", 1)[1])["idempotent"] is True
    decision_lines = (
        (tmp_path / "artifacts/human_decisions/workspace_decisions.jsonl").read_text().splitlines()
    )
    assert len(decision_lines) == 1

    blocked = _handle_request(
        b"POST /api/v1/orders HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}",
        tmp_path,
    )
    assert b" 404 " in blocked.split(b"\r\n\r\n", 1)[0]


def _demo_lane_render_source() -> str:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    start = html.index("function renderDemoLane(lane){")
    end = html.index("async function loadDemoLane(){", start)
    return html[start:end]


def test_demo_lane_card_pins_stage_b_and_authority_labels() -> None:
    source = _demo_lane_render_source()
    for label in (
        "Stage B decision evidence",
        "DEMO / FAKE MONEY",
        "NO REAL MONEY",
        "AUTHORITY:",
        "DIAGNOSTIC ONLY",
        "NO PROMOTION",
        "NO AUTO-TUNE",
        "lane.execution_authority",
        "lane.operational_status",
        "lane.stage_b",
    ):
        assert label in source, label


def test_demo_lane_card_renders_aggregate_null_and_the_ten_totals() -> None:
    source = _demo_lane_render_source()
    # aggregate=null path shows a pending message and never a PnL value.
    assert "Aggregate pending" in source
    for field in (
        "closed_count",
        "positive_count",
        "negative_count",
        "flat_count",
        "entry_exec_value_total",
        "exit_exec_value_total",
        "gross_quote_total",
        "quote_fee_total",
        "base_fee_total",
        "net_quote_total",
    ):
        assert "agg." + field in source, field


def test_demo_lane_card_reads_only_coins_and_portfolio_not_flat_legacy_fields() -> None:
    """The rich operator view reads lane.coins / lane.portfolio — never a flat legacy lane.* object
    (the Wave-3 aggregate-only card exposed none of these, and the operator card keeps that shape at
    the top level, moving the per-coin detail into the coins array)."""
    source = _demo_lane_render_source()
    for legacy in (
        "lane.orders",
        "lane.wallet",
        "lane.pnl",
        "lane.positions",
        "lane.position",
        "lane.heartbeat",
        "lane.windows",
        "lane.rules",
        "lane.divergence",
        "lane.pid",
        "lane.counts",
        "position_base",
        "walletTotal",
        "data-lane-range",
        "Order history",
    ):
        assert legacy not in source, legacy
    assert "lane.coins" in source
    assert "lane.portfolio" in source


def test_demo_lane_card_renders_rich_multi_coin_operator_view() -> None:
    source = _demo_lane_render_source()
    # Per-coin loop over the coins array, with the live operator fields.
    assert "coins.map(coinHtml)" in source
    for token in (
        "c.position",
        "c.protection",
        "c.watching",
        "c.trade_history",
        "unrealised_pnl_usd",
        "unrealised_pnl_pct",
        "time_in_trade_seconds",
        "distance_to_entry_pct",
        "volume_pct_of_gate",
        "disaster_stop_price_usd",
        "venue_resting_stop_trigger_usd",
        "realised_pnl_usd",
    ):
        assert token in source, token
    # Corrected banner reflects the actual aggregate state, and a portfolio roll-up is present.
    assert "coins in a position" in source
    assert "flat / watching" in source
    assert "pf.realised_pnl_usd" in source
    assert "pf.open_exposure_usd" in source
    # Safety labels stay visible on the operator card.
    for label in ("DIAGNOSTIC ONLY", "authority NONE", "UNVALIDATED"):
        assert label in source, label


def test_demo_lane_card_renders_confluence_activity_confidence_and_signals() -> None:
    source = _demo_lane_render_source()
    # A read-only confluence section reads the new arrays and maps each coin through actHtml.
    assert "lane.activity" in source
    assert "lane.activity_summary" in source
    assert "activity.map(actHtml)" in source
    assert "Confluence activity" in source
    # Per-coin confidence score (number + bar) and the agreeing strategies/timeframes.
    for token in (
        "a.confidence_score",
        "a.decision",
        "a.bullish",
        "a.bearish",
        "confidence",
        "bullish:",
        "bearish:",
    ):
        assert token in source, token
    # Strategy@timeframe rendering of the contributor pairs, all escaped.
    assert "s.strategy" in source and "s.timeframe" in source
    assert "esc(String(s.strategy))" in source
    # activity_summary is surfaced (coins scored / long / confidence).
    for token in ("asum.coins_long", "asum.coins_scored", "asum.highest_confidence"):
        assert token in source, token
    # Fake-money / authority / validation labels stay pinned on the confluence section too.
    for label in ("DIAGNOSTIC ONLY", "authority NONE", "UNVALIDATED", "Fake money"):
        assert label in source, label


def test_demo_lane_route_is_the_only_stage_b_surface_and_authority_is_none(
    tmp_path: Path,
) -> None:
    response = _handle_request(
        b"GET /api/v1/demo-lane HTTP/1.1\r\nHost: localhost\r\n\r\n", tmp_path
    )
    headers, body = response.split(b"\r\n\r\n", 1)
    assert b" 200 " in headers
    payload = json.loads(body)
    assert set(payload) == {
        "schema_version",
        "operational_status",
        "kill_switch",
        "environment",
        "real_money",
        "execution_authority",
        "validation_state",
        "promotion_eligible",
        "auto_tune",
        "coins",
        "portfolio",
        "activity",
        "activity_summary",
        "stage_b",
    }
    assert payload["schema_version"] == 1
    assert payload["execution_authority"] == "NONE"
    assert payload["real_money"] is False
    assert payload["promotion_eligible"] is False
    assert payload["auto_tune"] is False
    assert payload["stage_b"] == {"status": "NOT_ACTIVATED", "cohort_size": 30, "series": []}
    # The Stage B EVIDENCE field stays aggregate-only: no per-trade surface leaks into it.
    stage_b_lowered = json.dumps(payload["stage_b"]).lower().encode()
    for token in (b"order", b"wallet", b"pnl", b"position", b"heartbeat", b"pid", b"signal"):
        assert token not in stage_b_lowered, token

    # There is no separate Stage B route; readiness is a field on this one route only.
    missing = _handle_request(b"GET /api/v1/stage-b HTTP/1.1\r\nHost: localhost\r\n\r\n", tmp_path)
    missing_headers, missing_body = missing.split(b"\r\n\r\n", 1)
    assert b" 200 " not in missing_headers
    assert b"cohort" not in missing_body and b"series" not in missing_body


def test_demo_lane_action_response_body_is_exactly_four_fields(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts/demo_eth_lane.py").write_text("# stand-in\n")
    body = b'{"action":"STOP","idempotency_key":"dash-stop-1"}'
    response = _handle_request(
        b"POST /api/v1/demo-lane-actions HTTP/1.1\r\n"
        b"Host: localhost\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n\r\n".encode()
        + body,
        tmp_path,
    )
    headers, payload = response.split(b"\r\n\r\n", 1)
    assert b" 201 " in headers
    assert json.loads(payload) == {
        "schema_version": 2,
        "ok": True,
        "action": "STOP",
        "state": "STOPPED",
    }


def test_overview_has_demo_lane_control_panel_with_four_allowlisted_buttons() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    now_section = html[html.index('id="now"') : html.index('id="nowHeadline"')]
    assert 'id="demoLaneControlPanel"' in now_section
    # Four buttons wired to the allowlisted demo-lane actions (rendered by renderLaneControls).
    for action in ("START_ACTIVITY", "START", "RUN_ONCE", "STOP"):
        assert f'data-overview-lane="{action}"' in html
    for label in ("Start Activity Lane", "Start ETH Lane (loop)", "Run Once (ETH)", ">Stop<"):
        assert label in html
    # Every button POSTs to the same audited allowlisted endpoint; no free-form input field.
    assert "/api/v1/demo-lane-actions" in html
    assert "async function overviewLaneAction" in html
    assert "crypto.randomUUID()" in html
    assert "<input" not in now_section
    # Confirm-on-click for the state-changing starts and stop.
    assert "confirm(" in html
    # Running/stopped drives disable: Start disabled while running, Stop disabled while stopped.
    assert "const running=status==='RUNNING'||status==='STOPPING'" in html
    assert "startDis=running?'disabled':'',stopDis=running?'':'disabled'" in html
    # Fake-money / DIAGNOSTIC / authority-NONE labels stay visible next to the controls.
    for badge in ("DEMO / FAKE MONEY", "NO REAL MONEY", "AUTHORITY: NONE", "DIAGNOSTIC ONLY"):
        assert badge in now_section


def test_overview_demo_lane_live_auto_refresh_is_guarded_and_visibility_aware() -> None:
    html = (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()
    # ~5s auto-poll that re-uses fetchJson + renderDemoLane, no full page reload.
    assert "const DEMO_LANE_REFRESH_MS=5000" in html
    assert "setInterval(()=>pollDemoLane(false),DEMO_LANE_REFRESH_MS)" in html
    assert "async function pollDemoLane(force)" in html
    assert "await fetchJson('/api/v1/demo-lane')" in html
    assert "renderDemoLane(lane)" in html
    # Overlap guard: skip a tick while the previous fetch is still in flight.
    assert "if(demoLaneInFlight)return" in html
    # Pause when the tab is hidden, resume on visibilitychange.
    assert "document.hidden" in html
    assert "visibilitychange" in html
    assert "pollDemoLane(false)" in html
    # Scroll position and any open <details> are preserved across the re-render.
    assert "const y=window.scrollY" in html
    assert "details[open]" in html
    assert "window.scrollTo(0,y)" in html
    # Live indicator shows "updated Xs ago".
    assert 'id="demoLaneLive"' in html
    assert "function updateDemoLaneLive" in html
    assert "updated ${" in html and "s ago" in html
    # schema_version handling unchanged: the client still requires schema_version === 1.
    assert "payload.schema_version!==1" in html


def _dashboard_html() -> str:
    return (
        Path(__file__).resolve().parents[1] / "src/tios/services/dashboard_ui/dashboard.html"
    ).read_text()


def test_control_center_has_three_labeled_sections_with_all_wired_buttons() -> None:
    html = _dashboard_html()
    now_section = html[html.index('id="now"') : html.index('id="nowHeadline"')]
    assert 'id="demoLaneControlPanel"' in now_section
    # Three labeled sections.
    for label in (">Lane control<", ">Reports<", ">Research<"):
        assert label in now_section, label
    # Lane control: five allowlisted actions, all rendered by renderLaneControls; START_MULTI added.
    for action in ("START", "START_ACTIVITY", "START_MULTI", "RUN_ONCE", "STOP"):
        assert f'data-overview-lane="{action}"' in html, action
    assert "Start Multi Lane" in html
    # Reports: three read-only view endpoints, each loaded on click via the escaped report panel.
    for endpoint in ("/api/v1/demo-trades", "/api/v1/demo-status", "/api/v1/research-findings"):
        assert f'data-demo-report="{endpoint}"' in now_section, endpoint
    for report_label in (">Demo Trades<", ">Demo Status<", ">Research Findings<"):
        assert report_label in now_section, report_label
    assert 'id="demoReportPanel"' in now_section
    assert "async function loadDemoReport" in html
    assert "await fetchJson(url)" in html  # reuses the schema_version===1 fetch path
    # The report panel is written with textContent (escapes every value); never innerHTML.
    assert "panel.textContent=" in html
    # Research: a confirmed background START_RESEARCH launch with the honest 'no orders' note.
    assert 'id="runResearchSearch"' in now_section
    assert "async function runResearchSearch" in html
    assert "action:'START_RESEARCH'" in html
    assert "runs in background" in now_section.lower()
    assert "no orders" in now_section.lower()
    assert "crypto.randomUUID()" in html
    # Honest research framing stays present next to the controls (LEADS, not validated edge).
    assert "LEADS" in now_section
    assert "NOT validated edge" in now_section
    assert "confounded by multiple testing and cross-coin correlation" in now_section
    assert "UNVALIDATED" in now_section
    # Safety labels stay visible; no free-form input field anywhere in the panel.
    for badge in ("DEMO / FAKE MONEY", "NO REAL MONEY", "AUTHORITY: NONE", "DIAGNOSTIC ONLY"):
        assert badge in now_section
    assert "<input" not in now_section
    # Start/Stop remain confirm()-gated, including the new START_MULTI.
    assert "action==='START_MULTI'" in html


def test_control_center_report_endpoints_return_schema_version_1(tmp_path: Path) -> None:
    for endpoint in ("demo-trades", "demo-status", "research-findings"):
        response = _handle_request(
            f"GET /api/v1/{endpoint} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode(), tmp_path
        )
        headers, body = response.split(b"\r\n\r\n", 1)
        assert b" 200 " in headers, endpoint
        payload = json.loads(body)
        # The client fetchJson gate requires schema_version === 1; the read-only views satisfy it
        # and degrade gracefully (never a 500) even against an empty root.
        assert payload["schema_version"] == 1, endpoint
        assert "available" in payload and "report" in payload, endpoint


def _live_section() -> str:
    html = _dashboard_html()
    start = html.index('<section id="live" class="view active"')
    return html[start : html.index('<section id="settings-integration"', start)]


def _live_render_source() -> str:
    html = _dashboard_html()
    start = html.index("// --- Live cockpit:")
    return html[start : html.index("async function pollLiveFeed(){", start)]


def test_watch_group_holds_live_and_wallet_with_live_as_the_landing_view() -> None:
    html = _dashboard_html()
    watch = html[html.index('<div class="nav-label">Watch</div>') : html.index('id="labToggle"')]
    # WATCH contains exactly Live + Wallet; Wallet keeps the pre-existing "wallets" view id.
    assert re.findall(r'<button[^>]+data-workspace="([^"]+)"', watch) == ["live", "wallets"]
    assert ">Wallet</button>" in watch
    assert "wallets:[['wallets-demo','Demo'],['wallets-real','Real']]" in html
    # Live is the default landing view: static active markup, active state, and the init call.
    assert '<button class="active" data-workspace="live" aria-current="page">Live</button>' in watch
    assert "let activeWorkspace='live',activeView='live'" in html
    assert "showWorkspace('live');loadAll()" in html


def test_lab_group_is_collapsed_by_default_and_persists_state_in_localstorage() -> None:
    html = _dashboard_html()
    lab = html[html.index('id="labToggle"') : html.index("</nav>\n    </div></div>")]
    # A plain disclosure button, collapsed by default (hidden + aria-expanded="false").
    assert 'aria-expanded="false" aria-controls="labGroup"' in lab
    assert 'id="labGroup" aria-label="Trading OS lab workspaces" hidden' in lab
    assert ".nav[hidden]{display:none}" in html
    # All ten pre-existing pages stay reachable inside the group, none deleted; the read-only
    # Automation control map joins them.
    assert re.findall(r'<button[^>]+data-workspace="([^"]+)"', lab) == [
        "now",
        "signals",
        "trading",
        "testing",
        "research",
        "operations",
        "automation-map",
        "library",
        "skills",
        "todos",
        "settings",
    ]
    # One-click toggle, no dependency, state remembered across reloads via localStorage.
    assert "const LAB_GROUP_KEY='tios.nav.lab.expanded'" in html
    assert "labToggle?.addEventListener('click',()=>setLabExpanded(labGroup.hidden))" in html
    assert "localStorage.setItem(LAB_GROUP_KEY,expanded?'1':'0')" in html
    assert "localStorage.getItem(LAB_GROUP_KEY)==='1'" in html
    # Only an explicit stored '1' expands it, so a fresh browser lands collapsed.
    assert "labToggle.setAttribute('aria-expanded',String(expanded))" in html
    assert "labGroup.hidden=!expanded" in html


def test_live_page_has_the_four_panels_in_order_reading_the_named_endpoints() -> None:
    section = _live_section()
    ordered = [
        'id="liveStatusPanel"',
        'id="liveEventsPanel"',
        'id="liveAgreementPanel"',
        'id="livePositionsPanel"',
        'id="liveEquityBody"',
    ]
    indexes = [section.index(panel) for panel in ordered]
    assert indexes == sorted(indexes)
    html = _dashboard_html()
    # (a) status + (b) events read /api/v1/live-feed; (d) equity reads /api/v1/equity-curve.
    assert "await fetchJson('/api/v1/live-feed')" in html
    assert "await fetchJson('/api/v1/equity-curve')" in html
    assert "renderLiveStatus(feed);renderLiveEvents(feed)" in html
    source = _live_render_source()
    for field in ("lane.status", "lane.mode", "lane.coins_scored", "lane.scan_age_seconds"):
        assert field in source, field
    assert "lane.next_scan_eta_seconds" in source
    assert "7 strategies × 3 timeframes" in source
    assert "next scan in " in source and "last scan " in source
    for field in ("e.kind", "e.headline", "e.detail", "e.agreement", "e.pnl_pct", "e.age_seconds"):
        assert field in source, field
    assert "feed.event_count" in source and "feed.truncated" in source
    assert "LIVE_EVENT_CAP=40" in html and "events.slice(0,LIVE_EVENT_CAP)" in source
    assert (
        "LIVE_EVENT_TONE={ENTER:'green',EXIT:'cyan',STOP_ARMED:'amber',SCAN:'',REJECT:'red'}"
        in html
    )
    # (c) the leaderboard reuses the already-shipped demo-lane activity arrays, no new endpoint.
    for field in ("lane.activity", "lane.activity_summary", "a.confidence_score", "a.decision"):
        assert field in source, field
    assert "s.strategy" in source and "s.timeframe" in source
    assert "asum.coins_scored" in source and "asum.highest_confidence" in source
    # (d) positions read demo-lane activity[] and coins[]; equity reads points/summary/disclaimer.
    assert "lane.coins" in source and "item.position.side!=='LONG'" in source
    for field in ("p.unrealised_pnl_pct", "p.entry_price_usd", "p.time_in_trade_seconds"):
        assert field in source, field
    assert "pr.disaster_stop_price_usd" in source and "pr.distance_to_stop_pct" in source
    assert "p.cumulative_net_quote" in source
    for field in ("summary.closed_count", "summary.wins", "summary.losses"):
        assert field in source, field
    assert "summary.realised_net_quote" in source and "summary.fees_quote" in source
    # Read-only render: no innerHTML of an unescaped server string anywhere in the Live renderers.
    assert "esc(headline)" in source and "esc(symbol)" in source
    assert "esc(String(e.detail" in source and "esc(String(e.agreement))" in source
    assert "esc(String(a.symbol" in source and "esc(String(s&&s.strategy))" in source
    # No raw server field is ever interpolated into markup without esc().
    assert not re.search(r"\$\{(?:e|a|p|pr|x|s|lane|feed|summary|payload)\.[A-Za-z_]+\}", source)


def test_live_lane_controls_reuse_overview_action_with_only_allowlisted_strings() -> None:
    html = _dashboard_html()
    section = _live_section()
    controls = html[
        html.index("function renderLiveLaneControls") : html.index("function updateLiveCountdown")
    ]
    # Exactly the three required buttons, mapped to the three allowlisted action strings.
    assert re.findall(r'data-live-lane="([^"]+)"', controls) == ["START_ACTIVITY", "START", "STOP"]
    assert ">Start Activity Lane<" in controls
    assert ">Start ETH Lane<" in controls
    assert ">Stop<" in controls
    # They reuse the existing helper and its existing POST path; no new action name or endpoint.
    assert "overviewLaneAction(b.dataset.liveLane,b)" in controls
    assert "async function overviewLaneAction(action,button)" in html
    assert html.count("'/api/v1/demo-lane-actions'") == 3  # demoLaneAction, overview, research
    for forbidden in ("RUN_ONCE", "START_MULTI", "START_RESEARCH"):
        assert f'data-live-lane="{forbidden}"' not in html, forbidden
    # confirm() gating is untouched and still covers START / START_ACTIVITY / STOP.
    gate = html[
        html.index("async function overviewLaneAction") : html.index("async function pollDemoLane")
    ]
    assert "!confirm(" in gate
    for action in ("STOP", "START", "START_ACTIVITY"):
        assert f"action==='{action}'" in gate, action
    # Running/stopped disable logic is preserved on the Live surface.
    assert "const running=status==='RUNNING'||status==='STOPPING'" in controls
    assert "startDis=running?'disabled':'',stopDis=running?'':'disabled'" in controls
    # Both surfaces are locked out during an in-flight action, and both status lines are updated.
    assert "'#demoLaneControls button,#liveLaneControls button'" in html
    assert "'#demoLaneControlStatus,#liveLaneControlStatus'" in html
    # No free-form input anywhere on the Live page.
    assert "<input" not in section
    assert "<textarea" not in section and "<select" not in section


def test_live_page_labels_the_score_agreement_and_never_confidence() -> None:
    section = _live_section()
    source = _live_render_source()
    # The user-facing label is "agreement", with the honest one-line explainer and entry gate.
    assert "agreement ${score.toFixed(4)}" in source
    assert "top agreement" in source
    assert "weighted agreement among correlated strategies" in section
    assert "NOT a probability of profit and NOT validated edge" in section
    assert "Entry gate 0.15 — the bar fills as agreement builds" in section
    # "confidence" is never a user-facing label; it survives only as the server payload key names.
    labels = source
    for server_key in ("confidence_score", "highest_confidence", "average_confidence"):
        labels = labels.replace(server_key, "")
    assert "confidence" not in labels.lower()
    assert "confidence" not in section.lower()
    # "probability of profit" appears only as an explicit denial, never as a claim.
    assert section.lower().count("probability of profit") == 1
    assert "NOT a probability of profit" in section
    for forbidden in ("win probability", "expected return", "predicted"):
        assert forbidden not in section.lower(), forbidden


def test_live_equity_panel_renders_the_disclaimer_verbatim_and_the_not_edge_label() -> None:
    section = _live_section()
    source = _live_render_source()
    assert '<span class="badge amber">execution measurement — not edge</span>' in section
    # The endpoint's own disclaimer string is rendered (escaped, so verbatim on screen).
    assert "esc(String((payload&&payload.disclaimer)||" in source
    assert "not validated edge" in source
    # Safety badges stay pinned on the Live status strip.
    for badge in ("FAKE MONEY", "AUTHORITY: NONE", "UNVALIDATED"):
        assert badge in section, badge
    assert "nothing on this page is validated edge" in section


def test_live_poll_reuses_the_guarded_visibility_aware_demo_lane_tick() -> None:
    html = _dashboard_html()
    poll = html[
        html.index("async function pollDemoLane(force)") : html.index("function updateDemoLaneLive")
    ]
    # One timer only: the Live view rides the existing ~5s demo-lane tick.
    assert "const DEMO_LANE_REFRESH_MS=5000" in html
    assert html.count("setInterval(()=>pollDemoLane(false),DEMO_LANE_REFRESH_MS)") == 1
    assert "if(demoLaneInFlight)return" in poll  # in-flight guard intact
    assert "document.hidden" in poll  # visibility pause intact
    assert "!['now','wallets-demo','live'].includes(activeView)" in poll  # only polls active views
    assert "await pollLiveFeed()" in poll
    assert "if(activeView==='live')await pollLiveFeed()" in poll
    # Scroll position and open <details> are preserved across the Live re-render too.
    assert "const y=window.scrollY" in poll
    assert "'#live details[open]'" in poll
    assert "window.scrollTo(0,y)" in poll
    # The schema_version === 1 gate is untouched for every Live fetch.
    assert "payload.schema_version!==1" in html
    assert html.count("fetchJson(url)") + html.count("fetchJson('/api/v1/") >= 3
    # The countdown ticks locally on the existing 1s interval, no extra timer.
    assert "setInterval(updateDemoLaneLive,1000)" in html
    assert "updateLiveCountdown()" in html
    assert "function updateLiveCountdown" in html


def test_live_panels_degrade_without_undefined_or_nan_on_empty_payloads() -> None:
    source = _live_render_source()
    esc_helper = (
        "const esc=s=>String(s??'').replace(/[&<>\"']/g,"
        "c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
    )
    script = (
        esc_helper
        + """
const nodes={};
const make=id=>(nodes[id]={id,innerHTML:'',textContent:'',dataset:{},
  setAttribute(){},querySelectorAll(){return []}});
for(const id of ['liveStatusBody','liveEventsBody','liveEventsCount','liveAgreementBody',
  'liveAgreementSummary','livePositionsBody','livePositionsSummary','liveEquityBody',
  'liveLaneControls','liveLaneControlStatus','liveNextScan'])make(id);
const document={
  hidden:false,
  querySelector(selector){return nodes[selector.replace('#','')]||null},
  querySelectorAll(){return []}
};
const overviewLaneAction=()=>{};
"""
        + source
        + """
const render=(feed,lane,equity)=>{
  renderLiveStatus(feed);renderLiveEvents(feed);
  renderLiveAgreement(lane);renderLivePositions(lane);renderLiveEquity(equity);
};
const dump=()=>Object.fromEntries(
  Object.entries(nodes).map(([id,node])=>[id,`${node.innerHTML}|${node.textContent}`]));
const out={};
renderLiveLaneControls('UNAVAILABLE');
// 1. hard-empty: available:false, nothing anywhere.
render({schema_version:1,available:false,lane:{},events:[],event_count:0,truncated:false},
  {schema_version:1},{schema_version:1,available:false,points:[],summary:{},disclaimer:''});
out.empty=dump();
// 2. one equity point only (must not divide by zero or draw a broken path).
render({schema_version:1,available:false,lane:{},events:[],event_count:0,truncated:false},
  {schema_version:1},
  {schema_version:1,available:true,points:[{at:'2026-07-24T00:00:00Z',trade_number:1,
    cumulative_net_quote:'12.5',net_quote:'12.5',symbol:'ETHUSDT'}],
   summary:{closed_count:1,wins:1,losses:0,flat:0,realised_net_quote:'12.5',
     fees_quote:'0.4',win_rate_pct:'100.0'},disclaimer:'Execution measurement only.'});
out.one=dump();
// 3. zero equity points but a running lane with junk/missing numeric fields.
render({schema_version:1,available:true,generated_at:'2026-07-24T00:00:00Z',
  lane:{status:'RUNNING',mode:'ACTIVITY',kill_switch:false,coins_scored:null,
    last_scan_utc:null,scan_age_seconds:null,next_scan_eta_seconds:null},
  events:[{at:'2026-07-24T00:00:00Z',age_seconds:null,kind:'SCAN',symbol:null,
    headline:'Scanned 10 coins',detail:'',agreement:null,pnl_pct:null,ok:true}],
  event_count:1,truncated:false},
  {schema_version:1,activity:[{symbol:'ETHUSDT',confidence_score:null,decision:'FLAT'}],
   activity_summary:{},coins:[]},
  {schema_version:1,available:true,points:[],summary:{},disclaimer:'d'});
out.junk=dump();
// 4. fully populated, both lane shapes.
render({schema_version:1,available:true,generated_at:'2026-07-24T00:00:00Z',
  lane:{status:'RUNNING',mode:'ACTIVITY',kill_switch:true,coins_scored:10,
    last_scan_utc:'2026-07-24T00:00:00Z',scan_age_seconds:12,next_scan_eta_seconds:78},
  events:[
    {at:'2026-07-24T00:00:00Z',age_seconds:12,kind:'ENTER',symbol:'ETHUSDT',
     headline:'Entered ETHUSDT',detail:'4 of 7 strategies agreed',agreement:'0.2143',
     pnl_pct:null,ok:true},
    {at:'2026-07-24T00:00:00Z',age_seconds:900,kind:'EXIT',symbol:'BTCUSDT',
     headline:'Exited BTCUSDT',detail:'agreement decayed',agreement:'0.0400',
     pnl_pct:'-1.25',ok:true},
    {at:'2026-07-24T00:00:00Z',age_seconds:7200,kind:'REJECT',symbol:'SOLUSDT',
     headline:'Rejected SOLUSDT',detail:'below the entry gate',agreement:'0.1100',
     pnl_pct:null,ok:false}],
  event_count:3,truncated:true},
  {schema_version:1,
   activity:[
     {symbol:'ETHUSDT',confidence_score:0.2143,decision:'LONG',
      bullish:[{strategy:'DONCHIAN',timeframe:'1h'},{strategy:'RSI',timeframe:'4h'}],
      bearish:[],
      position:{side:'LONG',base_qty:'0.5',entry_price_usd:'3000',mark_price_usd:'3060',
        unrealised_pnl_usd:'30',unrealised_pnl_pct:2,time_in_trade_seconds:5400},
      protection:{disaster_stop_price_usd:'2850',distance_to_stop_pct:6.8}},
     {symbol:'BTCUSDT',confidence_score:-0.31,decision:'FLAT',
      bullish:[],bearish:[{strategy:'MACD',timeframe:'15m'}]},
     {symbol:'ADAUSDT',confidence_score:null,decision:'FLAT'}],
   activity_summary:{coins_long:1,coins_scored:2,highest_confidence:0.31},
   coins:[{symbol:'ETHUSDT',position:{side:'LONG'}},
     {symbol:'LINKUSDT',position:{side:'LONG',entry_price_usd:'14',mark_price_usd:'13',
       unrealised_pnl_usd:'-1',unrealised_pnl_pct:-7.1,time_in_trade_seconds:120},
      protection:{disaster_stop_price_usd:'12.6',distance_to_stop_pct:3.1}}]},
  {schema_version:1,available:true,points:[
    {at:'a',trade_number:1,cumulative_net_quote:'5',net_quote:'5',symbol:'ETHUSDT'},
    {at:'b',trade_number:2,cumulative_net_quote:'5',net_quote:'0',symbol:'ETHUSDT'},
    {at:'c',trade_number:3,cumulative_net_quote:'18.25',net_quote:'13.25',symbol:'BTCUSDT'}],
   summary:{closed_count:3,wins:2,losses:1,flat:0,realised_net_quote:'18.25',
     fees_quote:'1.2',win_rate_pct:'66.67'},
   disclaimer:'Execution measurement only, not evidence of edge.'});
out.full=dump();
console.log(JSON.stringify(out));
"""
    )
    state = json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    # No panel ever shows undefined / NaN / null, in any of the four payload shapes.
    for case, nodes in state.items():
        for node_id, rendered in nodes.items():
            for forbidden in ("undefined", "NaN", "null"):
                assert forbidden not in rendered, f"{case}/{node_id}: {forbidden}"

    # available:false degrades to calm prose, not a blank panel and not a crash.
    assert "Confluence lane · stopped" in state["empty"]["liveStatusBody"]
    assert "NO FEED YET" in state["empty"]["liveStatusBody"]
    assert "Nothing yet." in state["empty"]["liveEventsBody"]
    assert state["empty"]["liveEventsCount"].endswith("|nothing yet")
    assert "No coin is reporting agreement yet" in state["empty"]["liveAgreementBody"]
    assert "Holding nothing right now" in state["empty"]["livePositionsBody"]
    assert "No closed trade yet" in state["empty"]["liveEquityBody"]
    assert "not validated edge" in state["empty"]["liveEquityBody"]

    # 0 points -> no <svg> at all; 1 point -> a single dot, never a polyline.
    assert "<svg" not in state["empty"]["liveEquityBody"]
    assert "<circle" in state["one"]["liveEquityBody"]
    assert "polyline" not in state["one"]["liveEquityBody"]
    assert "Execution measurement only." in state["one"]["liveEquityBody"]

    # A running lane with all-null numerics still reads cleanly.
    status = state["junk"]["liveStatusBody"]
    assert "Confluence lane · live" in status
    assert "scanning — coins · 7 strategies × 3 timeframes" in status
    assert "no scan yet" in status
    assert "1 quiet" in state["junk"]["liveAgreementBody"]

    # Populated: status strip, colour-coded kinds, agreement bars, positions, sparkline.
    full = state["full"]
    assert "Confluence lane · live" in full["liveStatusBody"]
    assert "MODE ACTIVITY" in full["liveStatusBody"]
    assert "scanning 10 coins" in full["liveStatusBody"]
    assert "last scan 12s ago" in full["liveStatusBody"]
    assert "KILL SWITCH ON" in full["liveStatusBody"]
    assert "next scan in 1:18" in full["liveNextScan"]
    events = full["liveEventsBody"]
    assert '<span class="badge green">ENTER</span>' in events
    assert '<span class="badge cyan">EXIT</span>' in events
    assert '<span class="badge red">REJECT</span>' in events
    assert "12s ago" in events and "15m ago" in events and "2h ago" in events
    assert "agreement 0.2143" in events
    assert '<span class="badge red">-1.25%</span>' in events
    assert "truncated" in full["liveEventsCount"]
    agreement = full["liveAgreementBody"]
    # Strongest agreement first (|-0.31| > |0.2143|), bar width maps the score, chips are mono.
    assert agreement.index("BTCUSDT") < agreement.index("ETHUSDT")
    assert 'style="width:31.00%"' in agreement
    assert 'style="width:21.43%"' in agreement
    assert '<span class="live-chip mono">DONCHIAN@1h</span>' in agreement
    assert '<span class="live-chip mono">MACD@15m</span>' in agreement
    assert "1 quiet" in agreement
    assert "top agreement 0.3100" in full["liveAgreementSummary"]
    positions = full["livePositionsBody"]
    # activity[] and coins[] merge, deduped by symbol; ETHUSDT appears once.
    assert positions.count(">ETHUSDT<") == 1
    assert ">LINKUSDT<" in positions
    assert '<span class="live-up">+2.00%</span>' in positions
    assert '<span class="live-down">-7.10%</span>' in positions
    assert "in trade 1h 30m" in positions and "in trade 2m" in positions
    assert "stop $2,850 · 6.80% from mark" in positions
    assert full["livePositionsSummary"].endswith("|2 open")
    equity = full["liveEquityBody"]
    # Oldest -> newest polyline, first x=0 and last x=100, y clamped inside the 32-unit box.
    assert "<polyline" in equity
    points = re.search(r'points="([^"]+)"', equity)
    assert points is not None
    coords = [tuple(float(v) for v in pair.split(",")) for pair in points.group(1).split(" ")]
    assert [x for x, _ in coords] == [0.0, 50.0, 100.0]
    assert coords[0][1] == 28.0 and coords[-1][1] == 4.0
    assert all(0.0 <= y <= 32.0 for _, y in coords)
    assert "3 closed · 2W / 1L" in equity
    assert "win rate 66.67%" in equity
    assert "realised $18.25 · fees $1.2" in equity
    assert "Execution measurement only, not evidence of edge." in equity
    # The lane controls render the three allowlisted buttons in the stopped/disabled state.
    controls = state["empty"]["liveLaneControls"]
    assert re.findall(r'data-live-lane="([^"]+)"', controls) == ["START_ACTIVITY", "START", "STOP"]
    assert 'data-live-lane="STOP" disabled' in controls
    assert "Lane stopped/idle" in state["empty"]["liveLaneControlStatus"]


def _header_health_source() -> str:
    html = _dashboard_html()
    start = html.index("// --- Header status strip:")
    return html[start : html.index("function freshnessLabel(", start)]


def _run_node(script: str) -> dict[str, object]:
    return json.loads(
        subprocess.run(
            ["node", "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )


def _health_harness(source: str, body: str) -> str:
    """Drive the header-status helpers against a fake topbar with a switchable workspace."""
    return f"""
const dot={{className:''}},text={{textContent:''}};
let active='live';
const document={{querySelector(selector){{
  if(selector==='#healthDot')return dot;
  if(selector==='#healthText')return text;
  if(selector==='[data-workspace].active')return {{dataset:{{workspace:active}}}};
  return null;
}}}};
const window={{}};
const asArray=value=>Array.isArray(value)?value:[];
const esc=s=>String(s??'');
const timeText=value=>String(value??'');
const humanStatus=value=>String(value??'');
{source}
const snap=()=>({{dot:dot.className,text:text.textContent}});
const out={{}};
{body}
console.log(JSON.stringify(out));
"""


def test_watch_header_reports_the_lane_instead_of_the_blanket_source_alarm() -> None:
    poll = _dashboard_html()[
        _dashboard_html().index("async function pollDemoLane(force)") : _dashboard_html().index(
            "function updateDemoLaneLive"
        )
    ]
    # Both poll outcomes feed the Watch header: a good payload and a failed fetch.
    assert "setLaneHealthFrom(lane)" in poll
    assert "setLaneHealthUnavailable()" in poll

    state = _run_node(
        _health_harness(
            _header_health_source(),
            """
// The cockpit's own roll-up keeps firing in the background on every page.
const cockpitAlarm=()=>setHealthIndicator('unavailable','Some sources unavailable');
cockpitAlarm();
setLaneHealthFrom({operational_status:'RUNNING',
  activity:[{heartbeat_fresh:true}],coins:[{heartbeat_fresh:false}]});
out.watchRunning=snap();
cockpitAlarm();
setLaneHealthFrom({operational_status:'RUNNING',
  activity:[{heartbeat_fresh:false}],coins:[{heartbeat_fresh:false}]});
out.watchStale=snap();
setLaneHealthFrom({operational_status:'IDLE',activity:[],coins:[]});
out.watchIdle=snap();
setLaneHealthFrom({operational_status:'STOPPED',activity:[],coins:[]});
out.watchStopped=snap();
setLaneHealthFrom({operational_status:'UNAVAILABLE'});
out.watchUnavailable=snap();
setLaneHealthFrom(undefined);
out.watchMalformed=snap();
setLaneHealthFrom({operational_status:'RUNNING',activity:[{heartbeat_fresh:true}]});
setLaneHealthUnavailable();
out.watchFetchFailed=snap();
// Lab pages keep the untouched cockpit roll-up, including its alarming wording.
setLaneHealthFrom({operational_status:'RUNNING',activity:[{heartbeat_fresh:true}]});
active='now';applyHealthIndicator();
out.labAlarm=snap();
setHealthIndicator('degraded','Sources delayed');
out.labDelayed=snap();
setHealthIndicator('live','Sources live');
out.labLive=snap();
active='wallets';applyHealthIndicator();
out.walletRunning=snap();
""",
        )
    )

    # A Watch page never shows the blanket source alarm — it shows the lane it depends on.
    assert state["watchRunning"] == {"dot": "dot live", "text": "Lane running · fake money"}
    assert state["walletRunning"] == {"dot": "dot live", "text": "Lane running · fake money"}
    # ...and never claims healthy when the lane's own artifacts are stale, missing or unreadable.
    assert state["watchStale"] == {"dot": "dot degraded", "text": "Lane running · heartbeats stale"}
    assert state["watchUnavailable"] == {"dot": "dot unavailable", "text": "Lane state unavailable"}
    assert state["watchMalformed"] == {"dot": "dot unavailable", "text": "Lane state unavailable"}
    assert state["watchFetchFailed"] == {"dot": "dot unavailable", "text": "Lane state unavailable"}
    # Stopped/idle is honest and calm: neither green nor an error.
    assert state["watchIdle"] == {"dot": "dot", "text": "Lane idle · nothing trading"}
    assert state["watchStopped"] == {"dot": "dot", "text": "Lane stopped · nothing trading"}
    for watch_case in ("watchRunning", "watchStale", "watchIdle", "watchStopped", "walletRunning"):
        assert "sources" not in str(state[watch_case]).lower(), watch_case
    # Lab keeps every pre-existing cockpit label and tone, unchanged.
    assert state["labAlarm"] == {"dot": "dot unavailable", "text": "Some sources unavailable"}
    assert state["labDelayed"] == {"dot": "dot degraded", "text": "Sources delayed"}
    assert state["labLive"] == {"dot": "dot live", "text": "Sources live"}


def test_every_source_health_entry_carries_a_plain_language_explainer() -> None:
    html = _dashboard_html()
    source = html[
        html.index("// Plain-language explainer per") : html.index("function renderAttention")
    ]
    state = _run_node(
        f"""
const list={{innerHTML:''}};
const document={{querySelector:()=>list}};
const asArray=value=>Array.isArray(value)?value:[];
const escapes={{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>escapes[c]);
const timeText=value=>String(value??'');
const humanStatus=value=>String(value??'Unknown').replaceAll('_',' ');
{source}
const out={{}};
renderFreshness([
  {{source:'PAPER_RUNTIME',status:'UNAVAILABLE',observed_at:null,
    detail:'No strategy is approved for paper simulation.'}},
  {{source:'BINANCE_PUBLIC_DATA:eth-bot',status:'LIVE',observed_at:'2026-07-26T00:00:00Z',
    detail:'Public prices only; no account, credential, or order connection.'}},
  {{source:'RESEARCH_JOBS',status:'LIVE',observed_at:null,detail:'Local jobs store: AVAILABLE.'}},
  {{source:'RESEARCH_DATA',status:'DELAYED',observed_at:'2026-07-26T00:00:00Z',
    detail:'Governed local dataset refresh status.'}},
  {{source:'COINDESK_DATA_NEWS',status:'UNAVAILABLE',observed_at:null,
    detail:'Optional external news is not configured.'}},
  {{source:'SOMETHING_NEW',status:'STALE',observed_at:null,detail:'A source added later.'}}
]);
out.rendered=list.innerHTML;
renderFreshness([{{source:'RESEARCH_JOBS',status:'LIVE',observed_at:null,detail:'d'}}],true);
out.degraded=list.innerHTML;
renderFreshness([]);
out.empty=list.innerHTML;
console.log(JSON.stringify(out));
"""
    )
    rendered = str(state["rendered"])
    # One chip per entry, each with the ⓘ affordance and an explainer alongside the raw detail.
    assert rendered.count('class="source-chip') == 6
    assert rendered.count('class="source-why" aria-hidden="true"') == 6
    assert rendered.count("ⓘ") == 6
    for raw_detail in (
        "No strategy is approved for paper simulation.",
        "Public prices only; no account, credential, or order connection.",
        "Local jobs store: AVAILABLE.",
        "Governed local dataset refresh status.",
        "Optional external news is not configured.",
        "A source added later.",
    ):
        assert raw_detail in rendered, raw_detail
    for explainer in (
        "the legacy event-sourced paper simulator",
        "public Binance price heartbeats",
        "the local offline research-jobs database can be read",
        "how old the last governed dataset refresh is",
        "optional external news metadata",
        # An unknown future source still gets an honest fallback rather than silence.
        "a development or optional data source",
    ):
        assert explainer in rendered, explainer
    # Once in the hover tooltip and once in the screen-reader text, for each of the six entries.
    assert rendered.count("What it is:") == 12
    # Pre-existing behaviour intact: raw detail stays its own screen-reader span, and the
    # last-good downgrade (Live -> Delayed) and the empty fallback are unchanged.
    assert (
        '<span class="visually-hidden">PAPER_RUNTIME · No strategy is approved for '
        "paper simulation.</span>" in rendered
    )
    assert "<strong>Delayed</strong>" in str(state["degraded"])
    assert "No source freshness was returned." in str(state["empty"])


def test_lab_overview_keeps_the_full_raw_source_health_detail() -> None:
    html = _dashboard_html()
    now_section = html[html.index('<section id="now"') : html.index('id="nowHeadline"')]
    # The Overview block, its chip list and every raw field it projects are untouched.
    assert ">Environment and source health<" in now_section
    assert 'id="freshnessList" aria-label="Source freshness"' in now_section
    assert (
        "const detail=[row?.source,timeText(row?.observed_at),row?.detail].filter(Boolean)" in html
    )
    assert "esc(humanStatus(row?.source||'Unknown source'))" in html
    assert "({LIVE:'Live',DELAYED:'Delayed',STALE:'Stale',UNAVAILABLE:'Unavailable'})" in html
    assert '<span class="visually-hidden">${esc(detail)}</span>' in html
    # Plus the one-line caption that says what "Unavailable" means here.
    assert "not running" in now_section and "not configured" in now_section
    assert "The Watch pages (Live, Wallet) depend on none of these" in now_section


def _automation_section() -> str:
    html = _dashboard_html()
    start = html.index('<section id="automation-map"')
    return html[start : html.index("</section>", html.index("Deliberately not automated"))]


def test_automation_page_is_reachable_under_lab_and_lists_real_capabilities() -> None:
    html = _dashboard_html()
    section = _automation_section()
    assert '<button data-workspace="automation-map">Automation</button>' in html
    assert "'automation-map':[['automation-map','Automation']]" in html
    # Three groups, exactly as the operator asked for them.
    for heading in (
        ">Deterministic · zero AI<",
        ">Judgement · AI-assisted<",
        ">Human-gated execution<",
    ):
        assert heading in section, heading
    # Every capability cites the command or endpoint that actually runs it.
    for citation in (
        "GET /api/v1/live-feed",
        "GET /api/v1/demo-lane",
        "GET /api/v1/equity-curve",
        "GET /api/v1/cockpit?range=…",
        "GET /api/v1/demo-trades → scripts/report_demo_trades.py",
        "GET /api/v1/demo-status → scripts/report_demo_status.py",
        "GET /api/v1/research-findings → scripts/report_research_findings.py",
        "START_RESEARCH → python scripts/run_universe_search.py",
        "GET /api/v1/eth-signal",
        "make eth-signal → scripts/verify_eth_volume_breakout_flow.py --summary",
        "POST /api/v1/signals/poll",
        "POST /api/v1/workspace-actions/data-update",
        "POST /api/v1/workspace-actions/decision",
        "POST /api/v1/cockpit-actions",
        "make orchestrator → scripts/run_orchestrator.py --loop",
        "make orchestrator-once",
        "touch artifacts/orchestrator/KILL_SWITCH",
        "python scripts/demo_eth_lane.py --loop",
        "python scripts/demo_eth_lane.py --activity --loop --interval 5m",
        "python scripts/demo_eth_lane.py --multi",
        "python scripts/demo_eth_lane.py --once",
        "make demo-lane · make demo-lane-once",
        "src/tios/approval/intake_admission.py",
        "scripts/build_validation_package.py",
        "/trading-os-supervisor",
    ):
        assert citation in section, citation
    # Capabilities with no control surface say so instead of inventing a button.
    assert section.count("no control yet — runs from the terminal:") == 4
    assert "no control yet — library path only:" in section
    for mode in (
        "already-live read-only projection",
        ">on-click<",
        "self-looping",
        "human-armed only",
    ):
        assert mode in section, mode


def test_automation_page_cites_only_commands_and_endpoints_that_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    section = _automation_section()
    real_routes = {
        "/api/v1/dashboard",
        "/api/v1/status",
        "/api/v1/operations",
        "/api/v1/stage-gates",
        "/api/v1/search",
        "/api/v1/market",
        "/api/v1/cockpit",
        "/api/v1/signals",
        "/api/v1/signals/reliability",
        "/api/v1/signals/ingest",
        "/api/v1/signals/poll",
        "/api/v1/skills",
        "/api/v1/demo-lane",
        "/api/v1/demo-trades",
        "/api/v1/demo-status",
        "/api/v1/live-feed",
        "/api/v1/equity-curve",
        "/api/v1/research-findings",
        "/api/v1/ai-costs",
        "/api/v1/open-work",
        "/api/v1/orchestrator",
        "/api/v1/eth-signal",
        "/api/v1/workspace-actions/data-update",
        "/api/v1/workspace-actions/decision",
        "/api/v1/cockpit-actions",
        "/api/v1/demo-lane-actions",
    }
    cited_routes = set(re.findall(r"/api/v1/[a-z0-9/-]+", section))
    assert cited_routes <= real_routes, cited_routes - real_routes
    # No fictional script or Makefile target: the page can only cite what is really there.
    makefile = (root / "Makefile").read_text()
    targets = set(re.findall(r"^([a-zA-Z0-9_.-]+):", makefile, re.MULTILINE))
    cited_targets = set(re.findall(r"\bmake ([a-z][a-z-]*)", section))
    assert cited_targets <= targets, cited_targets - targets
    for script in set(re.findall(r"(?:scripts|src)/[A-Za-z0-9_/]+\.py", section)):
        assert (root / script).is_file(), script


def test_automation_page_adds_no_control_surface_and_no_new_action_name() -> None:
    section = _automation_section()
    # Documentation only: nothing clickable, nothing typable, no write path of its own.
    for forbidden in ("<input", "<form", "<select", "<textarea", "<button", "onclick", "fetch("):
        assert forbidden not in section, forbidden
    for wiring in (
        "data-live-lane",
        "data-overview-lane",
        "data-cockpit-action",
        "data-demo-report",
    ):
        assert wiring not in section, wiring
    assert "method:'POST'" not in section
    assert "innerHTML" not in section  # the page is static markup; nothing is server-derived
    # No POST path beyond the four that already exist, and no invented action name.
    assert set(re.findall(r"POST (/api/v1/[a-z/-]+)", section)) == {
        "/api/v1/signals/poll",
        "/api/v1/workspace-actions/data-update",
        "/api/v1/workspace-actions/decision",
        "/api/v1/cockpit-actions",
    }
    allowlisted = {"START", "START_ACTIVITY", "START_MULTI", "START_RESEARCH", "STOP", "RUN_ONCE"}
    assert set(re.findall(r'<td class="mono">([A-Z_]+)</td>', section)) == allowlisted - {
        "START_RESEARCH"
    }
    assert set(re.findall(r"\b[A-Z]{3,}(?:_[A-Z]+)+\b", section)) <= allowlisted | {
        "STOP_ARMED",  # a live-feed event kind, not an action
        "KILL_SWITCH",  # the stop flag's filename
        "DECISION_LOG",  # DECISION_LOG.md
    }


def test_automation_page_pins_human_armed_execution_and_authority_none() -> None:
    section = _automation_section()
    assert "Order-placing lanes are human-armed only." in section
    assert "The app never auto-starts trading by itself." in section
    assert "Execution authority is <strong>NONE</strong>" in section
    assert "AUTHORITY: NONE" in section
    assert (
        "There is no scheduler, cron, timer or background job anywhere in this system that can "
        "start an order-placing lane" in section
    )
    # Every order-placing row is marked human-armed; the stop path is always available.
    execution = section[section.index(">Human-gated execution<") :]
    for action in ("START", "START_ACTIVITY", "START_MULTI", "RUN_ONCE"):
        row = execution[execution.index(f'<td class="mono">{action}</td>') :]
        assert "human-armed only" in row[: row.index("</tr>")], action
    stop_row = execution[execution.index('<td class="mono">STOP</td>') :]
    assert "always available" in stop_row[: stop_row.index("</tr>")]
    assert "touch artifacts/trading_domain/demo_lane/KILL_SWITCH" in section
    assert "artifacts/human_decisions/demo_lane_actions.jsonl" in section
    # The page states the absence of automation explicitly rather than implying it.
    assert "No automatic trading start" in section
    assert "No auto-promotion, no auto-tuning" in section


def test_automation_page_holds_the_honest_labelling_doctrine() -> None:
    section = _automation_section()
    assert "confidence" not in section.lower()
    assert "Agreement is how much of the roster points the same way" in section
    assert "Execution measurement — not edge" in section
    assert "0 strategies are validated today" in section
    assert "Demo P&amp;L is non-evidence" in section
    assert "UNVALIDATED" in section
    assert section.lower().count("probability of profit") == 1
    assert "not a probability of profit" in section
    for forbidden in (
        "expected return",
        "profitable",
        "money printer",
        "win probability",
        "predicted",
        "guaranteed",
    ):
        assert forbidden not in section.lower(), forbidden
    assert "0 validated strategies" in section


def test_every_navigable_workspace_view_resolves_to_a_section() -> None:
    html = _dashboard_html()
    workspaces = html[html.index("const WORKSPACES=") : html.index("let activeWorkspace=")]
    view_ids = re.findall(r"\['([a-z-]+)','[^']+'\]", workspaces)
    # All twelve pre-existing pages plus the Automation map remain reachable and rendered.
    assert len(view_ids) >= 26
    for view_id in view_ids:
        assert f'id="{view_id}"' in html, view_id
    for workspace in re.findall(r'<button[^>]+data-workspace="([^"]+)"', html):
        assert f"{workspace}:[[" in workspaces or f"'{workspace}':[[" in workspaces, workspace


# --- Wallet page: the money view over /api/v1/wallet (D-120/D-121 honest-labelling doctrine) ---


def _wallet_section() -> str:
    html = _dashboard_html()
    start = html.index('<section id="wallets-demo"')
    return html[start : html.index('<section id="wallets-real"', start)]


def _wallet_render_source() -> str:
    html = _dashboard_html()
    start = html.index("// --- Wallet money view over /api/v1/wallet")
    return html[start : html.index("// --- read-only report panel", start)]


def test_watch_pages_carry_distinguishing_subtitles() -> None:
    """Live vs Wallet explains itself from the heading down, without opening either page."""
    live = _live_section()
    wallet = _wallet_section()
    assert "What the system is doing right now: scanning, agreement, entries and exits." in live
    assert (
        "The money: what the venue holds, what the lane is allowed to use, "
        "what it holds now, and what it has earned." in wallet
    )
    # Each subtitle sits directly under its own heading, inside its own view section.
    assert live.index('id="liveHeading"') < live.index("What the system is doing right now")
    assert wallet.index('id="walletsDemoHeading"') < wallet.index("The money: what the venue holds")
    # Neither view id moved, and the Demo/Real tabs still resolve.
    assert 'id="wallets-demo"' in wallet
    assert "wallets:[['wallets-demo','Demo'],['wallets-real','Real']]" in _dashboard_html()
    assert '<section id="wallets-real"' in _dashboard_html()


def test_wallet_page_has_the_four_money_panels_in_order_reading_the_wallet_endpoint() -> None:
    section = _wallet_section()
    source = _wallet_render_source()
    ordered = [
        'id="walletBudgetPanel"',
        'id="walletPositionsPanel"',
        'id="walletResultPanel"',
        'id="walletEquityBody"',
        'id="walletVenuePanel"',
        "<summary>Per-coin lane detail</summary>",
    ]
    positions = [section.index(marker) for marker in ordered]
    assert positions == sorted(positions), ordered
    for heading in (
        ">What the lane is working with<",
        ">Open positions<",
        ">Result so far<",
        ">Venue wallet<",
    ):
        assert heading in section, heading
    # Every documented /api/v1/wallet field the panels claim to show is actually read.
    assert "fetchJson('/api/v1/wallet')" in source
    for field in (
        "w.available",
        "w.as_of",
        "w.environment",
        "w.real_money",
        "w.execution_authority",
        "w.venue",
        "w.budget",
        "w.positions",
        "w.realised",
        "w.unrealised_total_usdt",
        "w.disclaimer",
        "budget.total_cap_usdt",
        "budget.per_trade_usdt",
        "budget.deployed_usdt",
        "budget.free_usdt",
        "budget.slots_total",
        "budget.slots_used",
        "budget.slots_free",
        "budget.disaster_stop_pct",
        "p.symbol",
        "p.strategy",
        "p.size_base",
        "p.entry_price",
        "p.mark_price",
        "p.value_usdt",
        "p.spent_usdt",
        "p.unrealised_usdt",
        "p.unrealised_pct",
        "p.held_seconds",
        "p.stop_price",
        "p.distance_to_stop_pct",
        "realised.closed_count",
        "realised.wins",
        "realised.losses",
        "realised.realised_usdt",
        "realised.fees_usdt",
        "venue.balances",
        "venue.quote_usdt",
        "venue.quote_usdc",
        "venue.note",
        "b.coin",
        "b.amount",
        "b.is_quote",
    ):
        assert field in source, field


def test_wallet_reuses_the_live_equity_renderer_instead_of_a_second_implementation() -> None:
    html = _dashboard_html()
    source = _wallet_render_source()
    # Exactly one curve renderer and one loader, both parameterised by target node.
    assert html.count("function renderLiveEquity(") == 1
    assert html.count("async function loadEquityInto(") == 1
    assert "function renderLiveEquity(payload,target)" in html
    assert "document.querySelector(target||'#liveEquityBody')" in html
    # Live and Wallet both go through it; neither draws its own polyline.
    assert "await loadEquityInto('#liveEquityBody')" in html
    assert "await loadEquityInto('#walletEquityBody')" in source
    assert html.count("<polyline") == 1
    assert source.count("polyline") == 0
    assert source.count("cumulative_net_quote") == 0
    # And it stays labelled the honest way on the wallet page too.
    assert '<span class="badge amber">execution measurement — not edge</span>' in _wallet_section()


def test_wallet_page_is_read_only_with_no_input_and_no_new_action_name() -> None:
    section = _wallet_section()
    source = _wallet_render_source()
    assert "<input" not in section
    assert "<form" not in section
    assert "<textarea" not in section
    assert "<select" not in section
    # No write path and no scheduler of its own: GET /api/v1/wallet plus the shared equity GET.
    for banned in ("method:'POST'", "method: 'POST'", "setInterval", "setTimeout", "randomUUID"):
        assert banned not in source, banned
    assert re.findall(r"fetchJson\('([^']+)'\)", source) == ["/api/v1/wallet"]
    # It adds no control surface: no lane action attribute anywhere in the new panels.
    panels = section[: section.index("<summary>Per-coin lane detail</summary>")]
    for attribute in ("data-lane-action", "data-live-lane", "data-overview-lane", "<button"):
        assert attribute not in panels, attribute


def test_wallet_page_holds_the_honest_labelling_doctrine() -> None:
    section = _wallet_section()
    source = _wallet_render_source()
    lane_source = _demo_lane_render_source()
    # Badges pinned; the demo lane's fake money and NONE authority stated on the page itself.
    for badge in ("FAKE MONEY", "AUTHORITY: NONE", "UNVALIDATED"):
        assert badge in section, badge
    assert "0 strategies are validated" in section
    assert "demo P&amp;L is NON-EVIDENCE" in section
    # "confidence" is never a user-facing score label on this page: the per-coin detail now says
    # "agreement", and "confidence" survives only inside server payload key names.
    labels = lane_source
    for server_key in ("confidence_score", "highest_confidence", "average_confidence"):
        labels = labels.replace(server_key, "")
    assert "confidence" not in labels.lower()
    assert "confidence" not in section.lower()
    assert "agreement <strong" in lane_source
    assert "top agreement" in lane_source
    assert "NOT a probability of profit" in lane_source
    # No profit-expectation / money-printer vocabulary anywhere on the page or in its renderer.
    for forbidden in (
        "profit",
        "returns",
        "growth",
        "money printer",
        "gains",
        "expected return",
        "predicted",
        "roi",
    ):
        assert forbidden not in section.lower(), forbidden
        assert forbidden not in source.lower(), forbidden
    # No fabricated price chart: the page says so rather than drawing one.
    assert "no price history in this view" in section.lower()


def test_wallet_page_keeps_the_legacy_per_coin_detail_reachable() -> None:
    section = _wallet_section()
    html = _dashboard_html()
    # The pre-existing per-coin card and the mockup provider grid are demoted, not deleted.
    detail = section[section.index('<details class="wallet-legacy"') :]
    assert "<summary>Per-coin lane detail</summary>" in detail
    assert 'id="demoLaneCard"' in detail
    assert 'id="walletDemoBody"' in detail
    assert "Sample provider balances" in detail
    # Still driven by the same renderers, and still below every money panel.
    assert section.index('id="walletVenuePanel"') < section.index('<details class="wallet-legacy"')
    assert "renderDemoLane(lane)" in html
    assert "renderWalletTab('demo')" in html


def test_wallet_poll_reuses_the_guarded_visibility_aware_demo_lane_tick() -> None:
    html = _dashboard_html()
    poll = html[
        html.index("async function pollDemoLane(force)") : html.index("function updateDemoLaneLive")
    ]
    # No competing timer: the wallet view rides the single existing ~5s tick.
    assert html.count("setInterval(()=>pollDemoLane(false),DEMO_LANE_REFRESH_MS)") == 1
    assert "if(demoLaneInFlight)return" in poll  # in-flight guard intact
    assert "document.hidden" in poll  # visibility pause intact
    assert "!['now','wallets-demo','live'].includes(activeView)" in poll  # wallet view allowlisted
    assert "if(activeView==='wallets-demo')await loadWallet()" in poll
    # Every wallet fetch still goes through the schema_version === 1 gate.
    assert "payload.schema_version!==1" in html
    assert "async function loadWallet()" in html
    assert "fetchJson('/api/v1/wallet')" in html


@functools.cache
def _wallet_state() -> dict[str, dict[str, str]]:
    """Drive the real wallet renderer under node over four payload shapes."""
    esc_helper = (
        "const esc=s=>String(s??'').replace(/[&<>\"']/g,"
        "c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));"
    )
    script = (
        esc_helper
        + """
const window={};
const nodes={};
const make=id=>(nodes[id]={id,innerHTML:'',textContent:'',dataset:{},
  setAttribute(){},querySelectorAll(){return []}});
for(const id of ['liveStatusBody','liveEventsBody','liveEventsCount','liveAgreementBody',
  'liveAgreementSummary','livePositionsBody','livePositionsSummary','liveEquityBody',
  'liveLaneControls','liveLaneControlStatus','liveNextScan','walletBudgetBody',
  'walletBudgetSummary','walletPositionsBody','walletPositionsSummary','walletResultBody',
  'walletVenueBody','walletEquityBody'])make(id);
const document={
  hidden:false,
  querySelector(selector){return nodes[selector.replace('#','')]||null},
  querySelectorAll(){return []}
};
const overviewLaneAction=()=>{};
"""
        + _live_render_source()
        + _wallet_render_source()
        + """
const render=(wallet,equity)=>{
  renderWalletMoney(wallet);renderLiveEquity(equity,'#walletEquityBody')};
const dump=()=>Object.fromEntries(Object.entries(nodes)
  .filter(([id])=>id.startsWith('wallet'))
  .map(([id,node])=>[id,`${node.innerHTML}|${node.textContent}`]));
const out={};
// 1. available:false — the same key set, empty. Nothing may render as undefined/NaN/null.
render({schema_version:1,available:false,as_of:null,environment:'VENUE_DEMO',real_money:false,
  execution_authority:'NONE',
  venue:{balances:[],quote_usdt:'0',quote_usdc:'0',note:''},
  budget:{total_cap_usdt:'0',per_trade_usdt:'0',deployed_usdt:'0',free_usdt:'0',
    slots_total:0,slots_used:0,slots_free:0,disaster_stop_pct:'0'},
  positions:[],realised:{closed_count:0,wins:0,losses:0,realised_usdt:'0',fees_usdt:'0'},
  unrealised_total_usdt:null,disclaimer:''},
  {schema_version:1,available:false,points:[],summary:{},disclaimer:''});
out.empty=dump();
// 2. a cap with nothing deployed and no position: the allocation bar is a bare track.
render({schema_version:1,available:true,as_of:'2026-07-26T10:00:00+00:00',
  environment:'VENUE_DEMO',real_money:false,execution_authority:'NONE',
  venue:{balances:[{coin:'USDC',amount:'50000',is_quote:true}],quote_usdt:'49673.21',
    quote_usdc:'50000',note:'Pre-funded seed capital.'},
  budget:{total_cap_usdt:'300',per_trade_usdt:'25',deployed_usdt:'0',free_usdt:'300',
    slots_total:12,slots_used:0,slots_free:12,disaster_stop_pct:'15'},
  positions:[],realised:{closed_count:0,wins:0,losses:0,realised_usdt:'0',fees_usdt:'0'},
  unrealised_total_usdt:'0',disclaimer:'Execution measurement only.'},
  {schema_version:1,available:true,points:[{at:'a',trade_number:1,cumulative_net_quote:'0.5379',
    net_quote:'0.5379',symbol:'ETHUSDT'}],
   summary:{closed_count:1,wins:1,losses:0,flat:0,realised_net_quote:'0.5379',fees_quote:'0.05',
     win_rate_pct:'100.0'},disclaimer:'Execution measurement only.'});
out.one=dump();
// 3. no cap reported at all — no chart, no division by zero, no pips.
render({schema_version:1,available:true,as_of:null,environment:'VENUE_DEMO',real_money:false,
  execution_authority:'NONE',
  venue:{balances:[],quote_usdt:null,quote_usdc:null,note:''},
  budget:{total_cap_usdt:null,per_trade_usdt:null,deployed_usdt:null,free_usdt:null,
    slots_total:0,slots_used:0,slots_free:null,disaster_stop_pct:null},
  positions:[],realised:{closed_count:null,wins:null,losses:null,realised_usdt:null,
    fees_usdt:null},unrealised_total_usdt:null,disclaimer:''},
  {schema_version:1,available:true,points:[],summary:{},disclaimer:''});
out.nocap=dump();
// 4. the real shape: $300 cap, $25 per position, 12/12 slots used, $0 free, one null-mark row.
render({schema_version:1,available:true,as_of:'2026-07-26T14:55:00+00:00',
  environment:'VENUE_DEMO',real_money:false,execution_authority:'NONE',
  venue:{balances:[{coin:'BTC',amount:'1.00021',is_quote:false},
    {coin:'ETH',amount:'0.9987',is_quote:false},
    {coin:'USDC',amount:'50000',is_quote:true},
    {coin:'USDT',amount:'49673.4412',is_quote:true}],
   quote_usdt:'49673.4412',quote_usdc:'50000',
   note:'Pre-funded fake money: the venue demo account was seeded before any '
     +'trading. Not performance, not the operator money.'},
  budget:{total_cap_usdt:'300',per_trade_usdt:'25',deployed_usdt:'300',free_usdt:'0',
    slots_total:12,slots_used:12,slots_free:0,disaster_stop_pct:'15'},
  positions:[
    {symbol:'BTCUSDT',strategy:'ACTIVITY-CONFLUENCE',opened_at:'2026-07-26T14:53:02+00:00',
     held_seconds:5400,size_base:'0.00021',entry_price:'118000',mark_price:'119180',
     spent_usdt:'25',value_usdt:'25.25',unrealised_usdt:'0.25',unrealised_pct:'1.0',
     stop_price:'100300',distance_to_stop_pct:'15.84'},
    {symbol:'AXSUSDT',strategy:'ACTIVITY-CONFLUENCE',opened_at:'2026-07-26T14:54:32+00:00',
     held_seconds:120,size_base:'6.1',entry_price:'4.1',mark_price:null,
     spent_usdt:'25',value_usdt:null,unrealised_usdt:null,unrealised_pct:null,
     stop_price:null,distance_to_stop_pct:null}],
  realised:{closed_count:1,wins:1,losses:0,realised_usdt:'0.5379',fees_usdt:'0.0512'},
  unrealised_total_usdt:'-1.14',
  disclaimer:'Demo execution measurement only — not evidence of edge.'},
  {schema_version:1,available:true,points:[
    {at:'a',trade_number:1,cumulative_net_quote:'0.5379',net_quote:'0.5379',symbol:'ETHUSDT'},
    {at:'b',trade_number:2,cumulative_net_quote:'0.5379',net_quote:'0',symbol:'ETHUSDT'}],
   summary:{closed_count:1,wins:1,losses:0,flat:0,realised_net_quote:'0.5379',fees_quote:'0.0512',
     win_rate_pct:'100.0'},
   disclaimer:'Demo execution measurement only — not evidence of edge.'});
out.full=dump();
console.log(JSON.stringify(out));
"""
    )
    return _run_node(script)  # type: ignore[return-value]


def test_wallet_panels_never_render_undefined_nan_or_null() -> None:
    state = _wallet_state()
    for case, panels in state.items():
        for panel_id, rendered in panels.items():
            for forbidden in ("undefined", "NaN", "null"):
                assert forbidden not in rendered, f"{case}/{panel_id}: {forbidden}"
    # available:false degrades to calm prose in every panel, not a blank card and not a crash.
    empty = state["empty"]
    assert "No lane budget yet" in empty["walletBudgetBody"]
    assert "No open positions." in empty["walletPositionsBody"]
    assert empty["walletPositionsSummary"].endswith("|none open")
    assert empty["walletBudgetSummary"].endswith("|no lane budget yet")
    assert "No venue balances reported." in empty["walletVenueBody"]
    assert "No closed trade yet" in empty["walletEquityBody"]
    # Missing numbers become em dashes, never zeros invented on the operator's behalf.
    nocap = state["nocap"]
    assert nocap["walletBudgetBody"].count("—") >= 5
    assert "Closed trades" in nocap["walletResultBody"] and "—" in nocap["walletResultBody"]


def test_wallet_budget_headline_is_the_lane_cap_and_explains_a_full_slot_book() -> None:
    state = _wallet_state()
    full = state["full"]
    budget = full["walletBudgetBody"]
    # The headline figures are the lane's own money, read from budget.* — not the venue total.
    assert "Lane cap" in budget and "$300" in budget
    assert "Deployed" in budget
    assert "Free to spend" in budget and "$0" in budget
    assert "Per position" in budget and "$25" in budget
    assert "15.00%" in budget  # disaster stop
    assert full["walletBudgetSummary"].endswith("|12 / 12 slots used")
    # The venue's ~$99.7k never appears as a headline anywhere.
    assert "99" not in budget and "50000" not in budget and "49673" not in budget
    assert "wallet-figure" not in full["walletVenueBody"]
    assert "wallet-headline" not in full["walletVenueBody"]
    # slots_free === 0 gets the plain-language answer to "why is nothing happening".
    assert "Every slot is in use." in budget
    assert "No new position can open until one exits" in budget
    assert "Every slot is in use." not in state["one"]["walletBudgetBody"]


def test_wallet_charts_survive_zero_and_one_data_point() -> None:
    state = _wallet_state()
    # Allocation bar: track only with nothing deployed, one extra block per reporting position.
    assert state["one"]["walletBudgetBody"].count("<rect") == 1
    assert state["full"]["walletBudgetBody"].count("<rect") == 3  # track + two positions
    assert '<svg class="wallet-alloc"' in state["one"]["walletBudgetBody"]
    # No cap -> no chart at all rather than a divide-by-zero or a broken path.
    assert '<svg class="wallet-alloc"' not in state["nocap"]["walletBudgetBody"]
    assert "nothing to chart" in state["nocap"]["walletBudgetBody"]
    assert "wallet-pips" not in state["nocap"]["walletBudgetBody"]
    # Slot pips: exactly slots_total pips, exactly slots_used filled.
    assert state["one"]["walletBudgetBody"].count('class="wallet-pip"') == 12
    assert state["one"]["walletBudgetBody"].count('class="wallet-pip on"') == 0
    assert state["full"]["walletBudgetBody"].count('class="wallet-pip on"') == 12
    # Equity sparkline (the shared renderer) into the wallet target: 0 points, 1 point, 2 points.
    assert "<svg" not in state["empty"]["walletEquityBody"]
    assert "No closed trade yet" in state["empty"]["walletEquityBody"]
    assert "<circle" in state["one"]["walletEquityBody"]
    assert "polyline" not in state["one"]["walletEquityBody"]
    assert "<polyline" in state["full"]["walletEquityBody"]


def test_wallet_positions_table_renders_every_column_and_dashes_null_marks() -> None:
    state = _wallet_state()
    body = state["full"]["walletPositionsBody"]
    headers = re.findall(r"<th>([^<]+)</th>", body)
    assert headers == [
        "Coin",
        "Strategy",
        "Size",
        "Entry",
        "Mark",
        "Value",
        "Unrealised",
        "Unrealised %",
        "Held",
        "Stop",
        "To stop",
    ]
    assert state["full"]["walletPositionsSummary"].endswith("|2 open")
    # API order is preserved, not re-sorted client-side.
    assert body.index("BTCUSDT") < body.index("AXSUSDT")
    rows = re.findall(r"<tr><td class=\"mono\">(.*?)</tr>", body)
    assert len(rows) == 2
    # A fully-marked row: money, signed P&L with a colour class, humanised hold, stop distance.
    assert "ACTIVITY-CONFLUENCE" in rows[0]
    assert "$118,000" in rows[0] and "$119,180" in rows[0] and "$25.25" in rows[0]
    assert '<td class="mono live-up">+$0.25</td>' in rows[0]
    assert '<td class="mono live-up">+1.00%</td>' in rows[0]
    assert "1h 30m" in rows[0]
    assert "$100,300" in rows[0] and "15.84%" in rows[0]
    # The null-mark row renders em dashes in every unknown cell, never NaN/undefined/null.
    assert rows[1].count("—") == 6  # mark, value, unrealised $, unrealised %, stop, to stop
    assert '<td class="mono muted">—</td>' in rows[1]
    assert "2m" in rows[1]


def test_wallet_result_and_venue_panels_frame_the_prefunded_balance_honestly() -> None:
    state = _wallet_state()
    full = state["full"]
    result = full["walletResultBody"]
    # Result so far: realised, unrealised, closed count, W/L and fees, signed and colour-coded.
    assert "Realised" in result and "+$0.54" in result
    assert 'class="value live-down">-$1.14' in result
    assert "Closed trades" in result and ">1<" in result
    assert "1W / 0L" in result
    assert "Fees paid" in result and "$0.05" in result
    assert "Demo execution measurement only — not evidence of edge." in result
    # Venue wallet: the API's own note leads the panel, then the full balance list, then quotes.
    venue = full["walletVenueBody"]
    assert venue.index("Read this first:") < venue.index("<table")
    assert "Pre-funded fake money" in venue
    assert "seeded before any trading" in venue
    assert "Not performance, not the operator money." in venue
    for coin in ("BTC", "ETH", "USDC", "USDT"):
        assert f'<td class="mono">{coin}</td>' in venue, coin
    assert venue.count("<td>quote</td>") == 2
    assert venue.count("<td>coin</td>") == 2
    assert "49673.4412" in venue
    assert "The lane only ever touches the $300 cap" in venue
