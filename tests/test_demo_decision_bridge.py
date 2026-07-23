from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import sqlite3
import stat
from collections.abc import Mapping
from pathlib import Path

import pytest

import tios.evidence.demo_decision_bridge as bridge
from tios.evidence.demo_decision_bridge import (
    BAR_DISPOSITIONS,
    DecimalFidelity,
    DemoDecisionBridgeError,
    EventType,
    EvidenceConflictError,
    NumericLexeme,
    SourceIncidentError,
    build_legacy_projection,
    canonical_digest,
    canonical_json,
    canonical_jsonl,
    canonical_timestamp,
    decimal_evidence,
    make_event,
    parse_json_bytes,
    reduce_events,
    run_bridge,
    stable_id,
    validate_event,
    validate_no_secrets,
    validate_projection,
    validate_source_progress,
)

_CLI_PATH = Path(__file__).resolve().parents[1] / "scripts/build_demo_decision_evidence.py"
_CLI_SPEC = importlib.util.spec_from_file_location("build_demo_decision_evidence", _CLI_PATH)
assert _CLI_SPEC is not None and _CLI_SPEC.loader is not None
cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(cli)

CAPTURED_AT = "2026-07-23T07:00:00Z"
ORDER_AT = "2026-07-23T06:59:00+00:00"
SOURCE_REF = {
    "kind": "test",
    "label": "sanitized-copy.test",
    "sha256": "a" * 64,
    "byte_count": 10,
}


def _write_copied_fixture(repo: Path) -> tuple[Path, Path, Path]:
    copied = repo / "operator-copied"
    copied.mkdir(parents=True)
    lane_state = copied / "lane_state.json"
    heartbeat = copied / "heartbeat.json"
    orders = copied / "orders.jsonl"
    lane_state.write_bytes(
        b'{"entry_price":"1862.3700","lane_base":"0.01341033",'
        b'"resting_stop":{"base_qty":"0.01341","order_id":"stop-raw-42",'
        b'"position_base_qty":"0.01341033","price_tick":"0.01",'
        b'"risk_boundary_price":"1583.0145","risk_fraction":"0.15",'
        b'"state":"ACTIVE","trigger_price":"1583.02"}}\n'
    )
    heartbeat.write_bytes(
        b'{"at":"2026-07-23T06:59:30Z","lane_base":"0.01341033",'
        b'"mark_price":"1900.00","wallet":{"ETH":"0.01341033","USDT":"12345.67"}}\n'
    )
    orders.write_bytes(
        b'{"avg_price":"1862.3700","cum_exec_qty":"0.01341033","fee":"0.00000420",'
        b'"ok":true,"order_id":"venue-raw-123","reconcile":'
        b'{"ETH_delta":0.01341033,"USDT_delta":-25.0000},'
        b'"recorded_at":"2026-07-23T06:59:00+00:00","side":"Buy",'
        b'"signal_ref":"sanitized-signal"}\n'
    )
    return lane_state, heartbeat, orders


def _run(repo: Path, *, before_checkpoint=None):  # type: ignore[no-untyped-def]
    lane_state, heartbeat, orders = _write_copied_fixture(repo)
    result = run_bridge(
        lane_state_path=lane_state,
        heartbeat_path=heartbeat,
        orders_path=orders,
        output_dir=repo / "artifacts/evidence/demo-decision-stage-a",
        source_label="operator-copy-20260723",
        captured_at=CAPTURED_AT,
        repo_root=repo,
        before_checkpoint=before_checkpoint,
    )
    return result, (lane_state, heartbeat, orders)


def _output_dir(result) -> Path:  # type: ignore[no-untyped-def]
    return result.export_path.parents[2]


def _current_generation_dir(output: Path) -> Path:
    current = json.loads((output / "CURRENT.json").read_text(encoding="utf-8"))
    return output / "generations" / current["generation_id"]


def _event(
    event_type: EventType,
    *,
    minute: int,
    logical_key: str,
    payload: Mapping[str, object],
    decision_id: str | None = None,
    attempt_id: str | None = None,
) -> dict[str, object]:
    return make_event(
        event_type,
        logical_key=logical_key,
        occurred_at=f"2026-07-23T00:{minute:02d}:00Z",
        source_ref=SOURCE_REF,
        payload=payload,
        decision_id=decision_id,
        attempt_id=attempt_id,
    )


def _future_lifecycle() -> list[dict[str, object]]:
    quantity = decimal_evidence("1.25", DecimalFidelity.CANONICAL_DECIMAL_EXACT)
    return [
        _event(
            EventType.BAR_EVALUATED,
            minute=0,
            logical_key="bar:1",
            payload={"disposition": "ENTRY_SIGNAL"},
            decision_id="DEC-future",
        ),
        _event(
            EventType.ORDER_ATTEMPTED,
            minute=1,
            logical_key="attempt:1",
            payload={},
            decision_id="DEC-future",
            attempt_id="ATT-future",
        ),
        _event(
            EventType.ORDER_ACKNOWLEDGED,
            minute=2,
            logical_key="ack:1",
            payload={},
            decision_id="DEC-future",
            attempt_id="ATT-future",
        ),
        _event(
            EventType.ORDER_PARTIALLY_FILLED,
            minute=3,
            logical_key="partial:1",
            payload={"cumulative_quantity": quantity},
            decision_id="DEC-future",
            attempt_id="ATT-future",
        ),
        _event(
            EventType.ORDER_FILLED,
            minute=4,
            logical_key="fill:1",
            payload={"cumulative_quantity": quantity},
            decision_id="DEC-future",
            attempt_id="ATT-future",
        ),
        _event(
            EventType.RECONCILIATION_STARTED,
            minute=5,
            logical_key="reconcile-start:1",
            payload={},
            attempt_id="ATT-future",
        ),
        _event(
            EventType.RECONCILIATION_CONFIRMED,
            minute=6,
            logical_key="reconcile-confirm:1",
            payload={},
            attempt_id="ATT-future",
        ),
        _event(
            EventType.POSITION_OPENED,
            minute=7,
            logical_key="position-open:1",
            payload={
                "position_id": "POS-future",
                "before_quantity": decimal_evidence(
                    "0",
                    DecimalFidelity.CANONICAL_DECIMAL_EXACT,
                ),
                "after_quantity": quantity,
            },
            attempt_id="ATT-future",
        ),
        _event(
            EventType.STOP_REQUESTED,
            minute=8,
            logical_key="stop-request:1",
            payload={"position_id": "POS-future", "stop_id": "STOP-future"},
        ),
        _event(
            EventType.STOP_ACTIVE,
            minute=9,
            logical_key="stop-active:1",
            payload={"position_id": "POS-future", "stop_id": "STOP-future"},
        ),
    ]


