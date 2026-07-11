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
    build_dashboard_data,
    build_stage_gate_readiness,
    build_status,
    record_workspace_decision,
)
from tios.services.dashboard_ui.server import Handler, is_loopback_host


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    ai_run = next(action for action in status["workspace_actions"] if action["id"] == "T-011-05")
    assert {option["id"] for option in ai_run["options"]} == {
        "keep_deferred",
        "credentials_configured",
    }
    assert any(item["file"] == "14_dashboard.md" for item in status["initiatives"])
    assert status["checks"]["status"] in {"PASS", "UNKNOWN"}
    assert status["checks"]["known_passing"] is (status["checks"]["status"] == "PASS")
    assert status["checks"]["includes_dependency_audit"] is False


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
    }
    assert trading["counts"]["retained_run_artifacts"] == len(data["runs"])
    assert trading["counts"]["retained_backtest_fills"] > 0
    assert trading["counts"]["order_intents"] == 0
    assert trading["counts"]["order_states"] == 0
    assert trading["counts"]["accounts"] == 0
    assert trading["counts"]["portfolios"] == 0
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
    readiness = trading["stage_gate_readiness"]
    assert readiness["status"] == "BLOCKED_BY_GATES"
    assert readiness["execution_authority"] == "NONE"
    assert readiness["s3_paper_demo"]["status"] == "NOT_READY"
    assert readiness["s4_live"]["status"] == "NOT_READY"
    assert "S2_EXIT_PASS" in readiness["s3_paper_demo"]["blocked_by"]
    assert "one COMPLETE_APPROVABLE strategy context" in readiness["s3_paper_demo"]["blocked_by"]
    assert "HG_5_OPERATOR_APPROVAL" in readiness["s4_live"]["blocked_by"]
    assert "synthetic_wallet_mutation" in trading["prohibited"]
    assert "venue_order_routing" in trading["prohibited"]
    assert "live_order_capability" in trading["prohibited"]


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
        row["gate"] == "G10" and row["status"] == "FAIL" for row in comparisons["validation_gates"]
    )
    assert any(
        row["family"] == "B2" and row["verdict"] == "FAIL" for row in comparisons["g10_rows"]
    )
    assert comparisons["cross_engine"]["verdict"] == "PASS_WITH_SCOPE_NOTE"
    assert comparisons["cross_engine"]["economic_direction_agreement"] is True
    assert comparisons["seed_g10"]["status"] == "FAIL"
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
    assert sources["source_count"] == 14
    assert sources["hypothesis_only_count"] == 14
    assert sources["noneligible_count"] == 14
    assert sources["intake_plans"] == {
        "plan_count": 4,
        "ready_count": 3,
        "design_only_count": 1,
    }
    assert sources["replay_hypotheses"] == {
        "hypothesis_count": 4,
        "spec_candidate_count": 2,
        "replay_candidate_count": 1,
        "non_reconstructable_count": 1,
        "noneligible_count": 4,
    }
    assert sources["checked_date"] == "2026-07-11"
    assert len(sources["digest"]) == 64
    assert sources["family_counts"]["multiple_testing_controls"] == 4
    assert sources["family_counts"]["exchange_bot_replay"] == 1
    assert sources["family_counts"]["copy_trading_replay"] == 1
    assert sources["family_counts"]["signal_replay"] == 1
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
    assert 'data-view="market"' in html
    assert "external-embedding/embed-widget-advanced-chart.js" in html
    assert "NO ORDERS" in html
    assert "tradingview-widget-copyright" in html
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
        "Demo wallet boundary",
        "S3 paper/demo readiness",
        "S4 live readiness",
        "blocked gate chain",
        "human-only future stage",
        "Demo wallet readiness",
        "Demo wallet invariants",
        "DESIGN_ONLY_NOT_ACTIVATED",
        "synthetic capital not authorized",
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
    assert "No venue connectivity, paper/live execution, credentials, or order execution" in html


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
        "STALE_MS=15000",
        "MARKET_POLL_MS=15000",
        "setInterval(()=>{if(document.querySelector('#market').classList.contains('active'))loadMarket()}",
        "marketLoading=true",
        "last successful refresh",
        "returned malformed JSON",
        'id="retry"',
    ):
        assert contract in html
    assert "Array.from({length:24}" not in html
    assert "HG-2" not in html
    assert "S1" not in html


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
                "schema_version": 2,
                "gate": "check",
                "command": "make check",
                "status": "PASS",
                "includes_dependency_audit": False,
                "generated_at": (datetime.now(tz=UTC) - age).isoformat(),
            }
        )
    )
    checks = build_status(tmp_path)["checks"]
    assert checks["status"] == "PASS"
    assert checks["known_passing"] is True
    assert checks["includes_dependency_audit"] is False
    assert checks["required_gate"] == {"command": "make required", "status": "UNKNOWN"}


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
            "generated_at": (datetime.now(tz=UTC) + timedelta(minutes=1)).isoformat(),
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
    body = b'{"task_id":"T-011-05","choice":"keep_deferred"}'
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

    blocked = _handle_request(
        b"POST /api/v1/orders HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}",
        tmp_path,
    )
    assert b" 404 " in blocked.split(b"\r\n\r\n", 1)[0]
