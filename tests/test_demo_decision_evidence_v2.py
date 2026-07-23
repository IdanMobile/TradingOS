from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from tios.evidence import demo_decision_evidence_v2 as stage_b

NOW = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
STAMP = "2026-07-23T12:00:00.000000Z"
EPOCH = "act_" + "a" * 64
ROLLBACK_COMMIT = "c" * 40
STRATEGY = "strategy_" + "1" * 64
COST = "cost_" + "2" * 64
RISK = "risk_" + "3" * 64
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_STAGE_B_ROOT = PROJECT_ROOT / stage_b.PRIVATE_ROOT_REL

EXPECTED_BOUND_FILES = (
    "src/tios/evidence/demo_decision_evidence_v2.py",
    "tests/test_demo_decision_evidence_v2.py",
    "scripts/demo_eth_lane.py",
    "scripts/demo_roundtrip.py",
    "tests/test_demo_eth_lane.py",
    "tests/test_demo_roundtrip.py",
    "src/tios/services/dashboard_api/demo_lane.py",
    "tests/test_demo_lane_api.py",
    "src/tios/services/dashboard_ui/dashboard.html",
    "tests/test_dashboard.py",
    "PROJECT_STATE.md",
    "DECISION_LOG.md",
    "docs/architecture/AD.md",
    "PACKAGE_CHANGELOG.md",
    "PACKAGE_INTEGRITY_MANIFEST.md",
)
EXPECTED_PAYLOAD_FIELDS: dict[str, tuple[str, ...]] = {
    "ACTIVATION_BOUND": (
        "activation_receipt_sha256",
        "config_sha256",
        "independent_review_sha256",
        "flat_reconciliation_sha256",
        "rollback_config_sha256",
        "controlled_restart_id",
        "repo_commit",
    ),
    "DECISION_OBSERVED": (
        "strategy_alias",
        "cost_alias",
        "risk_alias",
        "symbol",
        "timeframe",
        "decision",
        "side",
        "requested_qty",
        "quantity_unit",
    ),
    "RISK_VERDICT_OBSERVED": (
        "decision_event_id",
        "verdict",
        "reason_code",
        "approved_qty",
        "quantity_unit",
        "quote_cap",
    ),
    "IDEMPOTENCY_KEY_RESERVED": (
        "decision_event_id",
        "risk_event_id",
        "order_alias",
        "client_key",
        "client_key_sha256",
    ),
    "SUBMISSION_INTENT_COMMITTED": (
        "key_event_id",
        "order_alias",
        "order_kind",
        "side",
        "order_type",
        "qty",
        "quantity_unit",
        "trigger_price",
        "risk_increasing",
    ),
    "SUBMISSION_ATTEMPTED": (
        "intent_event_id",
        "order_alias",
        "client_key_sha256",
        "endpoint",
        "attempt_ordinal",
    ),
    "VENUE_ACKNOWLEDGED": (
        "attempt_event_id",
        "order_alias",
        "venue_code",
        "result_code",
    ),
    "VENUE_REJECTED": (
        "attempt_event_id",
        "order_alias",
        "venue_code",
        "result_code",
    ),
    "SUBMISSION_RESULT_UNKNOWN": (
        "attempt_event_id",
        "order_alias",
        "venue_code",
        "result_code",
    ),
    "ORDER_UPDATE_OBSERVED": (
        "order_alias",
        "order_status",
        "cum_exec_qty",
        "cum_exec_value",
        "leaves_qty",
        "avg_price",
        "source",
    ),
    "FILL_OBSERVED": (
        "order_alias",
        "execution_alias",
        "fee_alias",
        "side",
        "exec_qty",
        "exec_price",
        "exec_value",
        "fee_amount",
        "fee_currency",
        "source",
    ),
    "CANCEL_OBSERVED": (
        "order_alias",
        "client_key_sha256",
        "cancel_state",
        "venue_code",
        "source",
    ),
    "EXIT_UPDATE_OBSERVED": (
        "episode_open_event_id",
        "order_alias",
        "exit_state",
        "executed_base_qty",
        "received_quote_value",
    ),
    "TERMINAL_RECONCILIATION_COMMITTED": (
        "order_alias",
        "terminal_status",
        "buy_exec_qty",
        "sell_exec_qty",
        "entry_exec_value",
        "exit_exec_value",
        "quote_fee",
        "base_fee",
        "third_fee_present",
        "position_base_qty",
        "protective_stop_state",
        "flat",
        "source",
        "all_pages_complete",
    ),
    "CLOSED_EPISODE_COMMITTED": (
        "series_sha256",
        "episode_ordinal",
        "entry_base_qty",
        "exit_base_qty",
        "entry_exec_value",
        "exit_exec_value",
        "gross_quote",
        "quote_fee",
        "base_fee",
        "third_fee_present",
        "net_quote",
        "terminal_reconciliation_event_id",
        "eligibility",
        "ineligibility_code",
    ),
    "CORRECTION_COMMITTED": (
        "target_event_id",
        "target_event_sha256",
        "correction_code",
        "replacement_event_id",
    ),
    "EVIDENCE_OUTAGE_RECORDED": (
        "incident_sha256",
        "outage_code",
        "first_affected_event_id",
        "risk_reduction_occurred",
    ),
    "RECOVERY_COMMITTED": (
        "incident_sha256",
        "recovery_record_sha256",
        "approval_sha256",
        "reconciliation_event_id",
        "prior_head_sha256",
    ),
}
EXPECTED_ENUMS: dict[str, frozenset[str]] = {
    "decision": frozenset({"ENTRY", "EXIT", "STOP", "CANCEL", "NO_ACTION"}),
    "side": frozenset({"BUY", "SELL", "NONE"}),
    "quantity_unit": frozenset({"BASE", "QUOTE", "NONE"}),
    "verdict": frozenset({"ALLOW_RISK_INCREASE", "BLOCK", "RISK_REDUCING"}),
    "reason_code": frozenset({"POLICY_PASS", "POLICY_BLOCK", "EXIT_ONLY", "KILL_SWITCH"}),
    "order_kind": frozenset(
        {"ENTRY", "EXIT", "STOP_CREATE", "STOP_REPLACE", "STOP_CLEANUP", "CANCEL"}
    ),
    "order_type": frozenset({"MARKET", "STOP_MARKET"}),
    "endpoint": frozenset({"CREATE", "CANCEL"}),
    "result_code": frozenset(
        {
            "ACCEPTED_PENDING",
            "POLICY_REJECTED",
            "VENUE_REJECTED",
            "TIMEOUT",
            "DISCONNECT",
            "MALFORMED",
            "UNKNOWN",
        }
    ),
    "order_status": frozenset(
        {
            "NEW",
            "PARTIALLY_FILLED",
            "FILLED",
            "CANCELLED",
            "REJECTED",
            "PARTIALLY_FILLED_CANCELED",
            "UNTRIGGERED",
            "TRIGGERED",
            "DEACTIVATED",
            "UNKNOWN",
        }
    ),
    "source": frozenset({"REALTIME", "HISTORY", "EXECUTION", "RECONCILIATION"}),
    "cancel_state": frozenset({"ACK_PENDING", "CONFIRMED", "REJECTED", "UNKNOWN"}),
    "exit_state": frozenset({"STARTED", "PARTIAL", "TERMINAL", "UNKNOWN"}),
    "terminal_status": frozenset({"FILLED", "CANCELLED", "REJECTED", "PARTIALLY_FILLED_CANCELED"}),
    "protective_stop_state": frozenset({"CLEAR", "ACTIVE", "FILLED", "CANCELLED", "UNKNOWN"}),
    "fee_currency": frozenset({"USDT", "ETH", "THIRD"}),
    "eligibility": frozenset({"ELIGIBLE", "PERMANENTLY_INELIGIBLE"}),
    "ineligibility_code": frozenset(
        {
            "NONE",
            "LEGACY",
            "OUTAGE",
            "CORRECTION",
            "THIRD_CURRENCY_FEE",
            "CHAIN_GAP",
            "UNRESOLVED",
            "STOP_NOT_CLEAR",
        }
    ),
    "correction_code": frozenset(
        {"SOURCE_CORRECTION", "DUPLICATE_CONFLICT", "RECONCILIATION_CORRECTION"}
    ),
    "outage_code": frozenset(
        {"WRITE", "FSYNC", "PERMISSION", "CAPACITY", "HASH", "SEQUENCE", "SCHEMA", "UNKNOWN_RESULT"}
    ),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write_private(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(raw)
    path.chmod(0o600)


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    _write_private(path, stage_b.canonical_json_bytes(dict(value)))


def _copy_bound_files(repo_root: Path) -> dict[str, object]:
    result: dict[str, object] = {}
    for relative in stage_b._BOUND_FILES:
        source = PROJECT_ROOT / relative
        target = repo_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        target.write_bytes(raw)
        result[relative] = _sha(raw)
    return result


def _git(repo_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), *arguments],
        check=True,
        shell=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _activation_root(tmp_path: Path, *, approved_at: datetime = NOW) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, mode=0o700)
    file_sha256 = _copy_bound_files(repo_root)
    _git(repo_root, "init", "--quiet")
    _git(repo_root, "add", "--", *stage_b._BOUND_FILES)
    _git(
        repo_root,
        "-c",
        "user.name=Stage B Fixture",
        "-c",
        "user.email=stage-b-fixture@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "stage-b activation fixture",
    )
    repo_commit = _git(repo_root, "rev-parse", "--verify", "HEAD")
    private = repo_root / stage_b.PRIVATE_ROOT_REL
    private.mkdir(parents=True, mode=0o700)
    private.chmod(0o700)
    for relative in (
        "activation",
        "private",
        "store",
        "store/generations",
        "quarantine",
        "recovery",
    ):
        directory = private / relative
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)

    module_sha256 = _sha((repo_root / stage_b._BOUND_FILES[0]).read_bytes())
    config = stage_b.expected_config(module_sha256)
    config_raw = stage_b.canonical_json_bytes(config)
    _write_private(private / "activation/CONFIG.json", config_raw)
    config_sha256 = _sha(config_raw)

    review: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.independent_review.v1",
        "decision": "GO",
        "reviewed_commit": repo_commit,
        "file_sha256": file_sha256,
        "config_sha256": config_sha256,
        "reviewed_at": STAMP,
    }
    review_raw = stage_b.canonical_json_bytes(review)
    _write_private(private / "activation/INDEPENDENT_REVIEW.json", review_raw)

    flat: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.flat_reconciliation.v1",
        "repo_commit": repo_commit,
        "config_sha256": config_sha256,
        "prior_stage_b_head_sha256": None,
        "observed_at": STAMP,
        "position_base_qty": "0",
        "open_order_count": 0,
        "unresolved_attempt_count": 0,
        "protective_stop_state": "CLEAR",
        "all_pages_complete": True,
        "source": "REALTIME_HISTORY_EXECUTION",
    }
    flat_raw = stage_b.canonical_json_bytes(flat)
    _write_private(private / "activation/FLAT_RECONCILIATION.json", flat_raw)

    rollback: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.rollback_config.v1",
        "rollback_commit": ROLLBACK_COMMIT,
        "prior_file_sha256": {
            "scripts/demo_eth_lane.py": "4" * 64,
            "scripts/demo_roundtrip.py": "5" * 64,
            "src/tios/services/dashboard_api/demo_lane.py": "6" * 64,
            "src/tios/services/dashboard_ui/dashboard.html": "7" * 64,
        },
        "prior_config": {
            "schema": "tios.demo_decision_evidence.rollback_prior_config.v1",
            "stage_b": "ABSENT",
            "execution_authority": "NONE",
        },
        "make_start_target": "demo-lane",
        "make_once_target": "demo-lane-once",
        "recorded_at": STAMP,
    }
    rollback_raw = stage_b.canonical_json_bytes(rollback)
    _write_private(private / "activation/ROLLBACK_CONFIG.json", rollback_raw)

    alias_key = bytes(range(32))
    _write_private(private / "private/install_alias.key", alias_key)
    receipt: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.activation_receipt.v1",
        "state": "ACTIVE",
        "environment": "VENUE_DEMO",
        "real_money": False,
        "execution_authority": "NONE",
        "package_version": "v8.146",
        "repo_commit": repo_commit,
        "file_sha256": file_sha256,
        "config_path": ("artifacts/evidence/private_demo/stage_b_v2/activation/CONFIG.json"),
        "config_sha256": config_sha256,
        "independent_review_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/INDEPENDENT_REVIEW.json"
        ),
        "independent_review_sha256": _sha(review_raw),
        "flat_reconciliation_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/FLAT_RECONCILIATION.json"
        ),
        "flat_reconciliation_sha256": _sha(flat_raw),
        "rollback_config_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/ROLLBACK_CONFIG.json"
        ),
        "rollback_config_sha256": _sha(rollback_raw),
        "private_root": "artifacts/evidence/private_demo/stage_b_v2",
        "receipt_path": (
            "artifacts/evidence/private_demo/stage_b_v2/activation/ACTIVATION_RECEIPT.json"
        ),
        "alias_key_path": ("artifacts/evidence/private_demo/stage_b_v2/private/install_alias.key"),
        "alias_key_sha256": _sha(alias_key),
        "rollback_commit": ROLLBACK_COMMIT,
        "controlled_restart_id": "restart_stage_b_test",
        "activation_epoch": EPOCH,
        "approved_at": stage_b.canonical_utc(approved_at),
    }
    _write_json(private / "activation/ACTIVATION_RECEIPT.json", receipt)
    lane_lock = repo_root / "artifacts/trading_domain/demo_lane/lane.lock"
    lane_lock.parent.mkdir(parents=True, exist_ok=True)
    lane_lock.write_text("", encoding="utf-8")
    lane_lock.chmod(0o600)
    return repo_root