def test_canonical_decimal_timestamp_json_digest_and_numeric_lexeme() -> None:
    parsed = parse_json_bytes(b'{"n":1.2300,"text":"1.2300"}', label="fixture")
    assert isinstance(parsed["n"], NumericLexeme)
    assert parsed["n"] == "1.2300"
    evidence = decimal_evidence(parsed["n"], DecimalFidelity.LEGACY_ROUNDED_4DP)
    assert evidence == {
        "canonical": "1.23",
        "source_text": "1.2300",
        "fidelity": "LEGACY_ROUNDED_4DP",
    }
    assert canonical_timestamp("2026-07-23T10:00:00+03:00") == CAPTURED_AT
    left = {"b": ["x", {"y": "2"}], "a": "1"}
    right = {"a": "1", "b": ["x", {"y": "2"}]}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_digest(left) == canonical_digest(right)
    assert stable_id("DEC", left) == stable_id("DEC", right)
    with pytest.raises(DemoDecisionBridgeError, match="binary floats"):
        canonical_json({"not_exact": 1.25})


def test_sanitized_current_fixture_projects_one_incomplete_open_episode_and_no_outcome(
    tmp_path: Path,
) -> None:
    result, _ = _run(tmp_path)
    projection = result.projection
    assert projection["projection_status"] == "OPEN_LEGACY_LIMITED"
    assert projection["snapshot_consistency"] == "BEST_EFFORT_MULTI_FILE"
    assert projection["client_idempotency"] == "LEGACY_NO_CLIENT_IDEMPOTENCY"
    assert projection["realized_outcomes"] == []
    assert projection["realized_outcome_count"] == 0
    episodes = projection["episodes"]
    assert isinstance(episodes, list) and len(episodes) == 1
    assert episodes[0]["state"] == "OPEN_INCOMPLETE"
    assert episodes[0]["realized_outcomes"] == []
    assert projection["wallet_balance_exported"] is False


def test_first_generation_commits_canonical_sources_baseline_manifest_and_current(
    tmp_path: Path,
) -> None:
    result, _ = _run(tmp_path)
    output = _output_dir(result)
    generation = _current_generation_dir(output)
    manifest = json.loads((generation / "manifest.json").read_text(encoding="utf-8"))
    baseline = json.loads((generation / "baseline.json").read_text(encoding="utf-8"))
    expected_kinds = ["heartbeat", "lane_state", "orders"]
    assert [ref["kind"] for ref in result.projection["source_refs"]] == expected_kinds
    assert result.projection["source_refs"] == baseline["source_refs"]
    assert baseline["source_refs"] == manifest["source_refs"]
    assert manifest["baseline"]["baseline_id"] == baseline["baseline_id"]
    assert set(path.name for path in generation.iterdir()) == {
        "baseline.json",
        "events.jsonl",
        "projection.json",
        "export.jsonl",
        "manifest.json",
    }
    current = json.loads((output / "CURRENT.json").read_text(encoding="utf-8"))
    assert current["generation_id"] == generation.name


def test_legacy_rounded_deltas_are_never_exact_pnl() -> None:
    lane = {"lane_base": "0.1", "entry_price": "2"}
    heartbeat = {"at": CAPTURED_AT, "mark_price": "3"}
    orders = [
        {
            "recorded_at": ORDER_AT,
            "side": "Buy",
            "reconcile": {
                "ETH_delta": NumericLexeme("0.12345678"),
                "USDT_delta": NumericLexeme("-25.0000"),
            },
        }
    ]
    projection, _ = build_legacy_projection(
        lane,
        heartbeat,
        orders,
        source_refs=[
            {**SOURCE_REF, "kind": "lane_state"},
            {**SOURCE_REF, "kind": "heartbeat"},
            {**SOURCE_REF, "kind": "orders"},
        ],
        captured_at=CAPTURED_AT,
    )
    attempt = projection["episodes"][0]["attempts"][0]
    deltas = attempt["legacy_reconciliation_deltas"]
    assert deltas["ETH_delta"]["fidelity"] == "LEGACY_ROUNDED_8DP"
    assert deltas["USDT_delta"]["fidelity"] == "LEGACY_ROUNDED_4DP"
    assert attempt["pnl_eligibility"] == "INELIGIBLE_ROUNDED_LEGACY_DELTAS"
    assert projection["realized_outcomes"] == []


@pytest.mark.parametrize("disposition", BAR_DISPOSITIONS)
def test_reducer_accepts_the_complete_bar_disposition_vocabulary(disposition: str) -> None:
    event = _event(
        EventType.BAR_EVALUATED,
        minute=0,
        logical_key=f"bar:{disposition}",
        payload={"disposition": disposition},
        decision_id=f"DEC-{disposition}",
    )
    state = reduce_events([event])
    assert state["decisions"] == {f"DEC-{disposition}": disposition}


def test_reducer_validates_attempt_reconciliation_position_and_stop_lifecycle() -> None:
    state = reduce_events(_future_lifecycle())
    assert state["attempts"] == {"ATT-future": "FILLED"}
    assert state["reconciliation"] == {"ATT-future": "CONFIRMED"}
    assert state["positions"] == {"POS-future": "OPEN"}
    assert state["stops"] == {"STOP-future": "ACTIVE"}


def test_partial_fill_cancel_reconciles_actual_quantity_and_attempt_is_consumed_once() -> None:
    lifecycle = _future_lifecycle()
    cancel = _event(
        EventType.ORDER_CANCELLED,
        minute=4,
        logical_key="cancel-after-partial",
        payload={},
        decision_id="DEC-future",
        attempt_id="ATT-future",
    )
    opened = lifecycle[7]
    events = [*lifecycle[:4], cancel, lifecycle[5], lifecycle[6], opened]
    state = reduce_events(events)
    assert state["attempts"] == {"ATT-future": "CANCELLED_WITH_FILL_PENDING_RECONCILIATION"}
    assert state["executed_quantities"] == {"ATT-future": "1.25"}
    repeated_transition = _event(
        EventType.POSITION_OPENED,
        minute=8,
        logical_key="position-open-reused-attempt",
        payload=dict(opened["payload"]),
        attempt_id="ATT-future",
    )
    with pytest.raises(DemoDecisionBridgeError, match="only one position transition"):
        reduce_events([*events, repeated_transition])


def test_reducer_rejects_missing_reordered_conflicting_and_nonincreasing_partial_events() -> None:
    lifecycle = _future_lifecycle()
    with pytest.raises(DemoDecisionBridgeError, match="missing its evaluated decision"):
        reduce_events([lifecycle[1]])
    reordered = [
        _event(
            EventType.BAR_EVALUATED,
            minute=2,
            logical_key="later",
            payload={"disposition": "NO_SIGNAL"},
            decision_id="DEC-later",
        ),
        _event(
            EventType.BAR_EVALUATED,
            minute=1,
            logical_key="earlier",
            payload={"disposition": "NO_SIGNAL"},
            decision_id="DEC-earlier",
        ),
    ]
    with pytest.raises(DemoDecisionBridgeError, match="reordered"):
        reduce_events(reordered)
    repeated = reduce_events([lifecycle[0], lifecycle[0]])
    assert repeated["event_count"] == 1
    conflict = _event(
        EventType.BAR_EVALUATED,
        minute=1,
        logical_key=str(lifecycle[0]["logical_key"]),
        payload={"disposition": "ERROR"},
        decision_id="DEC-other",
    )
    with pytest.raises(EvidenceConflictError):
        reduce_events([lifecycle[0], conflict])
    partial_again = _event(
        EventType.ORDER_PARTIALLY_FILLED,
        minute=4,
        logical_key="partial:2",
        payload={
            "cumulative_quantity": decimal_evidence("1.25", DecimalFidelity.CANONICAL_DECIMAL_EXACT)
        },
        decision_id="DEC-future",
        attempt_id="ATT-future",
    )
    with pytest.raises(DemoDecisionBridgeError, match="must increase"):
        reduce_events([*lifecycle[:4], partial_again])


def test_reducer_orders_fractional_timestamps_by_instant_not_text() -> None:
    later = make_event(
        EventType.BAR_EVALUATED,
        logical_key="fractional-later",
        occurred_at="2026-07-23T00:00:00.900000Z",
        source_ref=SOURCE_REF,
        payload={"disposition": "NO_SIGNAL"},
        decision_id="DEC-fractional-later",
    )
    earlier = make_event(
        EventType.BAR_EVALUATED,
        logical_key="whole-earlier",
        occurred_at="2026-07-23T00:00:00Z",
        source_ref=SOURCE_REF,
        payload={"disposition": "NO_SIGNAL"},
        decision_id="DEC-whole-earlier",
    )
    with pytest.raises(DemoDecisionBridgeError, match="reordered"):
        reduce_events([later, earlier])


@pytest.mark.parametrize(
    "disposition",
    [item for item in BAR_DISPOSITIONS if item not in {"ENTRY_SIGNAL", "EXIT_SIGNAL"}],
)
def test_non_execution_dispositions_cannot_create_order_attempts(disposition: str) -> None:
    bar = _event(
        EventType.BAR_EVALUATED,
        minute=0,
        logical_key=f"blocked-bar:{disposition}",
        payload={"disposition": disposition},
        decision_id="DEC-non-executable",
    )
    attempt = _event(
        EventType.ORDER_ATTEMPTED,
        minute=1,
        logical_key=f"blocked-attempt:{disposition}",
        payload={},
        decision_id="DEC-non-executable",
        attempt_id="ATT-non-executable",
    )
    with pytest.raises(DemoDecisionBridgeError, match="non-executable"):
        reduce_events([bar, attempt])


def test_decision_attempt_and_stop_position_identities_cannot_be_overwritten() -> None:
    lifecycle = _future_lifecycle()
    repeated_decision = _event(
        EventType.BAR_EVALUATED,
        minute=1,
        logical_key="bar:second-coordinate",
        payload={"disposition": "ENTRY_SIGNAL"},
        decision_id="DEC-future",
    )
    with pytest.raises(DemoDecisionBridgeError, match="decision_id"):
        reduce_events([lifecycle[0], repeated_decision])
    reused_attempt = _event(
        EventType.ORDER_ATTEMPTED,
        minute=2,
        logical_key="attempt:reuse",
        payload={},
        decision_id="DEC-future",
        attempt_id="ATT-future",
    )
    with pytest.raises(DemoDecisionBridgeError, match="attempt_id"):
        reduce_events([*lifecycle[:2], reused_attempt])
    mismatched_stop = _event(
        EventType.STOP_ACTIVE,
        minute=10,
        logical_key="stop:wrong-position",
        payload={"position_id": "POS-other", "stop_id": "STOP-future"},
    )
    with pytest.raises(DemoDecisionBridgeError, match="do not match"):
        reduce_events([*_future_lifecycle(), mismatched_stop])
    premature_reconciliation = _event(
        EventType.RECONCILIATION_STARTED,
        minute=4,
        logical_key="reconcile:partial",
        payload={},
        attempt_id="ATT-future",
    )
    with pytest.raises(DemoDecisionBridgeError, match="predecessor"):
        reduce_events([*_future_lifecycle()[:4], premature_reconciliation])


def test_position_close_requires_exit_reconciliation_and_terminal_associated_stop() -> None:
    quantity = decimal_evidence("1.25", DecimalFidelity.CANONICAL_DECIMAL_EXACT)
    zero = decimal_evidence("0", DecimalFidelity.CANONICAL_DECIMAL_EXACT)
    exit_events = [
        _event(
            EventType.BAR_EVALUATED,
            minute=10,
            logical_key="exit-bar",
            payload={"disposition": "EXIT_SIGNAL"},
            decision_id="DEC-exit",
        ),
        _event(
            EventType.ORDER_ATTEMPTED,
            minute=11,
            logical_key="exit-attempt",
            payload={},
            decision_id="DEC-exit",
            attempt_id="ATT-exit",
        ),
        _event(
            EventType.ORDER_ACKNOWLEDGED,
            minute=12,
            logical_key="exit-ack",
            payload={},
            decision_id="DEC-exit",
            attempt_id="ATT-exit",
        ),
        _event(
            EventType.ORDER_FILLED,
            minute=13,
            logical_key="exit-fill",
            payload={"cumulative_quantity": quantity},
            decision_id="DEC-exit",
            attempt_id="ATT-exit",
        ),
        _event(
            EventType.RECONCILIATION_STARTED,
            minute=14,
            logical_key="exit-reconcile-start",
            payload={},
            attempt_id="ATT-exit",
        ),
        _event(
            EventType.RECONCILIATION_CONFIRMED,
            minute=15,
            logical_key="exit-reconcile-confirm",
            payload={},
            attempt_id="ATT-exit",
        ),
    ]
    close = _event(
        EventType.POSITION_CLOSED,
        minute=17,
        logical_key="position-close",
        payload={
            "position_id": "POS-future",
            "before_quantity": quantity,
            "after_quantity": zero,
        },
        attempt_id="ATT-exit",
    )
    pending = reduce_events([*_future_lifecycle(), *exit_events, close])
    assert pending["positions"] == {"POS-future": "CLOSED_PENDING_STOP_TERMINATION"}
    cancel = _event(
        EventType.STOP_CANCELLED,
        minute=16,
        logical_key="stop-cancel",
        payload={"position_id": "POS-future", "stop_id": "STOP-future"},
    )
    state = reduce_events([*_future_lifecycle(), *exit_events, cancel, close])
    assert state["positions"] == {"POS-future": "CLOSED"}
    assert state["stops"] == {"STOP-future": "CANCELLED"}


def test_replay_is_idempotent_and_export_is_canonical(tmp_path: Path) -> None:
    first, paths = _run(tmp_path)
    replay = run_bridge(
        lane_state_path=paths[0],
        heartbeat_path=paths[1],
        orders_path=paths[2],
        output_dir=tmp_path / "artifacts/evidence/demo-decision-stage-a",
        source_label="operator-copy-20260723",
        captured_at=CAPTURED_AT,
        repo_root=tmp_path,
    )
    assert first.export_sha256 == replay.export_sha256
    assert replay.appended_event_count == 0
    assert canonical_jsonl(first.events) == first.export_path.read_bytes()