def _activation_event(repo_root: Path) -> stage_b.EvidenceEvent:
    activation = stage_b.load_activation(repo_root, now=NOW)
    return stage_b.next_event(
        None,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.ACTIVATION_BOUND,
        recorded_at=STAMP,
        payload={
            "activation_receipt_sha256": activation.receipt_sha256,
            "config_sha256": activation.config_sha256,
            "independent_review_sha256": activation.independent_review_sha256,
            "flat_reconciliation_sha256": activation.flat_reconciliation_sha256,
            "rollback_config_sha256": activation.rollback_config_sha256,
            "controlled_restart_id": "restart_stage_b_test",
            "repo_commit": activation.receipt["repo_commit"],
        },
    )


@contextmanager
def _lane_capability(repo_root: Path) -> Iterator[stage_b.LaneLockCapability]:
    with stage_b.exclusive_lane_lock_capability(repo_root) as capability:
        yield capability


def _append(
    sink: stage_b.StageBEvidenceSink,
    events: list[stage_b.EvidenceEvent] | tuple[stage_b.EvidenceEvent, ...],
    *,
    now: datetime = NOW,
) -> stage_b.EvidenceSnapshot:
    with _lane_capability(sink.private_root.parents[3]) as capability:
        return sink.append(events, capability=capability, now=now)


def _public_cohort(
    projection: Mapping[str, object], series_number: int, cohort_number: int
) -> dict[str, object]:
    series = projection["series"]
    assert isinstance(series, list)
    selected_series = series[series_number]
    assert isinstance(selected_series, dict)
    cohorts = selected_series["cohorts"]
    assert isinstance(cohorts, list)
    cohort = cohorts[cohort_number]
    assert isinstance(cohort, dict)
    return cohort


def _append_event(
    events: list[stage_b.EvidenceEvent],
    event_type: stage_b.EventType,
    payload: Mapping[str, object],
) -> stage_b.EvidenceEvent:
    event = stage_b.next_event(
        events[-1] if events else None,
        activation_epoch=EPOCH,
        event_type=event_type,
        recorded_at=STAMP,
        payload=payload,
    )
    events.append(event)
    return event


def _episode(
    events: list[stage_b.EvidenceEvent],
    *,
    number: int,
    result_unknown: bool = False,
    extra_entry_fills: int = 0,
) -> dict[str, stage_b.EvidenceEvent]:
    order = f"ord_{number * 2:064x}"
    exit_order = f"ord_{number * 2 + 1:064x}"
    execution_buy = f"exe_{number * 2:064x}"
    execution_sell = f"exe_{number * 2 + 1:064x}"
    key = f"tios2_{number:030x}"
    decision = _append_event(
        events,
        stage_b.EventType.DECISION_OBSERVED,
        {
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "ENTRY",
            "side": "BUY",
            "requested_qty": "1",
            "quantity_unit": "BASE",
        },
    )
    risk = _append_event(
        events,
        stage_b.EventType.RISK_VERDICT_OBSERVED,
        {
            "decision_event_id": decision.event_id,
            "verdict": "ALLOW_RISK_INCREASE",
            "reason_code": "POLICY_PASS",
            "approved_qty": "1",
            "quantity_unit": "BASE",
            "quote_cap": "10",
        },
    )
    reserved = _append_event(
        events,
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        {
            "decision_event_id": decision.event_id,
            "risk_event_id": risk.event_id,
            "order_alias": order,
            "client_key": key,
            "client_key_sha256": _sha(key.encode("ascii")),
        },
    )
    intent = _append_event(
        events,
        stage_b.EventType.SUBMISSION_INTENT_COMMITTED,
        {
            "key_event_id": reserved.event_id,
            "order_alias": order,
            "order_kind": "ENTRY",
            "side": "BUY",
            "order_type": "MARKET",
            "qty": "1",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "risk_increasing": True,
        },
    )
    attempted = _append_event(
        events,
        stage_b.EventType.SUBMISSION_ATTEMPTED,
        {
            "intent_event_id": intent.event_id,
            "order_alias": order,
            "client_key_sha256": _sha(key.encode("ascii")),
            "endpoint": "CREATE",
            "attempt_ordinal": 1,
        },
    )
    initial = _append_event(
        events,
        (
            stage_b.EventType.SUBMISSION_RESULT_UNKNOWN
            if result_unknown
            else stage_b.EventType.VENUE_ACKNOWLEDGED
        ),
        {
            "attempt_event_id": attempted.event_id,
            "order_alias": order,
            "venue_code": 0,
            "result_code": "TIMEOUT" if result_unknown else "ACCEPTED_PENDING",
        },
    )
    buy = _append_event(
        events,
        stage_b.EventType.FILL_OBSERVED,
        {
            "order_alias": order,
            "execution_alias": execution_buy,
            "fee_alias": f"fee_{number * 2:064x}",
            "side": "BUY",
            "exec_qty": "1",
            "exec_price": "10",
            "exec_value": "10",
            "fee_amount": "0.1",
            "fee_currency": "USDT",
            "source": "EXECUTION",
        },
    )
    for extra_index in range(extra_entry_fills):
        _append_event(
            events,
            stage_b.EventType.FILL_OBSERVED,
            {
                "order_alias": order,
                "execution_alias": f"exe_{1_000_000 + number * 10_000 + extra_index:064x}",
                "fee_alias": f"fee_{1_000_000 + number * 10_000 + extra_index:064x}",
                "side": "BUY",
                "exec_qty": "0",
                "exec_price": "10",
                "exec_value": "0",
                "fee_amount": "0",
                "fee_currency": "USDT",
                "source": "EXECUTION",
            },
        )
    entry_terminal = _append_event(
        events,
        stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        {
            "order_alias": order,
            "terminal_status": "FILLED",
            "buy_exec_qty": "1",
            "sell_exec_qty": "0",
            "entry_exec_value": "10",
            "exit_exec_value": "0",
            "quote_fee": "0.1",
            "base_fee": "0",
            "third_fee_present": False,
            "position_base_qty": "1",
            "protective_stop_state": "ACTIVE",
            "flat": False,
            "source": "RECONCILIATION",
            "all_pages_complete": True,
        },
    )
    exit_decision = _append_event(
        events,
        stage_b.EventType.DECISION_OBSERVED,
        {
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "EXIT",
            "side": "SELL",
            "requested_qty": "1",
            "quantity_unit": "BASE",
        },
    )
    exit_risk = _append_event(
        events,
        stage_b.EventType.RISK_VERDICT_OBSERVED,
        {
            "decision_event_id": exit_decision.event_id,
            "verdict": "RISK_REDUCING",
            "reason_code": "EXIT_ONLY",
            "approved_qty": "1",
            "quantity_unit": "BASE",
            "quote_cap": "0",
        },
    )
    exit_key = f"tios2_exit_{number:025x}"
    exit_reserved = _append_event(
        events,
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        {
            "decision_event_id": exit_decision.event_id,
            "risk_event_id": exit_risk.event_id,
            "order_alias": exit_order,
            "client_key": exit_key,
            "client_key_sha256": _sha(exit_key.encode("ascii")),
        },
    )
    exit_intent = _append_event(
        events,
        stage_b.EventType.SUBMISSION_INTENT_COMMITTED,
        {
            "key_event_id": exit_reserved.event_id,
            "order_alias": exit_order,
            "order_kind": "EXIT",
            "side": "SELL",
            "order_type": "MARKET",
            "qty": "1",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "risk_increasing": False,
        },
    )
    exit_attempted = _append_event(
        events,
        stage_b.EventType.SUBMISSION_ATTEMPTED,
        {
            "intent_event_id": exit_intent.event_id,
            "order_alias": exit_order,
            "client_key_sha256": _sha(exit_key.encode("ascii")),
            "endpoint": "CREATE",
            "attempt_ordinal": 1,
        },
    )
    exit_initial = _append_event(
        events,
        stage_b.EventType.VENUE_ACKNOWLEDGED,
        {
            "attempt_event_id": exit_attempted.event_id,
            "order_alias": exit_order,
            "venue_code": 0,
            "result_code": "ACCEPTED_PENDING",
        },
    )
    exit_update = _append_event(
        events,
        stage_b.EventType.EXIT_UPDATE_OBSERVED,
        {
            "episode_open_event_id": buy.event_id,
            "order_alias": exit_order,
            "exit_state": "STARTED",
            "executed_base_qty": "0",
            "received_quote_value": "0",
        },
    )
    sell = _append_event(
        events,
        stage_b.EventType.FILL_OBSERVED,
        {
            "order_alias": exit_order,
            "execution_alias": execution_sell,
            "fee_alias": f"fee_{number * 2 + 1:064x}",
            "side": "SELL",
            "exec_qty": "1",
            "exec_price": "11",
            "exec_value": "11",
            "fee_amount": "0.1",
            "fee_currency": "USDT",
            "source": "EXECUTION",
        },
    )
    exit_terminal = _append_event(
        events,
        stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        {
            "order_alias": exit_order,
            "terminal_status": "FILLED",
            "buy_exec_qty": "1",
            "sell_exec_qty": "1",
            "entry_exec_value": "10",
            "exit_exec_value": "11",
            "quote_fee": "0.2",
            "base_fee": "0",
            "third_fee_present": False,
            "position_base_qty": "0",
            "protective_stop_state": "CLEAR",
            "flat": True,
            "source": "RECONCILIATION",
            "all_pages_complete": True,
        },
    )
    terminal = exit_terminal
    if result_unknown:
        terminal = _append_event(
            events,
            stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
            {
                **exit_terminal.payload,
                "order_alias": order,
            },
        )
    series_sha = stage_b._series_identity(EPOCH, STRATEGY, COST, RISK)
    closed = _append_event(
        events,
        stage_b.EventType.CLOSED_EPISODE_COMMITTED,
        {
            "series_sha256": series_sha,
            "episode_ordinal": number,
            "entry_base_qty": "1",
            "exit_base_qty": "1",
            "entry_exec_value": "10",
            "exit_exec_value": "11",
            "gross_quote": "1",
            "quote_fee": "0.2",
            "base_fee": "0",
            "third_fee_present": False,
            "net_quote": "0.8",
            "terminal_reconciliation_event_id": terminal.event_id,
            "eligibility": "PERMANENTLY_INELIGIBLE" if result_unknown else "ELIGIBLE",
            "ineligibility_code": "UNRESOLVED" if result_unknown else None,
        },
    )
    return {
        "decision": decision,
        "risk": risk,
        "reserved": reserved,
        "intent": intent,
        "attempted": attempted,
        "initial": initial,
        "buy": buy,
        "entry_terminal": entry_terminal,
        "exit_decision": exit_decision,
        "exit_risk": exit_risk,
        "exit_reserved": exit_reserved,
        "exit_intent": exit_intent,
        "exit_attempted": exit_attempted,
        "exit_initial": exit_initial,
        "exit_update": exit_update,
        "sell": sell,
        "exit_terminal": exit_terminal,
        "terminal": terminal,
        "closed": closed,
    }


def _one_episode_chain(
    repo_root: Path, *, result_unknown: bool = False
) -> list[stage_b.EvidenceEvent]:
    events = [_activation_event(repo_root)]
    _episode(events, number=1, result_unknown=result_unknown)
    return events


@pytest.fixture(autouse=True)
def _repository_runtime_stays_absent() -> Iterator[None]:
    assert not REPOSITORY_STAGE_B_ROOT.exists()
    yield
    assert not REPOSITORY_STAGE_B_ROOT.exists()


def test_absent_activation_is_default_disabled_and_authority_none(tmp_path: Path) -> None:
    check = stage_b.activation_check(tmp_path)
    assert check.state is stage_b.ActivationState.NOT_ACTIVATED
    assert check.execution_authority == "NONE"
    assert stage_b.public_stage_b_projection(tmp_path) == {
        "status": "NOT_ACTIVATED",
        "cohort_size": 30,
        "series": [],
    }
    with pytest.raises(stage_b.StageBNotActivatedError):
        stage_b.StageBEvidenceSink(tmp_path).load()
    assert not (tmp_path / stage_b.PRIVATE_ROOT_REL).exists()


def test_valid_temporary_activation_is_procedural_and_authority_none(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    activation = stage_b.load_activation(repo_root, now=NOW)
    assert activation.activation_epoch == EPOCH
    assert activation.execution_authority == "NONE"
    assert not hasattr(activation, "alias_key")
    assert repr(bytes(range(32))) not in repr(activation)
    assert stage_b.activation_check(repo_root, now=NOW).state is stage_b.ActivationState.ACTIVE


@pytest.mark.parametrize(
    ("relative", "mutation"),
    [
        ("activation/CONFIG.json", "unknown"),
        ("activation/INDEPENDENT_REVIEW.json", "missing"),
        ("activation/FLAT_RECONCILIATION.json", "unknown"),
        ("activation/ROLLBACK_CONFIG.json", "missing"),
        ("activation/ACTIVATION_RECEIPT.json", "unknown"),
    ],
)
def test_activation_json_denies_unknown_and_missing_fields(
    tmp_path: Path, relative: str, mutation: str
) -> None:
    repo_root = _activation_root(tmp_path)
    path = repo_root / stage_b.PRIVATE_ROOT_REL / relative
    value = json.loads(path.read_text())
    if mutation == "unknown":
        value["unexpected"] = "forbidden"
    else:
        value.pop(next(iter(value)))
    _write_json(path, value)
    assert stage_b.activation_check(repo_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.load_activation(repo_root, now=NOW)


def _mutate_activation_document(
    repo_root: Path,
    relative: str,
    mutation: Callable[[dict[str, object]], None],
    *,
    receipt_digest_field: str | None = None,
) -> None:
    private = repo_root / stage_b.PRIVATE_ROOT_REL
    path = private / relative
    value = json.loads(path.read_text())
    mutation(value)
    _write_json(path, value)
    if receipt_digest_field is not None:
        receipt_path = private / stage_b.ACTIVATION_RECEIPT_REL
        receipt = json.loads(receipt_path.read_text())
        receipt[receipt_digest_field] = _sha(path.read_bytes())
        _write_json(receipt_path, receipt)


@pytest.mark.parametrize(
    ("relative", "field", "bad_value", "receipt_digest_field"),
    [
        ("activation/ACTIVATION_RECEIPT.json", "state", "INACTIVE", None),
        ("activation/ACTIVATION_RECEIPT.json", "environment", "PRODUCTION", None),
        ("activation/ACTIVATION_RECEIPT.json", "real_money", True, None),
        ("activation/ACTIVATION_RECEIPT.json", "execution_authority", "LIVE", None),
        ("activation/ACTIVATION_RECEIPT.json", "package_version", "v8.145", None),
        ("activation/ACTIVATION_RECEIPT.json", "repo_commit", "0" * 40, None),
        ("activation/ACTIVATION_RECEIPT.json", "config_path", "../CONFIG.json", None),
        ("activation/ACTIVATION_RECEIPT.json", "config_sha256", "0" * 64, None),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "independent_review_path",
            "../review.json",
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "independent_review_sha256",
            "0" * 64,
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "flat_reconciliation_path",
            "../flat.json",
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "flat_reconciliation_sha256",
            "0" * 64,
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "rollback_config_path",
            "../rollback.json",
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "rollback_config_sha256",
            "0" * 64,
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "private_root",
            "artifacts/evidence/private_demo/other",
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "receipt_path",
            "artifacts/evidence/private_demo/receipt.json",
            None,
        ),
        (
            "activation/ACTIVATION_RECEIPT.json",
            "alias_key_path",
            "artifacts/evidence/private_demo/key",
            None,
        ),
        ("activation/ACTIVATION_RECEIPT.json", "alias_key_sha256", "0" * 64, None),
        ("activation/ACTIVATION_RECEIPT.json", "rollback_commit", "0" * 40, None),
        ("activation/ACTIVATION_RECEIPT.json", "controlled_restart_id", "bad/id", None),
        ("activation/ACTIVATION_RECEIPT.json", "activation_epoch", "act_bad", None),
        (
            "activation/CONFIG.json",
            "implementation_module_sha256",
            "0" * 64,
            "config_sha256",
        ),
        (
            "activation/INDEPENDENT_REVIEW.json",
            "reviewed_commit",
            "0" * 40,
            "independent_review_sha256",
        ),
        (
            "activation/INDEPENDENT_REVIEW.json",
            "config_sha256",
            "0" * 64,
            "independent_review_sha256",
        ),
        (
            "activation/FLAT_RECONCILIATION.json",
            "position_base_qty",
            "1",
            "flat_reconciliation_sha256",
        ),
        (
            "activation/FLAT_RECONCILIATION.json",
            "open_order_count",
            1,
            "flat_reconciliation_sha256",
        ),
        (
            "activation/FLAT_RECONCILIATION.json",
            "unresolved_attempt_count",
            1,
            "flat_reconciliation_sha256",
        ),
        (
            "activation/FLAT_RECONCILIATION.json",
            "protective_stop_state",
            "ACTIVE",
            "flat_reconciliation_sha256",
        ),
        (
            "activation/FLAT_RECONCILIATION.json",
            "all_pages_complete",
            False,
            "flat_reconciliation_sha256",
        ),
        (
            "activation/ROLLBACK_CONFIG.json",
            "rollback_commit",
            "0" * 40,
            "rollback_config_sha256",
        ),
        (
            "activation/ROLLBACK_CONFIG.json",
            "make_start_target",
            "other-target",
            "rollback_config_sha256",
        ),
    ],
)
def test_full_activation_hash_path_and_cross_binding_mismatch_matrix(
    tmp_path: Path,
    relative: str,
    field: str,
    bad_value: object,
    receipt_digest_field: str | None,
) -> None:
    repo_root = _activation_root(tmp_path)
    _mutate_activation_document(
        repo_root,
        relative,
        lambda value: value.__setitem__(field, bad_value),
        receipt_digest_field=receipt_digest_field,
    )
    assert stage_b.activation_check(repo_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE


def test_activation_file_map_source_owner_epoch_and_alias_binding_mismatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_map_root = _activation_root(tmp_path / "file-map")
    receipt_path = file_map_root / stage_b.PRIVATE_ROOT_REL / stage_b.ACTIVATION_RECEIPT_REL
    receipt = json.loads(receipt_path.read_text())
    receipt["file_sha256"]["PROJECT_STATE.md"] = "0" * 64
    _write_json(receipt_path, receipt)
    assert (
        stage_b.activation_check(file_map_root, now=NOW).state
        is stage_b.ActivationState.UNAVAILABLE
    )

    source_root = _activation_root(tmp_path / "source")
    (source_root / "PROJECT_STATE.md").write_text("changed")
    assert (
        stage_b.activation_check(source_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE
    )

    alias_root = _activation_root(tmp_path / "alias")
    alias_path = alias_root / stage_b.PRIVATE_ROOT_REL / stage_b.ALIAS_KEY_REL
    _write_private(alias_path, b"x" * 32)
    assert (
        stage_b.activation_check(alias_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE
    )

    owner_root = _activation_root(tmp_path / "owner")
    real_uid = os.getuid()
    monkeypatch.setattr(os, "getuid", lambda: real_uid + 1)
    assert (
        stage_b.activation_check(owner_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE
    )


def test_activation_requires_a_real_clean_git_head_with_all_bound_files_tracked(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    assert stage_b.load_activation(repo_root, now=NOW).receipt["repo_commit"] == _git(
        repo_root, "rev-parse", "--verify", "HEAD"
    )
    shutil.rmtree(repo_root / ".git")
    with pytest.raises(stage_b.StageBEvidenceError, match="Git"):
        stage_b.load_activation(repo_root, now=NOW)


def test_activation_rejects_symlinked_ancestor_and_repository_root_escape(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path / "ancestor")
    external = tmp_path / "external"
    external.mkdir()
    artifacts = repo_root / "artifacts"
    shutil.move(str(artifacts), str(external / "artifacts"))
    artifacts.symlink_to(external / "artifacts", target_is_directory=True)
    assert stage_b.activation_check(repo_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE

    normal_root = _activation_root(tmp_path / "root-link")
    root_link = tmp_path / "repo-link"
    root_link.symlink_to(normal_root, target_is_directory=True)
    assert stage_b.activation_check(root_link, now=NOW).state is stage_b.ActivationState.UNAVAILABLE


def test_unused_stale_activation_fails_but_consumed_epoch_can_restart(tmp_path: Path) -> None:
    stale = NOW - timedelta(minutes=16)
    repo_root = _activation_root(tmp_path, approved_at=stale)
    with pytest.raises(stage_b.StageBEvidenceError, match="stale"):
        stage_b.load_activation(repo_root, now=NOW)

    fresh_root = _activation_root(tmp_path / "fresh", approved_at=NOW)
    activation_event = _activation_event(fresh_root)
    _append(stage_b.StageBEvidenceSink(fresh_root), [activation_event])
    activation = stage_b.load_activation(fresh_root, now=NOW + timedelta(days=2))
    assert activation.activation_epoch == EPOCH


@pytest.mark.parametrize("mode", [0o644, 0o400, 0o666])
def test_private_file_mode_drift_fails_closed(tmp_path: Path, mode: int) -> None:
    repo_root = _activation_root(tmp_path)
    receipt = repo_root / stage_b.PRIVATE_ROOT_REL / stage_b.ACTIVATION_RECEIPT_REL
    receipt.chmod(mode)
    assert stage_b.activation_check(repo_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE


def test_symlink_hardlink_and_unexpected_path_fail_closed(tmp_path: Path) -> None:
    symlink_root = _activation_root(tmp_path / "symlink")
    receipt = symlink_root / stage_b.PRIVATE_ROOT_REL / stage_b.ACTIVATION_RECEIPT_REL
    backup = receipt.with_suffix(".copy")
    shutil.copyfile(receipt, backup)
    receipt.unlink()
    receipt.symlink_to(backup)
    assert (
        stage_b.activation_check(symlink_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE
    )

    hardlink_root = _activation_root(tmp_path / "hardlink")
    config = hardlink_root / stage_b.PRIVATE_ROOT_REL / "activation/CONFIG.json"
    os.link(config, hardlink_root / "config-hardlink")
    assert (
        stage_b.activation_check(hardlink_root, now=NOW).state
        is stage_b.ActivationState.UNAVAILABLE
    )

    unexpected_root = _activation_root(tmp_path / "unexpected")
    _write_private(unexpected_root / stage_b.PRIVATE_ROOT_REL / "private/extra.key", b"x" * 32)
    assert (
        stage_b.activation_check(unexpected_root, now=NOW).state
        is stage_b.ActivationState.UNAVAILABLE
    )


def test_canonical_json_decimal_timestamp_and_duplicate_key_contract() -> None:
    assert stage_b.canonical_json_bytes({"b": True, "a": "x"}) == b'{"a":"x","b":true}'
    assert stage_b.exact_decimal("0") == 0
    assert stage_b.exact_decimal("1.2300") == Decimal("1.2300")
    assert stage_b.decimal_text(Decimal("1.2300")) == "1.23"
    assert stage_b.canonical_utc(STAMP) == STAMP
    for invalid in ("-0", "01", "1e3", "NaN", "Infinity", " 1", "1." + "0" * 19):
        with pytest.raises(stage_b.StageBEvidenceError):
            stage_b.exact_decimal(invalid)
    with pytest.raises(stage_b.StageBEvidenceError, match="duplicate"):
        stage_b._decode_json(b'{"a":1,"a":2}', label="test")
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.canonical_json_bytes({"float": 1.0})


def test_bool_and_integer_fields_are_type_strict_across_all_boundaries(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path / "receipt")
    receipt_path = repo_root / stage_b.PRIVATE_ROOT_REL / stage_b.ACTIVATION_RECEIPT_REL
    receipt = json.loads(receipt_path.read_text())
    receipt["real_money"] = 0
    _write_json(receipt_path, receipt)
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.load_activation(repo_root, now=NOW)

    flat_root = _activation_root(tmp_path / "flat")
    _mutate_activation_document(
        flat_root,
        "activation/FLAT_RECONCILIATION.json",
        lambda value: value.__setitem__("open_order_count", False),
        receipt_digest_field="flat_reconciliation_sha256",
    )
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.load_activation(flat_root, now=NOW)

    attempt = _standalone_payload(stage_b.EventType.SUBMISSION_ATTEMPTED)
    attempt["attempt_ordinal"] = True
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.EvidenceEvent.create(
            sequence=1,
            previous_event_sha256=None,
            activation_epoch=EPOCH,
            event_type=stage_b.EventType.SUBMISSION_ATTEMPTED,
            recorded_at=STAMP,
            payload=attempt,
        )
    terminal = _standalone_payload(stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED)
    terminal["flat"] = 1
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.EvidenceEvent.create(
            sequence=1,
            previous_event_sha256=None,
            activation_epoch=EPOCH,
            event_type=stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
            recorded_at=STAMP,
            payload=terminal,
        )

    manifest_root = _activation_root(tmp_path / "manifest")
    snapshot = _append(
        stage_b.StageBEvidenceSink(manifest_root),
        _one_episode_chain(manifest_root),
    )
    manifest = dict(snapshot.generations[0].manifest)
    manifest["event_count"] = True
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b._validate_manifest(
            manifest,
            digest=snapshot.generations[0].manifest_sha256,
            activation=snapshot.activation,
        )


def test_event_envelope_denies_unknown_missing_unknown_type_and_wrong_parent(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    event = _activation_event(repo_root)
    raw = event.to_dict()
    raw["extra"] = "forbidden"
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.EvidenceEvent.from_mapping(raw)
    raw = event.to_dict()
    raw.pop("payload")
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.EvidenceEvent.from_mapping(raw)
    raw = event.to_dict()
    raw["event_type"] = "UNKNOWN"
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.EvidenceEvent.from_mapping(raw)
    second = stage_b.next_event(
        event,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.DECISION_OBSERVED,
        recorded_at=STAMP,
        payload={
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "NO_ACTION",
            "side": "NONE",
            "requested_qty": "0",
            "quantity_unit": "NONE",
        },
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="sequence|parent"):
        stage_b.reduce_events([second, event])


def test_every_payload_denies_extra_nested_or_sanitizer_attack(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    for event in _one_episode_chain(repo_root):
        payload = dict(event.payload)
        payload["raw_response"] = {
            "wallet": "0xdeadbeef",
            "authorization": "Bearer secret",
            "url": "https://venue.invalid/order",
            "signal": "buy-now",
            "control": "\u0000",
            "confusable": "\u0430",
        }
        with pytest.raises(stage_b.StageBEvidenceError):
            stage_b.EvidenceEvent.create(
                sequence=event.sequence,
                previous_event_sha256=event.previous_event_sha256,
                activation_epoch=event.activation_epoch,
                event_type=event.event_type,
                recorded_at=event.recorded_at,
                payload=payload,
            )


def _standalone_payload(event_type: stage_b.EventType) -> dict[str, object]:
    values: dict[str, object] = {}
    for field_name in stage_b._PAYLOAD_FIELDS[event_type]:
        if field_name in stage_b._DECIMAL_FIELDS:
            values[field_name] = None if field_name in stage_b._NULLABLE_DECIMALS else "0"
        elif field_name in stage_b._EVENT_REF_FIELDS:
            values[field_name] = (
                None
                if field_name in {"replacement_event_id", "first_affected_event_id"}
                else "evt_" + "a" * 64
            )
        elif field_name in stage_b._SHA_FIELDS:
            values[field_name] = "b" * 64
        elif field_name in stage_b._PRIVATE_ALIAS_FIELDS:
            prefix = {
                "strategy_alias": "strategy_",
                "cost_alias": "cost_",
                "risk_alias": "risk_",
                "order_alias": "ord_",
                "execution_alias": "exe_",
                "fee_alias": "fee_",
            }[field_name]
            values[field_name] = prefix + "c" * 64
        elif field_name in stage_b._BOOLEAN_FIELDS:
            values[field_name] = False
        elif field_name in stage_b._ENUM_FIELDS:
            values[field_name] = sorted(stage_b._ENUM_FIELDS[field_name])[0]
        elif field_name == "client_key":
            values[field_name] = "tios2_contract"
        elif field_name == "controlled_restart_id":
            values[field_name] = "restart_contract"
        elif field_name == "repo_commit":
            values[field_name] = "d" * 40
        elif field_name == "symbol":
            values[field_name] = "ETHUSDT"
        elif field_name == "timeframe":
            values[field_name] = "1h"
        elif field_name in {"attempt_ordinal", "episode_ordinal"}:
            values[field_name] = 1
        elif field_name == "venue_code":
            values[field_name] = 0
        else:
            raise AssertionError(field_name)
    overrides: dict[stage_b.EventType, dict[str, object]] = {
        stage_b.EventType.DECISION_OBSERVED: {
            "decision": "NO_ACTION",
            "side": "NONE",
            "requested_qty": "0",
            "quantity_unit": "NONE",
        },
        stage_b.EventType.RISK_VERDICT_OBSERVED: {
            "verdict": "BLOCK",
            "reason_code": "POLICY_BLOCK",
            "approved_qty": "0",
            "quantity_unit": "NONE",
            "quote_cap": "0",
        },
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED: {
            "client_key_sha256": _sha(b"tios2_contract"),
        },
        stage_b.EventType.SUBMISSION_INTENT_COMMITTED: {
            "order_kind": "EXIT",
            "side": "SELL",
            "order_type": "MARKET",
            "qty": "0",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "risk_increasing": False,
        },
        stage_b.EventType.SUBMISSION_ATTEMPTED: {
            "endpoint": "CREATE",
            "attempt_ordinal": 1,
        },
        stage_b.EventType.VENUE_ACKNOWLEDGED: {
            "result_code": "ACCEPTED_PENDING",
        },
        stage_b.EventType.VENUE_REJECTED: {
            "result_code": "VENUE_REJECTED",
        },
        stage_b.EventType.SUBMISSION_RESULT_UNKNOWN: {
            "result_code": "TIMEOUT",
        },
        stage_b.EventType.ORDER_UPDATE_OBSERVED: {
            "order_status": "NEW",
            "source": "REALTIME",
        },
        stage_b.EventType.FILL_OBSERVED: {
            "side": "BUY",
            "fee_currency": "USDT",
            "source": "EXECUTION",
        },
        stage_b.EventType.CANCEL_OBSERVED: {
            "cancel_state": "ACK_PENDING",
            "source": "REALTIME",
        },
        stage_b.EventType.EXIT_UPDATE_OBSERVED: {
            "exit_state": "STARTED",
        },
        stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED: {
            "terminal_status": "FILLED",
            "protective_stop_state": "CLEAR",
            "flat": True,
            "source": "RECONCILIATION",
            "all_pages_complete": True,
        },
        stage_b.EventType.CLOSED_EPISODE_COMMITTED: {
            "gross_quote": "0",
            "net_quote": "0",
            "third_fee_present": False,
            "eligibility": "ELIGIBLE",
            "ineligibility_code": None,
        },
        stage_b.EventType.CORRECTION_COMMITTED: {
            "correction_code": "SOURCE_CORRECTION",
        },
        stage_b.EventType.EVIDENCE_OUTAGE_RECORDED: {
            "outage_code": "WRITE",
        },
    }
    values.update(overrides.get(event_type, {}))
    return values


def test_independent_literal_file_and_event_contracts_are_exact() -> None:
    assert stage_b._BOUND_FILES == EXPECTED_BOUND_FILES
    assert {
        event_type.value: fields for event_type, fields in stage_b._PAYLOAD_FIELDS.items()
    } == EXPECTED_PAYLOAD_FIELDS
    assert stage_b._ENUM_FIELDS == EXPECTED_ENUMS
    assert stage_b._CONFIG_PATHS == {
        "private_root": "artifacts/evidence/private_demo/stage_b_v2",
        "receipt": "activation/ACTIVATION_RECEIPT.json",
        "config": "activation/CONFIG.json",
        "independent_review": "activation/INDEPENDENT_REVIEW.json",
        "flat_reconciliation": "activation/FLAT_RECONCILIATION.json",
        "rollback_config": "activation/ROLLBACK_CONFIG.json",
        "alias_key": "private/install_alias.key",
        "generations": "store/generations",
        "head": "store/HEAD.json",
        "quarantine": "quarantine",
        "recovery": "recovery",
        "lane_state": "artifacts/trading_domain/demo_lane/lane_state.json",
    }
    assert stage_b._CONFIG_CONTRACTS == {
        "event_schema": "tios.demo_decision_evidence.v2",
        "cohort_size": 30,
        "formula": "EXACT_EXECUTION_CASHFLOW_V1",
        "dashboard_schema": "TIOS_DEMO_LANE_GLOBAL_ALLOWLIST_V2",
        "commit_protocol": "FINAL_DIR_MANIFEST_RENAME_V1",
        "create_attempts_per_logical_submission": 1,
    }
    assert stage_b._CONFIG_LIMITS == {
        "frame_bytes": 65_536,
        "events_per_generation": 4_096,
        "events_bytes": 268_435_456,
        "reducer_bytes": 33_554_432,
        "public_projection_bytes": 4_194_304,
        "cohorts_total": 4_096,
        "pages_per_endpoint": 100,
        "rows_per_page_internal": 50,
    }


def test_every_payload_field_rejects_missing_extra_wrong_type_and_unknown_enum() -> None:
    assert set(stage_b._PAYLOAD_FIELDS) == set(stage_b.EventType)
    for event_type in stage_b.EventType:
        valid = _standalone_payload(event_type)
        stage_b.EvidenceEvent.create(
            sequence=1,
            previous_event_sha256=None,
            activation_epoch=EPOCH,
            event_type=event_type,
            recorded_at=STAMP,
            payload=valid,
        )
        for field_name in stage_b._PAYLOAD_FIELDS[event_type]:
            missing = dict(valid)
            missing.pop(field_name)
            with pytest.raises(stage_b.StageBEvidenceError):
                stage_b.EvidenceEvent.create(
                    sequence=1,
                    previous_event_sha256=None,
                    activation_epoch=EPOCH,
                    event_type=event_type,
                    recorded_at=STAMP,
                    payload=missing,
                )
            wrong = dict(valid)
            wrong[field_name] = []
            with pytest.raises(stage_b.StageBEvidenceError):
                stage_b.EvidenceEvent.create(
                    sequence=1,
                    previous_event_sha256=None,
                    activation_epoch=EPOCH,
                    event_type=event_type,
                    recorded_at=STAMP,
                    payload=wrong,
                )
            if field_name in stage_b._ENUM_FIELDS:
                unknown = dict(valid)
                unknown[field_name] = "UNKNOWN_ENUM_VALUE"
                with pytest.raises(stage_b.StageBEvidenceError):
                    stage_b.EvidenceEvent.create(
                        sequence=1,
                        previous_event_sha256=None,
                        activation_epoch=EPOCH,
                        event_type=event_type,
                        recorded_at=STAMP,
                        payload=unknown,
                    )
        extra = dict(valid)
        extra["unexpected"] = "forbidden"
        with pytest.raises(stage_b.StageBEvidenceError):
            stage_b.EvidenceEvent.create(
                sequence=1,
                previous_event_sha256=None,
                activation_epoch=EPOCH,
                event_type=event_type,
                recorded_at=STAMP,
                payload=extra,
            )


def test_client_key_alias_and_risk_reduction_domain_contract() -> None:
    for key in ("x", "A" * 36, "abc_DEF-123"):
        assert stage_b._CLIENT_KEY.fullmatch(key)
    for key in ("", "A" * 37, "a/b", "a b", "é"):
        assert not stage_b._CLIENT_KEY.fullmatch(key)
    for tag in ("ord", "exe", "fee", "strategy", "cost", "risk"):
        alias = stage_b._derive_private_alias_vector(bytes(range(32)), tag, b"venue-id")
        expected = hmac.new(
            bytes(range(32)),
            b"tios.demo_decision_evidence.v2\x00" + tag.encode() + b"\x00venue-id",
            hashlib.sha256,
        ).hexdigest()
        assert alias == f"{tag}_{expected}"
        assert stage_b._derive_private_alias_vector(bytes(range(32)), tag, b"other-id") != alias
    payload_sha = "9" * 64
    first = stage_b.derive_risk_reduction_client_key(
        activation_epoch=EPOCH,
        subject_intent_event_id="evt_" + "8" * 64,
        action_kind="EXIT_CREATE",
        sequence=1,
        payload_sha256=payload_sha,
    )
    assert len(first) == 36
    assert stage_b._CLIENT_KEY.fullmatch(first)
    assert first == stage_b.derive_risk_reduction_client_key(
        activation_epoch=EPOCH,
        subject_intent_event_id="evt_" + "8" * 64,
        action_kind="EXIT_CREATE",
        sequence=1,
        payload_sha256=payload_sha,
    )


def test_alias_rotation_cannot_rebind_an_existing_nonflat_or_blocked_epoch(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    _blocked_snapshot(repo_root)
    private = repo_root / stage_b.PRIVATE_ROOT_REL
    key_path = private / stage_b.ALIAS_KEY_REL
    new_key = b"z" * 32
    _write_private(key_path, new_key)
    receipt_path = private / stage_b.ACTIVATION_RECEIPT_REL
    receipt = json.loads(receipt_path.read_text())
    receipt["alias_key_sha256"] = _sha(new_key)
    receipt["activation_epoch"] = "act_" + "e" * 64
    receipt["approved_at"] = STAMP
    _write_json(receipt_path, receipt)
    assert stage_b.activation_check(repo_root, now=NOW).state is stage_b.ActivationState.UNAVAILABLE


def test_execution_formulas_quote_base_and_third_currency() -> None:
    events: list[stage_b.EvidenceEvent] = []
    prior: stage_b.EvidenceEvent | None = None
    specs = [
        ("BUY", "2", "20", "0.1", "ETH"),
        ("SELL", "1.9", "22.8", "0.2", "USDT"),
        ("SELL", "0", "0", "0.01", "THIRD"),
    ]
    for index, (side, qty, value, fee, currency) in enumerate(specs, 1):
        event = stage_b.next_event(
            prior,
            activation_epoch=EPOCH,
            event_type=stage_b.EventType.FILL_OBSERVED,
            recorded_at=STAMP,
            payload={
                "order_alias": "ord_" + "a" * 64,
                "execution_alias": f"exe_{index:064x}",
                "fee_alias": f"fee_{index:064x}",
                "side": side,
                "exec_qty": qty,
                "exec_price": "10",
                "exec_value": value,
                "fee_amount": fee,
                "fee_currency": currency,
                "source": "EXECUTION",
            },
        )
        events.append(event)
        prior = event
    economics = stage_b.execution_economics(events)
    assert economics.buy_exec_qty == Decimal("2")
    assert economics.sell_exec_qty == Decimal("1.9")
    assert economics.position_base_qty == 0
    assert economics.quote_fee == Decimal("0.2")
    assert economics.base_fee == Decimal("0.1")
    assert economics.third_fee_present is True
    assert economics.net_quote is None


def test_exact_decimal_sums_do_not_use_the_process_default_28_digit_context() -> None:
    exact = "123456789012345678901234567890.123456789012345678"
    events: list[stage_b.EvidenceEvent] = []
    prior: stage_b.EvidenceEvent | None = None
    for index in range(2):
        event = stage_b.next_event(
            prior,
            activation_epoch=EPOCH,
            event_type=stage_b.EventType.FILL_OBSERVED,
            recorded_at=STAMP,
            payload={
                "order_alias": "ord_" + "a" * 64,
                "execution_alias": f"exe_{index + 100:064x}",
                "fee_alias": f"fee_{index + 100:064x}",
                "side": "BUY",
                "exec_qty": "0",
                "exec_price": "0",
                "exec_value": exact,
                "fee_amount": "0.000000000000000001",
                "fee_currency": "USDT",
                "source": "EXECUTION",
            },
        )
        events.append(event)
        prior = event
    economics = stage_b.execution_economics(events)
    assert stage_b.decimal_text(economics.entry_exec_value) == (
        "246913578024691357802469135780.246913578024691356"
    )
    assert stage_b.decimal_text(economics.quote_fee) == "0.000000000000000002"


def test_manifest_last_commit_replay_and_non_authoritative_head(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    with pytest.raises(stage_b.StageBEvidenceError, match="lane lock"):
        sink.append(events, capability=object(), now=NOW)  # type: ignore[arg-type]
    snapshot = _append(sink, events)
    assert len(snapshot.generations) == 1
    generation = snapshot.generations[0]
    assert generation.path.name == f"G-{generation.manifest_sha256}"
    assert {path.name for path in generation.path.iterdir()} == {
        "events.jsonl",
        "reducer_state.json",
        "public_projection.json",
        "manifest.json",
    }
    assert [event.frame() for event in snapshot.events] == [event.frame() for event in events]
    assert _append(sink, events).head_sha256 == snapshot.head_sha256
    head = repo_root / stage_b.PRIVATE_ROOT_REL / "store/HEAD.json"
    head.write_bytes(b"not-json")
    head.chmod(0o600)
    recovered = sink.load(now=NOW + timedelta(days=1))
    assert recovered.head_sha256 == snapshot.head_sha256


def test_lane_lock_capability_is_real_opaque_repository_bound_and_short_lived(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    sink = stage_b.StageBEvidenceSink(repo_root)
    events = _one_episode_chain(repo_root)
    with pytest.raises(stage_b.StageBEvidenceError, match="constructed"):
        stage_b.LaneLockCapability(
            object(),
            repo_root,
            -1,
            (repo_root / "artifacts/trading_domain/demo_lane/lane.lock").stat(),
        )
    with stage_b.exclusive_lane_lock_capability(repo_root) as capability:
        snapshot = sink.append(events, capability=capability, now=NOW)
    assert snapshot.head_sha256 is not None
    with pytest.raises(stage_b.StageBEvidenceError, match="invalid"):
        sink.append(events, capability=capability, now=NOW)


@pytest.mark.parametrize("unsafe_owner", ["generation_file", "quarantine_root"])
def test_mutation_preflight_rejects_symlinks_before_any_partial_demote(
    tmp_path: Path, unsafe_owner: str
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    private = repo_root / stage_b.PRIVATE_ROOT_REL
    generations = private / "store/generations"
    partial = generations / ("G-" + "f" * 64)
    partial.mkdir(mode=0o700)
    _write_private(partial / "events.jsonl", b"partial\n")
    before = sorted(str(path.relative_to(private)) for path in private.rglob("*"))
    external = tmp_path / "external"
    external.mkdir()
    if unsafe_owner == "generation_file":
        (partial / "events.jsonl").unlink()
        (partial / "events.jsonl").symlink_to(external / "missing")
    else:
        (private / "quarantine").rmdir()
        (private / "quarantine").symlink_to(external, target_is_directory=True)
    before_unsafe_append = sorted(str(path.relative_to(private)) for path in private.rglob("*"))
    sink = stage_b.StageBEvidenceSink(repo_root)
    with pytest.raises(stage_b.StageBEvidenceError, match="symlink"):
        with _lane_capability(repo_root) as capability:
            sink.append(events, capability=capability, now=NOW)
    assert sorted(str(path.relative_to(private)) for path in private.rglob("*")) == (
        before_unsafe_append
    )
    assert before
    assert partial.exists()


def test_second_generation_batch_binds_prior_head_and_cross_chain_parent_is_rejected(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    sink = stage_b.StageBEvidenceSink(repo_root)
    first = _append(sink, _one_episode_chain(repo_root))
    assert first.head_sha256 is not None
    next_decision = stage_b.next_event(
        first.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.DECISION_OBSERVED,
        recorded_at=STAMP,
        payload={
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "NO_ACTION",
            "side": "NONE",
            "requested_qty": "0",
            "quantity_unit": "NONE",
        },
    )
    second = _append(sink, [next_decision])
    assert len(second.generations) == 2
    assert second.generations[1].events == (next_decision,)
    assert second.generations[1].manifest["previous_manifest_sha256"] == first.head_sha256
    assert sink.load(now=NOW).events == second.events

    unrelated = stage_b.EvidenceEvent.create(
        sequence=next_decision.sequence + 1,
        previous_event_sha256="f" * 64,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.DECISION_OBSERVED,
        recorded_at=STAMP,
        payload=next_decision.payload,
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="parent"):
        _append(sink, [unrelated])
    conflicting = stage_b.EvidenceEvent.create(
        sequence=next_decision.sequence,
        previous_event_sha256=next_decision.previous_event_sha256,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.DECISION_OBSERVED,
        recorded_at=STAMP,
        payload={
            **next_decision.payload,
            "strategy_alias": "strategy_" + "f" * 64,
        },
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="conflicting replay"):
        _append(sink, [conflicting])


def test_content_addressed_generation_byte_conflict_fails_and_is_never_overwritten(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    snapshot = _append(sink, events)
    generation = snapshot.generations[0].path
    events_path = generation / "events.jsonl"
    original = events_path.read_bytes()
    corrupted = b"X" + original[1:]
    events_path.write_bytes(corrupted)
    events_path.chmod(0o600)
    with pytest.raises(stage_b.StageBEvidenceError, match="bind|canonical|content"):
        sink.load(now=NOW)
    assert events_path.read_bytes() == corrupted


@pytest.mark.parametrize(
    "target_name",
    ["events.jsonl", "reducer_state.json", "public_projection.json", ".manifest.json.tmp"],
)
def test_write_or_fsync_failure_leaves_uncommitted_material_for_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_name: str
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    real_write = stage_b._write_exclusive

    def fail_selected(path: Path, raw: bytes) -> None:
        if path.name == target_name:
            raise OSError("simulated storage failure")
        real_write(path, raw)

    monkeypatch.setattr(stage_b, "_write_exclusive", fail_selected)
    with pytest.raises(OSError, match="storage"):
        _append(sink, events)
    assert not any(
        (path / "manifest.json").exists()
        for path in (repo_root / stage_b.PRIVATE_ROOT_REL / "store/generations").iterdir()
    )
    monkeypatch.setattr(stage_b, "_write_exclusive", real_write)
    snapshot = _append(sink, events)
    assert snapshot.head_sha256 is not None
    assert any((repo_root / stage_b.PRIVATE_ROOT_REL / "quarantine").iterdir())


@pytest.mark.parametrize(
    "target_name",
    ["events.jsonl", "reducer_state.json", "public_projection.json", ".manifest.json.tmp"],
)
def test_each_data_and_manifest_file_fsync_failure_is_uncommitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target_name: str
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    real_fsync_file = stage_b._fsync_file

    def fail_selected(descriptor: int, path: Path) -> None:
        if path.name == target_name:
            raise OSError("simulated file fsync failure")
        real_fsync_file(descriptor, path)

    monkeypatch.setattr(stage_b, "_fsync_file", fail_selected)
    with pytest.raises(OSError, match="file fsync"):
        _append(sink, events)
    assert not any(
        (path / "manifest.json").exists()
        for path in (repo_root / stage_b.PRIVATE_ROOT_REL / "store/generations").iterdir()
    )


@pytest.mark.parametrize("fault_point", ["generations_parent", "generation_after_rename"])
def test_manifest_rename_is_the_sole_commit_point_across_directory_fsync_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault_point: str
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    real_fsync_directory = stage_b._fsync_directory

    def fail_selected(path: Path) -> None:
        if fault_point == "generations_parent" and path.name == "generations":
            raise OSError("simulated generation-parent fsync failure")
        if fault_point == "generation_after_rename" and path.name.startswith("G-"):
            raise OSError("simulated generation-directory fsync failure")
        real_fsync_directory(path)

    monkeypatch.setattr(stage_b, "_fsync_directory", fail_selected)
    expected_error = (
        OSError if fault_point == "generations_parent" else stage_b.StageBCommittedDurabilityError
    )
    with pytest.raises(expected_error):
        _append(sink, events)
    generations = repo_root / stage_b.PRIVATE_ROOT_REL / "store/generations"
    committed = [path for path in generations.iterdir() if (path / "manifest.json").exists()]
    assert bool(committed) is (fault_point == "generation_after_rename")
    monkeypatch.setattr(stage_b, "_fsync_directory", real_fsync_directory)
    if fault_point == "generation_after_rename":
        assert sink.load(now=NOW).head_sha256 == committed[0].name.removeprefix("G-")
    else:
        assert _append(sink, events).head_sha256 is not None


def test_head_directory_fsync_failure_occurs_after_generation_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    real_fsync_directory = stage_b._fsync_directory

    def fail_store(path: Path) -> None:
        if path.name == "store":
            raise OSError("simulated HEAD directory fsync failure")
        real_fsync_directory(path)

    monkeypatch.setattr(stage_b, "_fsync_directory", fail_store)
    with pytest.raises(stage_b.StageBCommittedHeadError):
        _append(sink, events)
    monkeypatch.setattr(stage_b, "_fsync_directory", real_fsync_directory)
    assert sink.load(now=NOW).head_sha256 is not None


def test_pre_manifest_rename_uncommitted_post_rename_committed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    sink = stage_b.StageBEvidenceSink(repo_root)
    real_replace = os.replace

    def fail_manifest(source: Path | str, target: Path | str) -> None:
        if Path(source).name == ".manifest.json.tmp":
            raise OSError("pre-commit crash")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_manifest)
    with pytest.raises(OSError, match="pre-commit"):
        _append(sink, events)
    monkeypatch.setattr(os, "replace", real_replace)
    committed = _append(sink, events)
    assert committed.head_sha256 is not None

    real_head = stage_b._write_head

    def fail_head(private_root: Path, generation: stage_b.Generation) -> None:
        raise OSError("post-commit crash")

    monkeypatch.setattr(stage_b, "_write_head", fail_head)
    decision = stage_b.next_event(
        committed.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.DECISION_OBSERVED,
        recorded_at=STAMP,
        payload={
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "NO_ACTION",
            "side": "NONE",
            "requested_qty": "0",
            "quantity_unit": "NONE",
        },
    )
    with pytest.raises(stage_b.StageBCommittedHeadError) as raised:
        _append(sink, [decision])
    assert sink.load(now=NOW).head_sha256 == raised.value.manifest_sha256
    monkeypatch.setattr(stage_b, "_write_head", real_head)


def test_513_distinct_execution_frames_commit_and_replay_byte_identically(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    _episode(events, number=1, extra_entry_fills=511)
    assert sum(event.event_type is stage_b.EventType.FILL_OBSERVED for event in events) == 513
    snapshot = _append(stage_b.StageBEvidenceSink(repo_root), events)
    assert b"".join(event.frame() for event in snapshot.events) == b"".join(
        event.frame() for event in events
    )
    assert snapshot.public_projection is not None
    assert _public_cohort(snapshot.public_projection, 0, 0)["aggregate"] is None


def test_29_30_31_episode_fixed_cohort_disclosure_and_immutability(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    for number in range(1, 30):
        _episode(events, number=number)
    projection_29 = stage_b.reduce_events(events).public_projection
    cohort_29 = _public_cohort(projection_29, 0, 0)
    assert cohort_29["assigned_count"] == 29
    assert cohort_29["aggregate"] is None

    _episode(events, number=30)
    projection_30 = stage_b.reduce_events(events).public_projection
    cohort_1_bytes = stage_b.canonical_json_bytes(_public_cohort(projection_30, 0, 0))
    aggregate = _public_cohort(projection_30, 0, 0)["aggregate"]
    assert aggregate == {
        "closed_count": 30,
        "positive_count": 30,
        "negative_count": 0,
        "flat_count": 0,
        "entry_exec_value_total": "300",
        "exit_exec_value_total": "330",
        "gross_quote_total": "30",
        "quote_fee_total": "6",
        "base_fee_total": "0",
        "net_quote_total": "24",
    }

    _episode(events, number=31)
    projection_31 = stage_b.reduce_events(events).public_projection
    assert stage_b.canonical_json_bytes(_public_cohort(projection_31, 0, 0)) == cohort_1_bytes
    assert _public_cohort(projection_31, 0, 1)["aggregate"] is None


def test_unknown_result_latches_entry_block_and_terminal_reconciliation_does_not_clear(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    reduced = stage_b.reduce_events(_one_episode_chain(repo_root, result_unknown=True))
    assert reduced.reducer_state["evidence_state"] == "ENTRY_BLOCK"
    assert reduced.reducer_state["unresolved_order_alias"] is not None
    assert reduced.reducer_state["unresolved_client_key"] is not None
    assert reduced.public_projection["status"] == "ENTRY_BLOCK"


def test_distinct_entry_and_exit_orders_are_bound_to_one_episode_economics(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    refs = _episode(events, number=1)
    assert refs["buy"].payload["order_alias"] != refs["sell"].payload["order_alias"]
    reduced = stage_b.reduce_events(events)
    cohort = _public_cohort(reduced.public_projection, 0, 0)
    assert cohort["eligible_closed_count"] == 1

    without_association = events[: events.index(refs["exit_update"])]
    _append_event(
        without_association,
        stage_b.EventType.FILL_OBSERVED,
        refs["sell"].payload,
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="association"):
        stage_b.reduce_events(without_association)


def test_pending_ack_blocks_a_second_entry_until_terminal_reconciliation(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    full = [_activation_event(repo_root)]
    refs = _episode(full, number=1)
    events = full[: full.index(refs["initial"]) + 1]
    decision = _append_event(
        events,
        stage_b.EventType.DECISION_OBSERVED,
        {
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "ENTRY",
            "side": "BUY",
            "requested_qty": "1",
            "quantity_unit": "BASE",
        },
    )
    risk = _append_event(
        events,
        stage_b.EventType.RISK_VERDICT_OBSERVED,
        {
            "decision_event_id": decision.event_id,
            "verdict": "ALLOW_RISK_INCREASE",
            "reason_code": "POLICY_PASS",
            "approved_qty": "1",
            "quantity_unit": "BASE",
            "quote_cap": "10",
        },
    )
    second_key = "tios2_second_pending"
    _append_event(
        events,
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        {
            "decision_event_id": decision.event_id,
            "risk_event_id": risk.event_id,
            "order_alias": "ord_" + "f" * 64,
            "client_key": second_key,
            "client_key_sha256": _sha(second_key.encode()),
        },
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="pending reconciliation"):
        stage_b.reduce_events(events)


def test_post_terminal_fill_is_forbidden_and_first_incident_is_stable(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    late_fill = dict(
        next(
            event.payload
            for event in reversed(events)
            if event.event_type is stage_b.EventType.FILL_OBSERVED
        )
    )
    late_fill["execution_alias"] = "exe_" + "f" * 64
    _append_event(events, stage_b.EventType.FILL_OBSERVED, late_fill)
    with pytest.raises(stage_b.StageBEvidenceError, match="follows terminal"):
        stage_b.reduce_events(events)

    blocked = _one_episode_chain(repo_root, result_unknown=True)
    first = stage_b.reduce_events(blocked).reducer_state["incident_sha256"]
    blocked_terminal = next(
        event
        for event in reversed(blocked)
        if event.event_type is stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED
    )
    _append_event(
        blocked,
        stage_b.EventType.EVIDENCE_OUTAGE_RECORDED,
        {
            "incident_sha256": "f" * 64,
            "outage_code": "WRITE",
            "first_affected_event_id": blocked_terminal.event_id,
            "risk_reduction_occurred": True,
        },
    )
    assert stage_b.reduce_events(blocked).reducer_state["incident_sha256"] == first


def test_blocked_risk_verdict_cannot_bind_a_risk_increasing_entry_intent(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    decision = _append_event(
        events,
        stage_b.EventType.DECISION_OBSERVED,
        {
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "ENTRY",
            "side": "BUY",
            "requested_qty": "1",
            "quantity_unit": "BASE",
        },
    )
    blocked = _append_event(
        events,
        stage_b.EventType.RISK_VERDICT_OBSERVED,
        {
            "decision_event_id": decision.event_id,
            "verdict": "BLOCK",
            "reason_code": "POLICY_BLOCK",
            "approved_qty": "0",
            "quantity_unit": "BASE",
            "quote_cap": "0",
        },
    )
    key = "tios2_blocked"
    reserved = _append_event(
        events,
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        {
            "decision_event_id": decision.event_id,
            "risk_event_id": blocked.event_id,
            "order_alias": "ord_" + "e" * 64,
            "client_key": key,
            "client_key_sha256": _sha(key.encode()),
        },
    )
    _append_event(
        events,
        stage_b.EventType.SUBMISSION_INTENT_COMMITTED,
        {
            "key_event_id": reserved.event_id,
            "order_alias": "ord_" + "e" * 64,
            "order_kind": "ENTRY",
            "side": "BUY",
            "order_type": "MARKET",
            "qty": "1",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "risk_increasing": True,
        },
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="blocked verdict"):
        stage_b.reduce_events(events)


def test_assigned_outage_episode_is_permanently_ineligible_and_not_refilled(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    refs = _episode(events, number=1)
    outage = stage_b.next_event(
        events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.EVIDENCE_OUTAGE_RECORDED,
        recorded_at=STAMP,
        payload={
            "incident_sha256": "d" * 64,
            "outage_code": "WRITE",
            "first_affected_event_id": refs["buy"].event_id,
            "risk_reduction_occurred": True,
        },
    )
    events.append(outage)
    reduced = stage_b.reduce_events(events)
    cohort = _public_cohort(reduced.public_projection, 0, 0)
    assert cohort["assigned_count"] == 1
    assert cohort["ineligible_count"] == 1
    assert cohort["readiness"] == "PERMANENTLY_INELIGIBLE"
    assert cohort["aggregate"] is None


def test_generation_event_count_4096_boundary_and_4097_rejected(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    for _index in range(1, stage_b.MAX_EVENTS_PER_GENERATION):
        _append_event(
            events,
            stage_b.EventType.DECISION_OBSERVED,
            {
                "strategy_alias": STRATEGY,
                "cost_alias": COST,
                "risk_alias": RISK,
                "symbol": "ETHUSDT",
                "timeframe": "1h",
                "decision": "NO_ACTION",
                "side": "NONE",
                "requested_qty": "0",
                "quantity_unit": "NONE",
            },
        )
    snapshot = _append(stage_b.StageBEvidenceSink(repo_root), events)
    assert snapshot.generations[0].manifest["event_count"] == 4096
    with pytest.raises(stage_b.StageBEvidenceError, match="count"):
        _append(
            stage_b.StageBEvidenceSink(repo_root),
            events
            + [
                stage_b.next_event(
                    events[-1],
                    activation_epoch=EPOCH,
                    event_type=stage_b.EventType.DECISION_OBSERVED,
                    recorded_at=STAMP,
                    payload=events[-1].payload,
                )
            ],
        )


def test_exact_storage_and_page_boundary_constants_are_pinned() -> None:
    assert stage_b.MAX_FRAME_BYTES == 65_536
    assert stage_b.MAX_EVENTS_PER_GENERATION == 4_096
    assert stage_b.MAX_EVENTS_BYTES == 268_435_456
    assert stage_b.MAX_REDUCER_BYTES == 33_554_432
    assert stage_b.MAX_PUBLIC_PROJECTION_BYTES == 4_194_304
    assert stage_b._CONFIG_LIMITS["pages_per_endpoint"] == 100
    assert stage_b._CONFIG_LIMITS["rows_per_page_internal"] == 50
    for maximum, label in (
        (stage_b.MAX_FRAME_BYTES, "frame"),
        (stage_b.MAX_EVENTS_BYTES, "events"),
        (stage_b.MAX_REDUCER_BYTES, "reducer"),
        (stage_b.MAX_PUBLIC_PROJECTION_BYTES, "public projection"),
    ):
        assert stage_b._require_size(maximum, maximum, label) == maximum
        with pytest.raises(stage_b.StageBEvidenceError, match="size"):
            stage_b._require_size(maximum + 1, maximum, label)
        with pytest.raises(stage_b.StageBEvidenceError, match="size"):
            stage_b._require_size(0, maximum, label)
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.parse_event_frame(b" " * stage_b.MAX_FRAME_BYTES)
    with pytest.raises(stage_b.StageBEvidenceError, match="boundary"):
        stage_b.parse_event_frame(b" " * stage_b.MAX_FRAME_BYTES + b"\n")


def test_frame_boundary_is_enforced_by_the_owning_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _activation_root(tmp_path)
    event = _activation_event(repo_root)
    exact = b"x" * (stage_b.MAX_FRAME_BYTES - 1) + b"\n"
    monkeypatch.setattr(
        stage_b,
        "_decode_json",
        lambda _raw, *, label: event.to_dict(),
    )
    monkeypatch.setattr(stage_b.EvidenceEvent, "frame", lambda _self: exact)
    assert stage_b.parse_event_frame(exact) is not None
    with pytest.raises(stage_b.StageBEvidenceError, match="boundary"):
        stage_b.parse_event_frame(b"x" * stage_b.MAX_FRAME_BYTES + b"\n")


@pytest.mark.parametrize(
    ("constant_name", "label"),
    [
        ("MAX_EVENTS_BYTES", "events"),
        ("MAX_REDUCER_BYTES", "reducer"),
        ("MAX_PUBLIC_PROJECTION_BYTES", "public projection"),
    ],
)
def test_serialized_storage_boundaries_run_through_the_append_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    label: str,
) -> None:
    passing_root = _activation_root(tmp_path / "passing")
    passing_events = _one_episode_chain(passing_root)
    passing_reduced = stage_b.reduce_events(passing_events)
    sizes = {
        "MAX_EVENTS_BYTES": len(b"".join(event.frame() for event in passing_events)),
        "MAX_REDUCER_BYTES": len(stage_b.canonical_json_bytes(passing_reduced.reducer_state)),
        "MAX_PUBLIC_PROJECTION_BYTES": len(
            stage_b.canonical_json_bytes(passing_reduced.public_projection)
        ),
    }
    monkeypatch.setattr(stage_b, constant_name, sizes[constant_name])
    assert _append(stage_b.StageBEvidenceSink(passing_root), passing_events).head_sha256

    failing_root = _activation_root(tmp_path / "failing")
    failing_events = _one_episode_chain(failing_root)
    failing_reduced = stage_b.reduce_events(failing_events)
    failing_sizes = {
        "MAX_EVENTS_BYTES": len(b"".join(event.frame() for event in failing_events)),
        "MAX_REDUCER_BYTES": len(stage_b.canonical_json_bytes(failing_reduced.reducer_state)),
        "MAX_PUBLIC_PROJECTION_BYTES": len(
            stage_b.canonical_json_bytes(failing_reduced.public_projection)
        ),
    }
    monkeypatch.setattr(stage_b, constant_name, failing_sizes[constant_name] - 1)
    with pytest.raises(stage_b.StageBEvidenceError, match=label):
        _append(stage_b.StageBEvidenceSink(failing_root), failing_events)
    assert not any((failing_root / stage_b.PRIVATE_ROOT_REL / "store/generations").iterdir())


def test_cohort_limit_runs_through_the_reducer_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]
    for number in range(1, 32):
        _episode(events, number=number)
    monkeypatch.setattr(stage_b, "MAX_COHORTS", 2)
    series = stage_b.reduce_events(events).public_projection["series"]
    assert isinstance(series, list)
    assert len(series) == 1
    monkeypatch.setattr(stage_b, "MAX_COHORTS", 1)
    with pytest.raises(stage_b.StageBEvidenceError, match="cohort limit"):
        stage_b.reduce_events(events)


def test_replay_work_is_bounded_by_generation_and_total_event_caps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = _activation_root(tmp_path)
    sink = stage_b.StageBEvidenceSink(repo_root)
    snapshot = _append(sink, _one_episode_chain(repo_root))
    activation = snapshot.activation
    monkeypatch.setattr(stage_b, "MAX_GENERATIONS", 0)
    with pytest.raises(stage_b.StageBEvidenceError, match="generation count"):
        stage_b.load_snapshot(activation)
    monkeypatch.setattr(stage_b, "MAX_GENERATIONS", 256)
    monkeypatch.setattr(stage_b, "MAX_TOTAL_EVENTS", 1)
    with pytest.raises(stage_b.StageBEvidenceError, match="total event count"):
        stage_b.load_snapshot(activation)


def _blocked_snapshot(repo_root: Path) -> tuple[stage_b.EvidenceSnapshot, stage_b.EvidenceEvent]:
    events = _one_episode_chain(repo_root, result_unknown=True)
    terminal = next(
        event
        for event in reversed(events)
        if event.event_type is stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED
    )
    snapshot = _append(stage_b.StageBEvidenceSink(repo_root), events)
    return snapshot, terminal


def _approval(
    tmp_path: Path,
    *,
    snapshot: stage_b.EvidenceSnapshot,
    terminal: stage_b.EvidenceEvent,
    quarantine_sha256: str,
    approved_at: datetime = NOW,
) -> Path:
    assert snapshot.reducer_state is not None
    approval: dict[str, object] = {
        "schema": "tios.demo_decision_evidence.recovery_approval.v1",
        "decision": "APPROVE_RECOVERY_RECORD_ONLY",
        "activation_epoch": EPOCH,
        "expected_head_sha256": snapshot.head_sha256,
        "expected_incident_sha256": snapshot.reducer_state["incident_sha256"],
        "expected_reconciliation_event_id": terminal.event_id,
        "expected_quarantine_inventory_sha256": quarantine_sha256,
        "reason_code": "CHAIN_VERIFIED_AND_FLAT_RECONCILIATION_REQUIRED",
        "approved_at": stage_b.canonical_utc(approved_at),
    }
    path = (tmp_path / "recovery-approval.json").absolute()
    _write_json(path, approval)
    return path


def test_recovery_cli_writes_record_only_and_never_unlatches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo_root = _activation_root(tmp_path)
    snapshot, terminal = _blocked_snapshot(repo_root)
    inventory, quarantine_sha256 = stage_b.quarantine_inventory(
        repo_root / stage_b.PRIVATE_ROOT_REL
    )
    cli_now = datetime.now(UTC)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=terminal,
        quarantine_sha256=quarantine_sha256,
        approved_at=cli_now,
    )
    assert inventory["entries"] == []
    assert snapshot.head_sha256 is not None
    assert snapshot.reducer_state is not None
    path = stage_b.create_recovery_record(
        repo_root=repo_root,
        approval_path=approval,
        expected_head=snapshot.head_sha256,
        expected_incident=str(snapshot.reducer_state["incident_sha256"]),
        expected_reconciliation=terminal.event_id,
        expected_quarantine=quarantine_sha256,
        now=cli_now,
    )
    assert path.parent == repo_root / stage_b.PRIVATE_ROOT_REL / "recovery"
    assert path.name.startswith("RECOVERY-")
    after = stage_b.StageBEvidenceSink(repo_root).load(now=NOW)
    assert after.reducer_state is not None
    assert after.reducer_state["evidence_state"] == "ENTRY_BLOCK"
    assert after.head_sha256 == snapshot.head_sha256

    monkeypatch.chdir(repo_root)
    status = stage_b.main(
        [
            "recover",
            "--approval",
            str(approval),
            "--expected-head",
            snapshot.head_sha256,
            "--expected-incident",
            str(snapshot.reducer_state["incident_sha256"]),
            "--expected-reconciliation",
            terminal.event_id,
            "--expected-quarantine",
            quarantine_sha256,
        ]
    )
    assert status == 0
    assert capsys.readouterr().out.startswith("STAGE_B_RECOVERY_RECORD_OK RECOVERY-")
    assert len(list(path.parent.iterdir())) == 1

    def fail_with_oserror(**_kwargs: object) -> Path:
        raise OSError("private filesystem detail")

    monkeypatch.setattr(stage_b, "create_recovery_record", fail_with_oserror)
    refused = stage_b.main(
        [
            "recover",
            "--approval",
            str(approval),
            "--expected-head",
            snapshot.head_sha256,
            "--expected-incident",
            str(snapshot.reducer_state["incident_sha256"]),
            "--expected-reconciliation",
            terminal.event_id,
            "--expected-quarantine",
            quarantine_sha256,
        ]
    )
    captured = capsys.readouterr()
    assert refused == 2
    assert captured.err == "STAGE_B_RECOVERY_REFUSED\n"
    assert "private filesystem detail" not in captured.err


def test_recovery_requires_fresh_distinct_reconciliation_and_durable_recovery_event(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    snapshot, candidate = _blocked_snapshot(repo_root)
    _, quarantine_sha256 = stage_b.quarantine_inventory(repo_root / stage_b.PRIVATE_ROOT_REL)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=candidate,
        quarantine_sha256=quarantine_sha256,
    )
    assert snapshot.head_sha256 is not None
    assert snapshot.reducer_state is not None
    record_path = stage_b.create_recovery_record(
        repo_root=repo_root,
        approval_path=approval,
        expected_head=snapshot.head_sha256,
        expected_incident=str(snapshot.reducer_state["incident_sha256"]),
        expected_reconciliation=candidate.event_id,
        expected_quarantine=quarantine_sha256,
        now=NOW,
    )
    record_sha256 = record_path.stem.removeprefix("RECOVERY-")
    approval_sha256 = _sha(approval.read_bytes())
    bad_recovery = stage_b.next_event(
        snapshot.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.RECOVERY_COMMITTED,
        recorded_at=STAMP,
        payload={
            "incident_sha256": snapshot.reducer_state["incident_sha256"],
            "recovery_record_sha256": record_sha256,
            "approval_sha256": approval_sha256,
            "reconciliation_event_id": candidate.event_id,
            "prior_head_sha256": snapshot.head_sha256,
        },
    )
    sink = stage_b.StageBEvidenceSink(repo_root)
    with pytest.raises(stage_b.StageBEvidenceError, match="distinct fresh"):
        _append(sink, [bad_recovery])

    fresh = stage_b.next_event(
        snapshot.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        recorded_at=STAMP,
        payload=candidate.payload,
    )
    reconciled_only = stage_b.reduce_events((*snapshot.events, fresh))
    assert reconciled_only.reducer_state["evidence_state"] == "ENTRY_BLOCK"
    recovery = stage_b.next_event(
        fresh,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.RECOVERY_COMMITTED,
        recorded_at=STAMP,
        payload={
            "incident_sha256": snapshot.reducer_state["incident_sha256"],
            "recovery_record_sha256": record_sha256,
            "approval_sha256": approval_sha256,
            "reconciliation_event_id": fresh.event_id,
            "prior_head_sha256": snapshot.head_sha256,
        },
    )
    recovered = _append(sink, [fresh, recovery])
    assert recovered.reducer_state is not None
    assert recovered.reducer_state["evidence_state"] == "READY"
    assert recovered.reducer_state["incident_sha256"] is None


def test_historical_recovery_replay_requires_its_record_to_remain_valid(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    snapshot, candidate = _blocked_snapshot(repo_root)
    _, quarantine_sha256 = stage_b.quarantine_inventory(repo_root / stage_b.PRIVATE_ROOT_REL)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=candidate,
        quarantine_sha256=quarantine_sha256,
    )
    assert snapshot.head_sha256 is not None
    assert snapshot.reducer_state is not None
    record = stage_b.create_recovery_record(
        repo_root=repo_root,
        approval_path=approval,
        expected_head=snapshot.head_sha256,
        expected_incident=str(snapshot.reducer_state["incident_sha256"]),
        expected_reconciliation=candidate.event_id,
        expected_quarantine=quarantine_sha256,
        now=NOW,
    )
    fresh = stage_b.next_event(
        snapshot.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        recorded_at=STAMP,
        payload=candidate.payload,
    )
    recovery = stage_b.next_event(
        fresh,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.RECOVERY_COMMITTED,
        recorded_at=STAMP,
        payload={
            "incident_sha256": snapshot.reducer_state["incident_sha256"],
            "recovery_record_sha256": record.stem.removeprefix("RECOVERY-"),
            "approval_sha256": _sha(approval.read_bytes()),
            "reconciliation_event_id": fresh.event_id,
            "prior_head_sha256": snapshot.head_sha256,
        },
    )
    sink = stage_b.StageBEvidenceSink(repo_root)
    assert _append(sink, [fresh, recovery]).reducer_state is not None
    record.unlink()
    with pytest.raises(stage_b.StageBEvidenceError, match="required private path"):
        sink.load(now=NOW)


def test_incident_without_an_order_alias_uses_whole_lane_flat_recovery(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    candidate = next(
        event
        for event in reversed(events)
        if event.event_type is stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED
    )
    _append_event(
        events,
        stage_b.EventType.EVIDENCE_OUTAGE_RECORDED,
        {
            "incident_sha256": "d" * 64,
            "outage_code": "WRITE",
            "first_affected_event_id": None,
            "risk_reduction_occurred": False,
        },
    )
    sink = stage_b.StageBEvidenceSink(repo_root)
    snapshot = _append(sink, events)
    assert snapshot.reducer_state is not None
    assert snapshot.reducer_state["unresolved_order_alias"] is None
    _, quarantine_sha256 = stage_b.quarantine_inventory(repo_root / stage_b.PRIVATE_ROOT_REL)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=candidate,
        quarantine_sha256=quarantine_sha256,
    )
    assert snapshot.head_sha256 is not None
    record = stage_b.create_recovery_record(
        repo_root=repo_root,
        approval_path=approval,
        expected_head=snapshot.head_sha256,
        expected_incident="d" * 64,
        expected_reconciliation=candidate.event_id,
        expected_quarantine=quarantine_sha256,
        now=NOW,
    )
    fresh = stage_b.next_event(
        snapshot.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        recorded_at=STAMP,
        payload=candidate.payload,
    )
    recovery = stage_b.next_event(
        fresh,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.RECOVERY_COMMITTED,
        recorded_at=STAMP,
        payload={
            "incident_sha256": "d" * 64,
            "recovery_record_sha256": record.stem.removeprefix("RECOVERY-"),
            "approval_sha256": _sha(approval.read_bytes()),
            "reconciliation_event_id": fresh.event_id,
            "prior_head_sha256": snapshot.head_sha256,
        },
    )
    recovered = _append(sink, [fresh, recovery])
    assert recovered.reducer_state is not None
    assert recovered.reducer_state["evidence_state"] == "READY"
    assert recovered.reducer_state["incident_sha256"] is None
    assert recovered.reducer_state["unresolved_order_alias"] is None


def test_recovery_approval_freshness_is_strictly_fifteen_minutes(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    snapshot, terminal = _blocked_snapshot(repo_root)
    _, quarantine_sha256 = stage_b.quarantine_inventory(repo_root / stage_b.PRIVATE_ROOT_REL)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=terminal,
        quarantine_sha256=quarantine_sha256,
    )
    value = json.loads(approval.read_text())
    value["approved_at"] = stage_b.canonical_utc(NOW - timedelta(minutes=15, microseconds=1))
    _write_json(approval, value)
    assert snapshot.head_sha256 is not None
    assert snapshot.reducer_state is not None
    with pytest.raises(stage_b.StageBEvidenceError, match="stale"):
        stage_b.create_recovery_record(
            repo_root=repo_root,
            approval_path=approval,
            expected_head=snapshot.head_sha256,
            expected_incident=str(snapshot.reducer_state["incident_sha256"]),
            expected_reconciliation=terminal.event_id,
            expected_quarantine=quarantine_sha256,
            now=NOW,
        )


@pytest.mark.parametrize(
    "changed",
    ["head", "incident", "reconciliation", "quarantine"],
)
def test_recovery_refuses_argument_or_inventory_mismatch(tmp_path: Path, changed: str) -> None:
    repo_root = _activation_root(tmp_path)
    snapshot, terminal = _blocked_snapshot(repo_root)
    _, quarantine_sha256 = stage_b.quarantine_inventory(repo_root / stage_b.PRIVATE_ROOT_REL)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=terminal,
        quarantine_sha256=quarantine_sha256,
    )
    assert snapshot.head_sha256 is not None
    assert snapshot.reducer_state is not None
    arguments = {
        "expected_head": snapshot.head_sha256,
        "expected_incident": str(snapshot.reducer_state["incident_sha256"]),
        "expected_reconciliation": terminal.event_id,
        "expected_quarantine": quarantine_sha256,
    }
    field = f"expected_{changed}"
    arguments[field] = ("evt_" + "f" * 64) if changed == "reconciliation" else "f" * 64
    with pytest.raises(stage_b.StageBEvidenceError):
        stage_b.create_recovery_record(
            repo_root=repo_root,
            approval_path=approval,
            now=NOW,
            **arguments,
        )
    assert not any((repo_root / stage_b.PRIVATE_ROOT_REL / "recovery").iterdir())


def test_quarantine_inventory_binds_path_mode_bytes_and_content(tmp_path: Path) -> None:
    repo_root = _activation_root(tmp_path)
    private = repo_root / stage_b.PRIVATE_ROOT_REL
    interrupted = private / "quarantine" / "U-12345678-1234-4234-9234-123456789abc"
    interrupted.mkdir(mode=0o700)
    _write_private(interrupted / "events.jsonl", b"partial\n")
    inventory, digest = stage_b.quarantine_inventory(private)
    assert inventory["entries"] == [
        {
            "path": interrupted.name,
            "type": "DIR",
            "mode": "0700",
            "bytes": None,
            "sha256": None,
        },
        {
            "path": f"{interrupted.name}/events.jsonl",
            "type": "FILE",
            "mode": "0600",
            "bytes": 8,
            "sha256": _sha(b"partial\n"),
        },
    ]
    (interrupted / "events.jsonl").write_bytes(b"changed\n")
    (interrupted / "events.jsonl").chmod(0o600)
    _, changed = stage_b.quarantine_inventory(private)
    assert changed != digest


def test_public_projection_never_contains_private_alias_key_or_individual_rows(
    tmp_path: Path,
) -> None:
    repo_root = _activation_root(tmp_path)
    events = _one_episode_chain(repo_root)
    snapshot = _append(stage_b.StageBEvidenceSink(repo_root), events)
    public = stage_b.public_stage_b_projection(repo_root, now=NOW)
    encoded = stage_b.canonical_json_bytes(public)
    for forbidden in (
        b"strategy_",
        b"cost_",
        b"risk_",
        b"ord_",
        b"exe_",
        b"fee_",
        b"tios2_",
        b"recorded_at",
        b"event_id",
        b"wallet",
        b"signal",
        b"position",
        b"pnl",
    ):
        assert forbidden not in encoded
    assert snapshot.reducer_state is not None
    assert snapshot.reducer_state["unresolved_client_key"] is None


WHOLE_LANE_ALIAS = stage_b._WHOLE_LANE_RECONCILIATION_ALIAS


def _bound_payload(
    activation: stage_b.ActivationContext, *, repo_commit: object
) -> dict[str, object]:
    return {
        "activation_receipt_sha256": activation.receipt_sha256,
        "config_sha256": activation.config_sha256,
        "independent_review_sha256": activation.independent_review_sha256,
        "flat_reconciliation_sha256": activation.flat_reconciliation_sha256,
        "rollback_config_sha256": activation.rollback_config_sha256,
        "controlled_restart_id": "restart_stage_b_test",
        "repo_commit": repo_commit,
    }


def _whole_lane_outage(events: list[stage_b.EvidenceEvent], *, incident: str) -> None:
    _append_event(
        events,
        stage_b.EventType.EVIDENCE_OUTAGE_RECORDED,
        {
            "incident_sha256": incident,
            "outage_code": "WRITE",
            "first_affected_event_id": None,
            "risk_reduction_occurred": False,
        },
    )


def _zero_terminal(
    events: list[stage_b.EvidenceEvent], *, order_alias: str
) -> stage_b.EvidenceEvent:
    return _append_event(
        events,
        stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        {
            "order_alias": order_alias,
            "terminal_status": "CANCELLED",
            "buy_exec_qty": "0",
            "sell_exec_qty": "0",
            "entry_exec_value": "0",
            "exit_exec_value": "0",
            "quote_fee": "0",
            "base_fee": "0",
            "third_fee_present": False,
            "position_base_qty": "0",
            "protective_stop_state": "CLEAR",
            "flat": True,
            "source": "RECONCILIATION",
            "all_pages_complete": True,
        },
    )


def _acknowledged_exit_order(
    events: list[stage_b.EvidenceEvent], *, order_alias: str, key: str
) -> None:
    """Append a risk-reducing exit that reaches SUBMISSION_ATTEMPTED + ACK but no terminal."""

    key_sha = _sha(key.encode("ascii"))
    decision = _append_event(
        events,
        stage_b.EventType.DECISION_OBSERVED,
        {
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "EXIT",
            "side": "SELL",
            "requested_qty": "1",
            "quantity_unit": "BASE",
        },
    )
    risk = _append_event(
        events,
        stage_b.EventType.RISK_VERDICT_OBSERVED,
        {
            "decision_event_id": decision.event_id,
            "verdict": "RISK_REDUCING",
            "reason_code": "EXIT_ONLY",
            "approved_qty": "1",
            "quantity_unit": "BASE",
            "quote_cap": "0",
        },
    )
    reserved = _append_event(
        events,
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        {
            "decision_event_id": decision.event_id,
            "risk_event_id": risk.event_id,
            "order_alias": order_alias,
            "client_key": key,
            "client_key_sha256": key_sha,
        },
    )
    intent = _append_event(
        events,
        stage_b.EventType.SUBMISSION_INTENT_COMMITTED,
        {
            "key_event_id": reserved.event_id,
            "order_alias": order_alias,
            "order_kind": "EXIT",
            "side": "SELL",
            "order_type": "MARKET",
            "qty": "1",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "risk_increasing": False,
        },
    )
    attempted = _append_event(
        events,
        stage_b.EventType.SUBMISSION_ATTEMPTED,
        {
            "intent_event_id": intent.event_id,
            "order_alias": order_alias,
            "client_key_sha256": key_sha,
            "endpoint": "CREATE",
            "attempt_ordinal": 1,
        },
    )
    _append_event(
        events,
        stage_b.EventType.VENUE_ACKNOWLEDGED,
        {
            "attempt_event_id": attempted.event_id,
            "order_alias": order_alias,
            "venue_code": 0,
            "result_code": "ACCEPTED_PENDING",
        },
    )


def test_outstanding_submitted_attempt_blocks_recovery_until_it_reaches_terminal(
    tmp_path: Path,
) -> None:
    """Remediation 1: a submitted risk-reducing order keeps the lane un-recoverable until
    its EXACT terminal reconciliation, even when a whole-lane flat reconciliation exists."""

    repo_root = _activation_root(tmp_path)
    exit_order = "ord_" + "a1" * 32
    incident = "d" * 64

    def base_chain() -> list[stage_b.EvidenceEvent]:
        events = [_activation_event(repo_root)]
        _whole_lane_outage(events, incident=incident)
        _acknowledged_exit_order(events, order_alias=exit_order, key="tios2_outstanding_exit_key")
        return events

    # The order reached SUBMISSION_ATTEMPTED and was acknowledged but never terminally
    # reconciled, so a whole-lane flat reconciliation must NOT let recovery proceed.
    refused = base_chain()
    fresh_whole_lane = _zero_terminal(refused, order_alias=WHOLE_LANE_ALIAS)
    _append_event(
        refused,
        stage_b.EventType.RECOVERY_COMMITTED,
        {
            "incident_sha256": incident,
            "recovery_record_sha256": "e" * 64,
            "approval_sha256": "f" * 64,
            "reconciliation_event_id": fresh_whole_lane.event_id,
            "prior_head_sha256": "1" * 64,
        },
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="fresh flat reconciliation"):
        stage_b.reduce_events(refused)

    # Once the outstanding order itself reaches terminal reconciliation, recovery is allowed.
    permitted = base_chain()
    order_terminal = _zero_terminal(permitted, order_alias=exit_order)
    _append_event(
        permitted,
        stage_b.EventType.RECOVERY_COMMITTED,
        {
            "incident_sha256": incident,
            "recovery_record_sha256": "e" * 64,
            "approval_sha256": "f" * 64,
            "reconciliation_event_id": order_terminal.event_id,
            "prior_head_sha256": "1" * 64,
        },
    )
    recovered = stage_b.reduce_events(permitted)
    assert recovered.reducer_state["evidence_state"] == "READY"
    assert recovered.reducer_state["incident_sha256"] is None


def test_first_incident_ownership_survives_a_later_missing_submission_result(
    tmp_path: Path,
) -> None:
    """Remediation 3: a later missing-submission-result must never overwrite the first
    unknown-result incident (identity, alias, and client key are all first-owned)."""

    repo_root = _activation_root(tmp_path)
    events = [_activation_event(repo_root)]

    first_order = "ord_" + "b2" * 32
    first_key = "tios2_first_unknown_key"
    first_key_sha = _sha(first_key.encode("ascii"))
    decision = _append_event(
        events,
        stage_b.EventType.DECISION_OBSERVED,
        {
            "strategy_alias": STRATEGY,
            "cost_alias": COST,
            "risk_alias": RISK,
            "symbol": "ETHUSDT",
            "timeframe": "1h",
            "decision": "ENTRY",
            "side": "BUY",
            "requested_qty": "1",
            "quantity_unit": "BASE",
        },
    )
    risk = _append_event(
        events,
        stage_b.EventType.RISK_VERDICT_OBSERVED,
        {
            "decision_event_id": decision.event_id,
            "verdict": "ALLOW_RISK_INCREASE",
            "reason_code": "POLICY_PASS",
            "approved_qty": "1",
            "quantity_unit": "BASE",
            "quote_cap": "10",
        },
    )
    reserved = _append_event(
        events,
        stage_b.EventType.IDEMPOTENCY_KEY_RESERVED,
        {
            "decision_event_id": decision.event_id,
            "risk_event_id": risk.event_id,
            "order_alias": first_order,
            "client_key": first_key,
            "client_key_sha256": first_key_sha,
        },
    )
    intent = _append_event(
        events,
        stage_b.EventType.SUBMISSION_INTENT_COMMITTED,
        {
            "key_event_id": reserved.event_id,
            "order_alias": first_order,
            "order_kind": "ENTRY",
            "side": "BUY",
            "order_type": "MARKET",
            "qty": "1",
            "quantity_unit": "BASE",
            "trigger_price": None,
            "risk_increasing": True,
        },
    )
    attempted = _append_event(
        events,
        stage_b.EventType.SUBMISSION_ATTEMPTED,
        {
            "intent_event_id": intent.event_id,
            "order_alias": first_order,
            "client_key_sha256": first_key_sha,
            "endpoint": "CREATE",
            "attempt_ordinal": 1,
        },
    )
    unknown = _append_event(
        events,
        stage_b.EventType.SUBMISSION_RESULT_UNKNOWN,
        {
            "attempt_event_id": attempted.event_id,
            "order_alias": first_order,
            "venue_code": 0,
            "result_code": "TIMEOUT",
        },
    )
    # A later risk-reducing exit whose create result never arrives: the post-loop
    # missing-result handler must not latch over the earlier incident.
    _acknowledged_exit_order(events, order_alias="ord_" + "c3" * 32, key="tios2_second_missing")
    events.pop()  # drop the VENUE_ACKNOWLEDGED so the second attempt has NO initial result

    reduced = stage_b.reduce_events(events)
    assert reduced.reducer_state["incident_sha256"] == unknown.frame_sha256
    assert reduced.reducer_state["unresolved_order_alias"] == first_order
    assert reduced.reducer_state["unresolved_client_key"] == first_key


def test_whole_lane_recovery_route_immediately_after_activation_with_null_alias(
    tmp_path: Path,
) -> None:
    """Remediation 4: an outage immediately after ACTIVATION_BOUND with a NULL unresolved
    alias recovers through whole-lane pre/fresh flat reconciliations back to READY."""

    repo_root = _activation_root(tmp_path)
    incident = "d" * 64
    events = [_activation_event(repo_root)]
    _whole_lane_outage(events, incident=incident)
    candidate = _zero_terminal(events, order_alias=WHOLE_LANE_ALIAS)

    sink = stage_b.StageBEvidenceSink(repo_root)
    snapshot = _append(sink, events)
    assert snapshot.reducer_state is not None
    assert snapshot.reducer_state["evidence_state"] == "ENTRY_BLOCK"
    assert snapshot.reducer_state["unresolved_order_alias"] is None
    assert snapshot.head_sha256 is not None

    _, quarantine_sha256 = stage_b.quarantine_inventory(repo_root / stage_b.PRIVATE_ROOT_REL)
    approval = _approval(
        tmp_path,
        snapshot=snapshot,
        terminal=candidate,
        quarantine_sha256=quarantine_sha256,
    )
    record = stage_b.create_recovery_record(
        repo_root=repo_root,
        approval_path=approval,
        expected_head=snapshot.head_sha256,
        expected_incident=incident,
        expected_reconciliation=candidate.event_id,
        expected_quarantine=quarantine_sha256,
        now=NOW,
    )
    # Build the durable fresh whole-lane reconciliation + recovery commit off the real head.
    fresh = stage_b.next_event(
        snapshot.events[-1],
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.TERMINAL_RECONCILIATION_COMMITTED,
        recorded_at=STAMP,
        payload=candidate.payload,
    )
    recovery = stage_b.next_event(
        fresh,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.RECOVERY_COMMITTED,
        recorded_at=STAMP,
        payload={
            "incident_sha256": incident,
            "recovery_record_sha256": record.stem.removeprefix("RECOVERY-"),
            "approval_sha256": _sha(approval.read_bytes()),
            "reconciliation_event_id": fresh.event_id,
            "prior_head_sha256": snapshot.head_sha256,
        },
    )
    recovered = _append(sink, [fresh, recovery])
    assert recovered.reducer_state is not None
    assert recovered.reducer_state["evidence_state"] == "READY"
    assert recovered.reducer_state["incident_sha256"] is None


def test_append_rejects_wrong_genesis_binding_and_epoch_without_committing(
    tmp_path: Path,
) -> None:
    """Remediation 2: a genesis whose ACTIVATION_BOUND payload or event epoch disagrees with
    the activation bundle fails in append BEFORE commit, leaving zero generations on disk."""

    repo_root = _activation_root(tmp_path)
    activation = stage_b.load_activation(repo_root, now=NOW)
    sink = stage_b.StageBEvidenceSink(repo_root)
    generations = repo_root / stage_b.PRIVATE_ROOT_REL / "store/generations"

    wrong_binding = stage_b.next_event(
        None,
        activation_epoch=EPOCH,
        event_type=stage_b.EventType.ACTIVATION_BOUND,
        recorded_at=STAMP,
        payload=_bound_payload(activation, repo_commit="0" * 40),
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="ACTIVATION_BOUND disagrees"):
        _append(sink, [wrong_binding])
    assert not any(generations.iterdir())

    wrong_epoch = stage_b.next_event(
        None,
        activation_epoch="act_" + "b" * 64,
        event_type=stage_b.EventType.ACTIVATION_BOUND,
        recorded_at=STAMP,
        payload=_bound_payload(activation, repo_commit=activation.receipt["repo_commit"]),
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="epoch disagrees"):
        _append(sink, [wrong_epoch])
    assert not any(generations.iterdir())


def test_committed_generation_with_mismatched_event_epoch_fails_historical_replay(
    tmp_path: Path,
) -> None:
    """Remediation 2: a committed generation whose event envelope epoch differs from the
    receipt epoch (manifest epoch still bound) is rejected on historical replay."""

    repo_root = _activation_root(tmp_path)
    activation = stage_b.load_activation(repo_root, now=NOW)
    genesis = stage_b.next_event(
        None,
        activation_epoch="act_" + "b" * 64,
        event_type=stage_b.EventType.ACTIVATION_BOUND,
        recorded_at=STAMP,
        payload=_bound_payload(activation, repo_commit=activation.receipt["repo_commit"]),
    )
    reduced = stage_b.reduce_events([genesis])
    stage_b._commit_generation(
        activation=activation,
        events=[genesis],
        reduced=reduced,
        previous_manifest_sha256=None,
        committed_at=NOW,
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="epoch disagrees"):
        stage_b.load_snapshot(activation)


def test_git_binding_rejects_dirty_recomputed_wrong_head_and_untracked_bound_file(
    tmp_path: Path,
) -> None:
    """Reviewer request: activation binds real Git state, defending beyond content hashing."""

    # (1) Dirty bound file, with the receipt/review file_sha256 maps RECOMPUTED to match the
    # dirtied bytes: content-hash binding passes, but `git status --porcelain` still fails.
    dirty_root = _activation_root(tmp_path / "dirty")
    target = dirty_root / "PROJECT_STATE.md"
    target.write_bytes(target.read_bytes() + b"\n<!-- working-tree drift -->\n")
    new_digest = _sha(target.read_bytes())
    private = dirty_root / stage_b.PRIVATE_ROOT_REL
    review_path = private / "activation/INDEPENDENT_REVIEW.json"
    review = json.loads(review_path.read_text())
    review["file_sha256"]["PROJECT_STATE.md"] = new_digest
    _write_json(review_path, review)
    receipt_path = private / stage_b.ACTIVATION_RECEIPT_REL
    receipt = json.loads(receipt_path.read_text())
    receipt["file_sha256"]["PROJECT_STATE.md"] = new_digest
    receipt["independent_review_sha256"] = _sha(review_path.read_bytes())
    _write_json(receipt_path, receipt)
    with pytest.raises(stage_b.StageBEvidenceError, match="dirty"):
        stage_b.load_activation(dirty_root, now=NOW)

    # (2) Wrong HEAD: the working tree/receipt stay clean but HEAD advances past the receipt.
    head_root = _activation_root(tmp_path / "head")
    _git(
        head_root,
        "-c",
        "user.name=Stage B Fixture",
        "-c",
        "user.email=stage-b-fixture@example.invalid",
        "commit",
        "--allow-empty",
        "--quiet",
        "-m",
        "advance HEAD past the receipt",
    )
    with pytest.raises(stage_b.StageBEvidenceError, match="actual Git HEAD"):
        stage_b.load_activation(head_root, now=NOW)

    # (3) Untracked bound file: content on disk still matches, but it is no longer tracked.
    untracked_root = _activation_root(tmp_path / "untracked")
    _git(untracked_root, "rm", "--cached", "--quiet", "--", "docs/architecture/AD.md")
    with pytest.raises(stage_b.StageBEvidenceError, match="tracked"):
        stage_b.load_activation(untracked_root, now=NOW)

    # (4) Missing bound file: deleting it fails the content binding before Git is consulted.
    missing_root = _activation_root(tmp_path / "missing")
    (missing_root / "docs/architecture/AD.md").unlink()
    with pytest.raises(stage_b.StageBEvidenceError, match="unavailable"):
        stage_b.load_activation(missing_root, now=NOW)