def test_source_progress_detects_mutation_and_truncation() -> None:
    prior = {"byte_count": 3, "sha256": hashlib.sha256(b"abc").hexdigest()}
    assert validate_source_progress(prior, b"abcd") is None
    assert validate_source_progress(prior, b"abd") == "SOURCE_MUTATION"
    assert validate_source_progress(prior, b"ab") == "SOURCE_TRUNCATION"


def test_source_label_change_cannot_reset_private_history(tmp_path: Path) -> None:
    _, paths = _run(tmp_path)
    with pytest.raises(DemoDecisionBridgeError, match="different source label"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=tmp_path / "artifacts/evidence/demo-decision-stage-a",
            source_label="changed-label",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )


def test_missing_legacy_order_time_is_capture_independent_and_explicitly_unknown() -> None:
    order = {"side": "Buy", "avg_price": "2", "order_id": "raw"}
    refs = [
        {**SOURCE_REF, "kind": "lane_state", "label": "stable.lane_state"},
        {**SOURCE_REF, "kind": "heartbeat", "label": "stable.heartbeat"},
        {**SOURCE_REF, "kind": "orders", "label": "stable.orders"},
    ]
    _, first = build_legacy_projection(
        {"lane_base": "1"},
        {},
        [order],
        source_refs=refs,
        captured_at="2026-07-23T00:00:00Z",
        source_label="stable",
    )
    _, second = build_legacy_projection(
        {"lane_base": "1"},
        {},
        [order],
        source_refs=refs,
        captured_at="2026-07-24T00:00:00Z",
        source_label="stable",
    )
    assert first[0] == second[0]
    assert first[0]["occurred_at"]["status"] == "SOURCE_UNKNOWN"
    assert first[0]["occurred_at"]["canonical"] is None


def test_same_capture_source_mutation_and_orders_truncation_halt_projection(
    tmp_path: Path,
) -> None:
    _, paths = _run(tmp_path)
    paths[0].write_text('{"entry_price":"2","lane_base":"0.02"}\n', encoding="utf-8")
    with pytest.raises(SourceIncidentError, match="SOURCE_MUTATION"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=tmp_path / "artifacts/evidence/demo-decision-stage-a",
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )
    other = tmp_path / "other"
    _, other_paths = _run(other)
    other_paths[2].write_bytes(b"")
    with pytest.raises(SourceIncidentError, match="SOURCE_TRUNCATION"):
        run_bridge(
            lane_state_path=other_paths[0],
            heartbeat_path=other_paths[1],
            orders_path=other_paths[2],
            output_dir=other / "artifacts/evidence/demo-decision-stage-a",
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=other,
        )


def test_crash_after_durable_append_before_checkpoint_replays_safely(tmp_path: Path) -> None:
    def crash() -> None:
        raise RuntimeError("injected checkpoint crash")

    with pytest.raises(RuntimeError, match="injected"):
        _run(tmp_path, before_checkpoint=crash)
    output = tmp_path / "artifacts/evidence/demo-decision-stage-a"
    pending = list((output / "generations").iterdir())
    assert len(pending) == 1
    assert (pending[0] / "events.jsonl").is_file()
    assert not (output / "CURRENT.json").exists()
    paths = (
        tmp_path / "operator-copied/lane_state.json",
        tmp_path / "operator-copied/heartbeat.json",
        tmp_path / "operator-copied/orders.jsonl",
    )
    replay = run_bridge(
        lane_state_path=paths[0],
        heartbeat_path=paths[1],
        orders_path=paths[2],
        output_dir=output,
        source_label="operator-copy-20260723",
        captured_at=CAPTURED_AT,
        repo_root=tmp_path,
    )
    assert replay.appended_event_count == 0
    assert (output / "CURRENT.json").is_file()


def test_crash_baseline_detects_mutated_and_truncated_retry_sources(
    tmp_path: Path,
) -> None:
    def crash() -> None:
        raise RuntimeError("injected checkpoint crash")

    mutated = tmp_path / "mutated"
    with pytest.raises(RuntimeError, match="injected"):
        _run(mutated, before_checkpoint=crash)
    mutated_paths = (
        mutated / "operator-copied/lane_state.json",
        mutated / "operator-copied/heartbeat.json",
        mutated / "operator-copied/orders.jsonl",
    )
    mutated_paths[0].write_text(
        '{"entry_price":"2","lane_base":"0.02"}\n',
        encoding="utf-8",
    )
    with pytest.raises(SourceIncidentError, match="SOURCE_MUTATION") as mutation:
        run_bridge(
            lane_state_path=mutated_paths[0],
            heartbeat_path=mutated_paths[1],
            orders_path=mutated_paths[2],
            output_dir=mutated / "artifacts/evidence/demo-decision-stage-a",
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=mutated,
        )
    assert mutation.value.incident_type == "SOURCE_MUTATION"
    assert mutation.value.event["event_type"] == "SOURCE_MUTATION"

    truncated = tmp_path / "truncated"
    with pytest.raises(RuntimeError, match="injected"):
        _run(truncated, before_checkpoint=crash)
    truncated_paths = (
        truncated / "operator-copied/lane_state.json",
        truncated / "operator-copied/heartbeat.json",
        truncated / "operator-copied/orders.jsonl",
    )
    truncated_paths[2].write_bytes(b"")
    with pytest.raises(SourceIncidentError, match="SOURCE_TRUNCATION") as truncation:
        run_bridge(
            lane_state_path=truncated_paths[0],
            heartbeat_path=truncated_paths[1],
            orders_path=truncated_paths[2],
            output_dir=truncated / "artifacts/evidence/demo-decision-stage-a",
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=truncated,
        )
    assert truncation.value.incident_type == "SOURCE_TRUNCATION"
    assert truncation.value.event["event_type"] == "SOURCE_TRUNCATION"


def test_generation_aware_recovery_preserves_committed_a_and_finishes_b(
    tmp_path: Path,
) -> None:
    first, paths = _run(tmp_path)
    output = _output_dir(first)
    current_a = (output / "CURRENT.json").read_bytes()
    generation_a = _current_generation_dir(output)
    projection_a = (generation_a / "projection.json").read_bytes()

    def crash() -> None:
        raise RuntimeError("generation B crash")

    captured_b = "2026-07-23T08:00:00Z"
    with pytest.raises(RuntimeError, match="generation B"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=captured_b,
            repo_root=tmp_path,
            before_checkpoint=crash,
        )
    assert (output / "CURRENT.json").read_bytes() == current_a
    assert (generation_a / "projection.json").read_bytes() == projection_a
    assert len(list((output / "generations").iterdir())) == 2

    recovered = run_bridge(
        lane_state_path=paths[0],
        heartbeat_path=paths[1],
        orders_path=paths[2],
        output_dir=output,
        source_label="operator-copy-20260723",
        captured_at=captured_b,
        repo_root=tmp_path,
    )
    assert recovered.appended_event_count == 0
    assert (output / "CURRENT.json").read_bytes() != current_a
    assert _current_generation_dir(output) != generation_a
    assert (generation_a / "projection.json").read_bytes() == projection_a


def test_precommit_verification_failure_never_advances_current(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, paths = _run(tmp_path)
    output = _output_dir(first)
    retained_current = (output / "CURRENT.json").read_bytes()
    committed_generation = _current_generation_dir(output).name
    real_verify = bridge._verify_generation_manifest

    def reject_new_generation(manifest, *args, **kwargs):  # type: ignore[no-untyped-def]
        if manifest["generation_id"] != committed_generation:
            raise DemoDecisionBridgeError("injected precommit verification failure")
        return real_verify(manifest, *args, **kwargs)

    monkeypatch.setattr(bridge, "_verify_generation_manifest", reject_new_generation)
    with pytest.raises(DemoDecisionBridgeError, match="injected precommit"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=tmp_path,
        )
    assert (output / "CURRENT.json").read_bytes() == retained_current


@pytest.mark.parametrize(
    "fault_hook",
    ["after_generation_verified", "before_current_replace"],
)
def test_unreferenced_final_generation_is_verified_and_adopted_after_retry(
    tmp_path: Path,
    fault_hook: str,
) -> None:
    first, paths = _run(tmp_path)
    output = _output_dir(first)
    retained_current = (output / "CURRENT.json").read_bytes()

    def crash() -> None:
        raise RuntimeError(f"crash at {fault_hook}")

    hooks = {fault_hook: crash}
    with pytest.raises(RuntimeError, match="crash at"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=tmp_path,
            **hooks,
        )
    assert (output / "CURRENT.json").read_bytes() == retained_current
    pending = [
        path
        for path in (output / "generations").iterdir()
        if path != _current_generation_dir(output)
    ]
    assert len(pending) == 1
    assert set(path.name for path in pending[0].iterdir()) == {
        "baseline.json",
        "events.jsonl",
        "projection.json",
        "export.jsonl",
        "manifest.json",
    }

    adopted = run_bridge(
        lane_state_path=paths[0],
        heartbeat_path=paths[1],
        orders_path=paths[2],
        output_dir=output,
        source_label="operator-copy-20260723",
        captured_at="2026-07-23T08:00:00Z",
        repo_root=tmp_path,
    )
    assert adopted.appended_event_count == 0
    assert (output / "CURRENT.json").read_bytes() != retained_current


@pytest.mark.parametrize("replacement_fault", ["before_replace", "after_replace"])
def test_current_replacement_interruption_recovers_or_replays_committed_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement_fault: str,
) -> None:
    first, paths = _run(tmp_path)
    output = _output_dir(first)
    retained_current = (output / "CURRENT.json").read_bytes()
    real_write = bridge._safe_write_atomic

    def interrupt_current(path, payload, *, create_only=False):  # type: ignore[no-untyped-def]
        if path.name == "CURRENT.json":
            if replacement_fault == "before_replace":
                temporary = path.with_name(".CURRENT.json.tmp-888888")
                descriptor = os.open(
                    temporary,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                os.write(descriptor, payload[: max(1, len(payload) // 2)])
                os.fsync(descriptor)
                os.close(descriptor)
            else:
                real_write(path, payload, create_only=create_only)
            raise RuntimeError(f"{replacement_fault} interruption")
        return real_write(path, payload, create_only=create_only)

    monkeypatch.setattr(bridge, "_safe_write_atomic", interrupt_current)
    with pytest.raises(RuntimeError, match="interruption"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=tmp_path,
        )
    if replacement_fault == "before_replace":
        assert (output / "CURRENT.json").read_bytes() == retained_current
    else:
        assert (output / "CURRENT.json").read_bytes() != retained_current

    monkeypatch.setattr(bridge, "_safe_write_atomic", real_write)
    recovered = run_bridge(
        lane_state_path=paths[0],
        heartbeat_path=paths[1],
        orders_path=paths[2],
        output_dir=output,
        source_label="operator-copy-20260723",
        captured_at="2026-07-23T08:00:00Z",
        repo_root=tmp_path,
    )
    assert recovered.appended_event_count == 0
    assert (output / "CURRENT.json").read_bytes() != retained_current


@pytest.mark.parametrize("interrupted_name", ["baseline.json", "events.jsonl"])
def test_interrupted_atomic_generation_writes_leave_current_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted_name: str,
) -> None:
    first, paths = _run(tmp_path)
    output = _output_dir(first)
    retained_current = (output / "CURRENT.json").read_bytes()
    real_write = bridge._safe_write_atomic

    def interrupt(path, payload, *, create_only=False):  # type: ignore[no-untyped-def]
        if path.name == interrupted_name:
            temporary = path.with_name(f".{path.name}.tmp-999999")
            descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(descriptor, payload[: max(1, len(payload) // 2)])
            os.fsync(descriptor)
            os.close(descriptor)
            raise RuntimeError(f"interrupted {interrupted_name}")
        return real_write(path, payload, create_only=create_only)

    monkeypatch.setattr(bridge, "_safe_write_atomic", interrupt)
    with pytest.raises(RuntimeError, match="interrupted"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=tmp_path,
        )
    assert (output / "CURRENT.json").read_bytes() == retained_current
    monkeypatch.setattr(bridge, "_safe_write_atomic", real_write)
    recovered = run_bridge(
        lane_state_path=paths[0],
        heartbeat_path=paths[1],
        orders_path=paths[2],
        output_dir=output,
        source_label="operator-copy-20260723",
        captured_at="2026-07-23T08:00:00Z",
        repo_root=tmp_path,
    )
    assert recovered.appended_event_count >= 0
    assert (output / "CURRENT.json").read_bytes() != retained_current


def test_extra_or_temporary_generation_files_fail_closed(
    tmp_path: Path,
) -> None:
    committed_root = tmp_path / "committed"
    committed, committed_paths = _run(committed_root)
    committed_output = _output_dir(committed)
    extra = _current_generation_dir(committed_output) / "unexpected.bin"
    extra.write_bytes(b"unexpected")
    os.chmod(extra, 0o600)
    with pytest.raises(DemoDecisionBridgeError, match="extra, temporary"):
        run_bridge(
            lane_state_path=committed_paths[0],
            heartbeat_path=committed_paths[1],
            orders_path=committed_paths[2],
            output_dir=committed_output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=committed_root,
        )

    pending_root = tmp_path / "pending"
    first, pending_paths = _run(pending_root)
    pending_output = _output_dir(first)

    def crash() -> None:
        raise RuntimeError("pending crash")

    with pytest.raises(RuntimeError, match="pending crash"):
        run_bridge(
            lane_state_path=pending_paths[0],
            heartbeat_path=pending_paths[1],
            orders_path=pending_paths[2],
            output_dir=pending_output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=pending_root,
            before_checkpoint=crash,
        )
    pending_generation = next(
        path
        for path in (pending_output / "generations").iterdir()
        if path != _current_generation_dir(pending_output)
    )
    temporary = pending_generation / ".projection.json.tmp-interrupted"
    temporary.write_bytes(b"partial")
    os.chmod(temporary, 0o600)
    with pytest.raises(DemoDecisionBridgeError, match="extra, temporary"):
        run_bridge(
            lane_state_path=pending_paths[0],
            heartbeat_path=pending_paths[1],
            orders_path=pending_paths[2],
            output_dir=pending_output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=pending_root,
        )


def test_initial_and_mid_prefix_sqlite_interruptions_recover_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial = tmp_path / "initial"
    initial_paths = _write_copied_fixture(initial)
    initial_output = initial / "artifacts/evidence/demo-decision-stage-a"
    real_append = bridge._append_store
    initial_calls = 0

    def interrupt_initial(store, event, recorded_at):  # type: ignore[no-untyped-def]
        nonlocal initial_calls
        real_append(store, event, recorded_at)
        initial_calls += 1
        if initial_calls == 1:
            raise RuntimeError("initial sqlite interruption")

    monkeypatch.setattr(bridge, "_append_store", interrupt_initial)
    with pytest.raises(RuntimeError, match="initial sqlite"):
        run_bridge(
            lane_state_path=initial_paths[0],
            heartbeat_path=initial_paths[1],
            orders_path=initial_paths[2],
            output_dir=initial_output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=initial,
        )
    assert not (initial_output / "CURRENT.json").exists()
    monkeypatch.setattr(bridge, "_append_store", real_append)
    recovered_initial = run_bridge(
        lane_state_path=initial_paths[0],
        heartbeat_path=initial_paths[1],
        orders_path=initial_paths[2],
        output_dir=initial_output,
        source_label="operator-copy-20260723",
        captured_at=CAPTURED_AT,
        repo_root=initial,
    )
    assert (initial_output / "CURRENT.json").is_file()
    assert recovered_initial.appended_event_count == len(recovered_initial.events) - 1

    prefix = tmp_path / "prefix"
    first, prefix_paths = _run(prefix)
    prefix_output = _output_dir(first)
    retained_current = (prefix_output / "CURRENT.json").read_bytes()
    with prefix_paths[2].open("ab") as handle:
        handle.write(
            b'{"avg_price":"1901","cum_exec_qty":"0.01","order_id":"new-order",'
            b'"recorded_at":"2026-07-23T07:30:00Z","side":"Sell"}\n'
        )
    prefix_calls = 0

    def interrupt_prefix(store, event, recorded_at):  # type: ignore[no-untyped-def]
        nonlocal prefix_calls
        real_append(store, event, recorded_at)
        prefix_calls += 1
        if prefix_calls == 1:
            raise RuntimeError("mid-prefix interruption")

    monkeypatch.setattr(bridge, "_append_store", interrupt_prefix)
    with pytest.raises(RuntimeError, match="mid-prefix"):
        run_bridge(
            lane_state_path=prefix_paths[0],
            heartbeat_path=prefix_paths[1],
            orders_path=prefix_paths[2],
            output_dir=prefix_output,
            source_label="operator-copy-20260723",
            captured_at="2026-07-23T08:00:00Z",
            repo_root=prefix,
        )
    assert (prefix_output / "CURRENT.json").read_bytes() == retained_current
    monkeypatch.setattr(bridge, "_append_store", real_append)
    recovered_prefix = run_bridge(
        lane_state_path=prefix_paths[0],
        heartbeat_path=prefix_paths[1],
        orders_path=prefix_paths[2],
        output_dir=prefix_output,
        source_label="operator-copy-20260723",
        captured_at="2026-07-23T08:00:00Z",
        repo_root=prefix,
    )
    assert recovered_prefix.appended_event_count == 1
    assert (prefix_output / "CURRENT.json").read_bytes() != retained_current


@pytest.mark.parametrize(
    "payload",
    [
        {"api_key": "not-allowed"},
        {"password": "not-allowed"},
        {"passphrase": "not-allowed"},
        {"access_token": "not-allowed"},
        {"refreshToken": "not-allowed"},
        {"session_id": "not-allowed"},
        {"cookie": "not-allowed"},
        {"nested": {"request_headers": {"x": "y"}}},
        {"value": "Bearer abcdef0123456789"},
        {"value": "password=hunter2"},
        {"value": "access_token=opaque-token"},
        {"value": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature"},
        {"value": "https://example.test/x?signature=raw"},
        {"value": 1.5},
    ],
)
def test_security_rejects_forbidden_keys_secret_like_values_and_floats(
    payload: Mapping[str, object],
) -> None:
    with pytest.raises(DemoDecisionBridgeError):
        validate_no_secrets(payload)


@pytest.mark.parametrize(
    "provider_token",
    [
        "".join(("s", "k", "-", "1234567890abcdef")),
        "".join(("g", "h", "p", "_", "1234567890abcdef")),
        "".join(("github", "_pat_", "1234567890_abcdef")),
        "".join(("xox", "b-", "1234567890-abcdef")),
        "".join(("xox", "p-", "1234567890-abcdef")),
        "".join(("s", "k", "_live_", "1234567890abcdef")),
        "".join(("gl", "pat-", "1234567890abcdef")),
        "".join(("AI", "za", "1234567890abcdefghijklmnop")),
    ],
)
def test_security_rejects_provider_tokens_under_neutral_keys(
    provider_token: str,
) -> None:
    with pytest.raises(DemoDecisionBridgeError, match="secret-like value"):
        validate_no_secrets({"value": provider_token})


def test_security_rejects_active_symlink_hardlink_and_output_escape(tmp_path: Path) -> None:
    lane_state, heartbeat, orders = _write_copied_fixture(tmp_path)
    active = tmp_path / "artifacts/trading_domain/demo_lane"
    active.mkdir(parents=True)
    active_state = active / "lane_state.json"
    active_state.write_text("{}", encoding="utf-8")
    with pytest.raises(DemoDecisionBridgeError, match="active demo-lane"):
        run_bridge(
            lane_state_path=active_state,
            heartbeat_path=heartbeat,
            orders_path=orders,
            output_dir=tmp_path / "artifacts/evidence/active-reject",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )
    symlink = tmp_path / "operator-copied/symlink.json"
    symlink.symlink_to(lane_state)
    with pytest.raises(DemoDecisionBridgeError, match="symlink"):
        run_bridge(
            lane_state_path=symlink,
            heartbeat_path=heartbeat,
            orders_path=orders,
            output_dir=tmp_path / "artifacts/evidence/symlink-reject",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )
    hardlink = tmp_path / "operator-copied/hardlink.json"
    os.link(lane_state, hardlink)
    with pytest.raises(DemoDecisionBridgeError, match="single-link"):
        run_bridge(
            lane_state_path=hardlink,
            heartbeat_path=heartbeat,
            orders_path=orders,
            output_dir=tmp_path / "artifacts/evidence/hardlink-reject",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )
    hardlink.unlink()
    assert lane_state.stat().st_nlink == 1
    with pytest.raises(DemoDecisionBridgeError, match="artifacts/evidence"):
        run_bridge(
            lane_state_path=lane_state,
            heartbeat_path=heartbeat,
            orders_path=orders,
            output_dir=tmp_path / "escaped-output",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )


def test_security_rejects_symlinked_source_and_output_ancestors(tmp_path: Path) -> None:
    real = tmp_path / "real"
    lane_state, heartbeat, orders = _write_copied_fixture(real)
    source_alias = tmp_path / "source-alias"
    source_alias.symlink_to(real / "operator-copied", target_is_directory=True)
    with pytest.raises(DemoDecisionBridgeError, match="symlink ancestors"):
        run_bridge(
            lane_state_path=source_alias / lane_state.name,
            heartbeat_path=heartbeat,
            orders_path=orders,
            output_dir=tmp_path / "artifacts/evidence/source-ancestor",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )
    assert not (tmp_path / "artifacts").exists()
    actual_output_parent = tmp_path / "actual-output-parent"
    actual_output_parent.mkdir()
    output_alias = tmp_path / "artifacts"
    output_alias.symlink_to(actual_output_parent, target_is_directory=True)
    with pytest.raises(DemoDecisionBridgeError, match="symlink"):
        run_bridge(
            lane_state_path=lane_state,
            heartbeat_path=heartbeat,
            orders_path=orders,
            output_dir=output_alias / "evidence/bridge",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )


def test_malformed_optional_decimal_excessive_exponent_and_structure_fail_closed() -> None:
    refs = [
        {**SOURCE_REF, "kind": "lane_state"},
        {**SOURCE_REF, "kind": "heartbeat"},
        {**SOURCE_REF, "kind": "orders"},
    ]
    with pytest.raises(DemoDecisionBridgeError, match="avg_price"):
        build_legacy_projection(
            {"lane_base": "1"},
            {},
            [{"side": "Buy", "avg_price": "not-a-number"}],
            source_refs=refs,
            captured_at=CAPTURED_AT,
        )
    with pytest.raises(DemoDecisionBridgeError, match="exponent"):
        decimal_evidence("1e1000", DecimalFidelity.UNKNOWN_PRECISION)
    nested: object = "leaf"
    for _ in range(20):
        nested = {"x": nested}
    with pytest.raises(DemoDecisionBridgeError, match="depth"):
        canonical_json(nested)
    with pytest.raises(DemoDecisionBridgeError, match="too long"):
        canonical_json({"x": "a" * 5000})


@pytest.mark.parametrize(
    ("lane", "heartbeat", "orders", "message"),
    [
        (
            {"lane_base": "1"},
            {},
            [{"recorded_at": 7, "side": "Buy"}],
            "recorded_at",
        ),
        (
            {"lane_base": "1"},
            {},
            [{"side": "Buy", "reconcile": "not-an-object"}],
            "reconcile",
        ),
        (
            {"lane_base": "1", "resting_stop": "not-an-object"},
            {},
            [],
            "resting_stop",
        ),
    ],
)
def test_present_but_malformed_legacy_fields_fail_closed(
    lane: Mapping[str, object],
    heartbeat: Mapping[str, object],
    orders: list[Mapping[str, object]],
    message: str,
) -> None:
    refs = [
        {**SOURCE_REF, "kind": "lane_state"},
        {**SOURCE_REF, "kind": "heartbeat"},
        {**SOURCE_REF, "kind": "orders"},
    ]
    with pytest.raises(DemoDecisionBridgeError, match=message):
        build_legacy_projection(
            lane,
            heartbeat,
            orders,
            source_refs=refs,
            captured_at=CAPTURED_AT,
        )


def test_cross_field_event_and_projection_identities_are_recomputed() -> None:
    projection, events = build_legacy_projection(
        {"lane_base": "1"},
        {},
        [{"recorded_at": ORDER_AT, "side": "Buy"}],
        source_refs=[
            {**SOURCE_REF, "kind": "lane_state"},
            {**SOURCE_REF, "kind": "heartbeat"},
            {**SOURCE_REF, "kind": "orders"},
        ],
        captured_at=CAPTURED_AT,
    )
    legacy_event = dict(events[0])
    legacy_payload = dict(legacy_event["payload"])
    legacy_payload["attempt_id"] = "ATT-different"
    legacy_event["payload"] = legacy_payload
    with pytest.raises(DemoDecisionBridgeError, match="payload identity"):
        validate_event(legacy_event)

    projection["projection_id"] = "PRJ-different"
    with pytest.raises(DemoDecisionBridgeError, match="fixed projection seed"):
        validate_projection(projection)

    incident = make_event(
        EventType.SOURCE_MUTATION,
        logical_key="incident:identity",
        occurred_at=CAPTURED_AT,
        source_ref=SOURCE_REF,
        payload={
            "source_kind": SOURCE_REF["kind"],
            "prior_sha256": "b" * 64,
            "prior_byte_count": 9,
            "current_sha256": "c" * 64,
            "current_byte_count": SOURCE_REF["byte_count"],
            "projection_halted": True,
        },
    )
    with pytest.raises(DemoDecisionBridgeError, match="source_ref"):
        validate_event(incident)


def test_copied_legacy_decimal_text_is_unknown_not_venue_attested() -> None:
    projection, _ = build_legacy_projection(
        {"lane_base": "0.1000", "entry_price": "2.00"},
        {},
        [],
        source_refs=[
            {**SOURCE_REF, "kind": "lane_state"},
            {**SOURCE_REF, "kind": "heartbeat"},
            {**SOURCE_REF, "kind": "orders"},
        ],
        captured_at=CAPTURED_AT,
    )
    episode = projection["episodes"][0]
    assert episode["position_base"]["fidelity"] == "UNKNOWN_PRECISION"
    assert episode["entry_price"]["fidelity"] == "UNKNOWN_PRECISION"


def test_private_output_permissions_and_hardlink_detection(tmp_path: Path) -> None:
    result, _ = _run(tmp_path)
    output = _output_dir(result)
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE(result.export_path.parent.stat().st_mode) == 0o700
    for path in output.rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
    linked = tmp_path / "linked-events"
    os.link(_current_generation_dir(output) / "events.jsonl", linked)
    paths = (
        tmp_path / "operator-copied/lane_state.json",
        tmp_path / "operator-copied/heartbeat.json",
        tmp_path / "operator-copied/orders.jsonl",
    )
    with pytest.raises(DemoDecisionBridgeError, match="single-link"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )


def test_private_evidence_root_and_store_reject_unsafe_modes_and_links(
    tmp_path: Path,
) -> None:
    unsafe_root = tmp_path / "unsafe-root"
    paths = _write_copied_fixture(unsafe_root)
    evidence_root = unsafe_root / "artifacts/evidence"
    evidence_root.mkdir(parents=True, mode=0o755)
    os.chmod(evidence_root, 0o755)
    with pytest.raises(DemoDecisionBridgeError, match="0700"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=evidence_root / "bridge",
            source_label="copy",
            captured_at=CAPTURED_AT,
            repo_root=unsafe_root,
        )

    linked_root = tmp_path / "linked-store"
    result, linked_paths = _run(linked_root)
    output = _output_dir(result)
    os.link(output / "evidence.sqlite3", linked_root / "database-hardlink")
    with pytest.raises(DemoDecisionBridgeError, match="single-link"):
        run_bridge(
            lane_state_path=linked_paths[0],
            heartbeat_path=linked_paths[1],
            orders_path=linked_paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=linked_root,
        )

    symlinked_lock_root = tmp_path / "symlinked-lock"
    result, symlinked_paths = _run(symlinked_lock_root)
    output = _output_dir(result)
    lock_path = output / "evidence.sqlite3.lock"
    retained_lock = output / "retained-lock"
    lock_path.rename(retained_lock)
    lock_path.symlink_to(retained_lock)
    with pytest.raises(DemoDecisionBridgeError, match="symlink"):
        run_bridge(
            lane_state_path=symlinked_paths[0],
            heartbeat_path=symlinked_paths[1],
            orders_path=symlinked_paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=symlinked_lock_root,
        )


def test_checkpoint_and_persisted_store_bind_exact_identity(tmp_path: Path) -> None:
    result, paths = _run(tmp_path)
    output = _output_dir(result)
    connection = sqlite3.connect(output / "evidence.sqlite3")
    row = connection.execute(
        "SELECT record_type, stage, occurred_at, payload_json FROM evidence_events "
        "ORDER BY sequence LIMIT 1"
    ).fetchone()
    connection.close()
    assert row[0] == "DemoDecisionEvidenceEvent"
    assert row[1] == "S3_PAPER_DEMO"
    retained = json.loads(row[3])
    assert retained["record_type"] == row[0]
    assert retained["stage"] == row[1]
    assert retained["occurred_at"]["storage_timestamp"] == row[2].replace("+00:00", "Z")

    projection_path = _current_generation_dir(output) / "projection.json"
    projection_path.write_bytes(projection_path.read_bytes() + b" ")
    with pytest.raises(DemoDecisionBridgeError, match="binding failed"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=tmp_path,
        )


@pytest.mark.parametrize("tamper", ["corrupt", "delete", "extra"])
def test_generation_manifest_rejects_corrupt_missing_and_extra_store_rows(
    tmp_path: Path,
    tamper: str,
) -> None:
    root = tmp_path / tamper
    result, paths = _run(root)
    output = _output_dir(result)
    connection = sqlite3.connect(output / "evidence.sqlite3")
    if tamper == "corrupt":
        connection.execute("DROP TRIGGER evidence_no_update")
        connection.execute(
            "UPDATE evidence_events SET payload_sha256 = ? WHERE sequence = 1",
            ("f" * 64,),
        )
    elif tamper == "delete":
        connection.execute("DROP TRIGGER evidence_no_delete")
        connection.execute("DELETE FROM evidence_events WHERE sequence = 1")
    else:
        extra = make_event(
            EventType.BAR_EVALUATED,
            logical_key="tampered-extra-row",
            occurred_at=CAPTURED_AT,
            source_ref=SOURCE_REF,
            payload={"disposition": "NO_SIGNAL"},
            decision_id="DEC-tampered-extra",
        )
        payload_json = canonical_json(extra)
        connection.execute(
            """INSERT INTO evidence_events(
                   idempotency_key, record_id, record_type, stage, occurred_at,
                   recorded_at, payload_json, payload_sha256
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                extra["logical_key"],
                extra["event_id"],
                "DemoDecisionEvidenceEvent",
                "S3_PAPER_DEMO",
                "2026-07-23T07:00:00+00:00",
                "2026-07-23T07:00:00+00:00",
                payload_json,
                hashlib.sha256(payload_json.encode()).hexdigest(),
            ),
        )
    connection.commit()
    connection.close()

    with pytest.raises(DemoDecisionBridgeError):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=root,
        )


@pytest.mark.parametrize("schema_tamper", ["weaken", "extra"])
def test_fixed_sqlite_schema_contract_rejects_weakened_or_extra_schema(
    tmp_path: Path,
    schema_tamper: str,
) -> None:
    root = tmp_path / schema_tamper
    result, paths = _run(root)
    output = _output_dir(result)
    connection = sqlite3.connect(output / "evidence.sqlite3")
    if schema_tamper == "weaken":
        connection.execute("DROP TRIGGER evidence_no_update")
    else:
        connection.execute("CREATE INDEX unexpected_evidence_idx ON evidence_events(record_id)")
    connection.commit()
    connection.close()
    with pytest.raises(DemoDecisionBridgeError, match="fixed contract"):
        run_bridge(
            lane_state_path=paths[0],
            heartbeat_path=paths[1],
            orders_path=paths[2],
            output_dir=output,
            source_label="operator-copy-20260723",
            captured_at=CAPTURED_AT,
            repo_root=root,
        )


def test_deterministic_redacted_export_has_opaque_order_ids_and_no_wallet_balances(
    tmp_path: Path,
) -> None:
    first, _ = _run(tmp_path / "one")
    second, _ = _run(tmp_path / "two")
    first_bytes = first.export_path.read_bytes()
    assert first_bytes == second.export_path.read_bytes()
    assert b"venue-raw-123" not in first_bytes
    assert b"stop-raw-42" not in first_bytes
    assert b"12345.67" not in first_bytes
    assert b"VOH-" in first_bytes


def test_module_and_cli_have_no_network_order_transport_or_demo_runtime_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "src/tios/evidence/demo_decision_bridge.py",
        root / "scripts/build_demo_decision_evidence.py",
    ]
    forbidden_roots = {"urllib", "requests", "httpx", "websockets", "socket"}
    forbidden_modules = {
        "scripts.demo_eth_lane",
        "tios.services.dashboard_api.demo_lane",
        "tios.adapters",
    }
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not {item.split(".")[0] for item in imported} & forbidden_roots
        assert not imported & forbidden_modules


def test_cli_requires_every_path_and_rejects_active_demo_input(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.main([], repo_root=tmp_path)
    active = tmp_path / "artifacts/trading_domain/demo_lane"
    active.mkdir(parents=True)
    for name in ("lane_state.json", "heartbeat.json", "orders.jsonl"):
        (active / name).write_text("{}\n", encoding="utf-8")
    status = cli.main(
        [
            "--lane-state",
            str(active / "lane_state.json"),
            "--heartbeat",
            str(active / "heartbeat.json"),
            "--orders",
            str(active / "orders.jsonl"),
            "--output-dir",
            str(tmp_path / "artifacts/evidence/cli"),
            "--source-label",
            "copy",
            "--captured-at",
            CAPTURED_AT,
        ],
        repo_root=tmp_path,
    )
    assert status == 2
    assert "active demo-lane paths are forbidden" in capsys.readouterr().err
