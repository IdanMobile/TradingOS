from __future__ import annotations

import ast
import importlib.util
import json
import os
import stat
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import tios.evidence.demo_snapshot_adapter as adapter
from tios.evidence.demo_decision_bridge import (
    DemoDecisionBridgeError,
    build_legacy_projection,
    parse_json_bytes,
    parse_jsonl_bytes,
    run_bridge,
)
from tios.evidence.demo_snapshot_adapter import (
    DemoSnapshotError,
    capture_demo_snapshot,
    snapshot_venue_order_ref,
)

CAPTURED_AT = "2026-07-23T07:00:00Z"
_CLI_PATH = Path(__file__).resolve().parents[1] / "scripts/capture_demo_decision_snapshot.py"
_CLI_SPEC = importlib.util.spec_from_file_location("capture_demo_decision_snapshot", _CLI_PATH)
assert _CLI_SPEC is not None and _CLI_SPEC.loader is not None
cli = importlib.util.module_from_spec(_CLI_SPEC)
_CLI_SPEC.loader.exec_module(cli)


def _active_fixture(repo: Path) -> tuple[Path, Path, Path]:
    active = repo / "artifacts/trading_domain/demo_lane"
    active.mkdir(parents=True)
    state = active / "lane_state.json"
    heartbeat = active / "heartbeat.json"
    orders = active / "orders.jsonl"
    state.write_bytes(
        b'{"cursor":"2026-07-23T06:55:00Z","entry_price":"1862.3700",'
        b'"lane_base":0.0134103300,"resting_stop":{"base_qty":"0.01341",'
        b'"order_id":"raw-stop-42","position_base_qty":"0.01341033",'
        b'"price_tick":"0.01","risk_boundary_price":"1583.0145",'
        b'"risk_fraction":"0.15","state":"ACTIVE","trigger_price":"1583.02"},'
        b'"unknown":"drop-me"}\n'
    )
    heartbeat.write_bytes(
        b'{"action":"private free text","at":"2026-07-23T06:59:30Z",'
        b'"candidate":"ETHUSDT-5m","disaster_stop_event":{"private":"drop"},'
        b'"disaster_stop_price":"1","entry_price":"1862.3700",'
        b'"environment":"VENUE_DEMO","execution_authority_note":"drop",'
        b'"fresh_signals":1,"kill_switch":false,"lane_base":"0.0134103300",'
        b'"latest_closed_bar":"2026-07-23T06:55:00Z","mark_price":"1900.00",'
        b'"promotion_eligible":false,"real_money":false,'
        b'"resting_stop":{"base_qty":"0.013410","order_id":"raw-stop-42",'
        b'"position_base_qty":"0.013410330","price_tick":"0.010",'
        b'"risk_boundary_price":"1583.01450","risk_fraction":"0.150",'
        b'"state":"ACTIVE","trigger_price":"1583.020"},'
        b'"rule_levels":{"private":"drop"},"schema_version":"v1","signals_in_window":3,'
        b'"validation_state":"UNVALIDATED",'
        b'"wallet":{"ETH":"0.01341033","USDT":"12345.67"}}\n'
    )
    orders.write_bytes(
        b'{"avg_price":"1862.3700","cum_exec_qty":0.0134103300,'
        b'"environment":"VENUE_DEMO","execution_authority_note":"drop","fee":"0.00000420",'
        b'"ok":true,"order_id":"raw-order-123","order_status":"FILLED",'
        b'"promotion_eligible":false,"qty":"0.01341033","real_money":false,'
        b'"reason":"ENTRY_SIGNAL","reconcile":{"ETH_delta":0.0134103300,'
        b'"USDT_delta":-25.0000,"wallet_after":"drop"},'
        b'"recorded_at":"2026-07-23T06:59:00+00:00","schema_version":"v1",'
        b'"side":"Buy","signal_ref":"raw-signal-7","stage":"OBSERVED",'
        b'"symbol":"ETHUSDT","unit":"base","validation_state":"UNVALIDATED",'
        b'"wallet_after":{"ETH":"private"}}\n'
    )
    return state, heartbeat, orders


def _load_snapshot(result: adapter.DemoSnapshotResult) -> tuple[dict[str, object], ...]:
    state = parse_json_bytes(
        (result.snapshot_dir / "lane_state.json").read_bytes(), label="snapshot state"
    )
    heartbeat = parse_json_bytes(
        (result.snapshot_dir / "heartbeat.json").read_bytes(), label="snapshot heartbeat"
    )
    orders = parse_jsonl_bytes(
        (result.snapshot_dir / "orders.jsonl").read_bytes(), label="snapshot orders"
    )
    coverage = json.loads((result.snapshot_dir / "coverage.json").read_text(encoding="utf-8"))
    return state, heartbeat, *orders, coverage


def _failure_order(stage: str, *, index: int = 0) -> dict[str, object]:
    record: dict[str, object] = {
        "schema_version": "v1",
        "recorded_at": f"2026-07-23T06:58:{index:02d}Z",
        "symbol": "ETHUSDT",
        "side": "Buy",
        "unit": "base",
        "signal_ref": f"frame-{index}",
        "reason": "ENTRY_SIGNAL",
        "environment": "VENUE_DEMO",
        "real_money": False,
        "promotion_eligible": False,
        "validation_state": "UNVALIDATED",
        "ok": False,
        "stage": stage,
    }
    if stage in {"kill_switch", "place"}:
        record["qty"] = "0.01"
    if stage == "place":
        record["error"] = "https://demo.invalid/v5/order?message=refused"
    return record


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_capture_sanitizes_fixed_sources_and_emits_stage_a_ready_private_snapshot(
    tmp_path: Path,
) -> None:
    _active_fixture(tmp_path)
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    entries = {path.name for path in result.snapshot_dir.iterdir()}
    assert entries == {
        "lane_state.json",
        "heartbeat.json",
        "orders.jsonl",
        "coverage.json",
        "manifest.json",
    }
    assert stat.S_IMODE(result.snapshot_dir.stat().st_mode) == 0o700
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in result.snapshot_dir.iterdir())
    retained = b"".join(
        (result.snapshot_dir / name).read_bytes()
        for name in ("lane_state.json", "heartbeat.json", "orders.jsonl")
    )
    for forbidden in (
        b"raw-stop-42",
        b"raw-order-123",
        b"raw-signal-7",
        b"12345.67",
        b'"wallet"',
        b'"action"',
        b'"disaster_stop_event"',
        b'"disaster_stop_price"',
        b'"execution_authority_note"',
        b'"rule_levels"',
    ):
        assert forbidden not in retained
    assert b'"lane_base":0.0134103300' in (result.snapshot_dir / "lane_state.json").read_bytes()
    state, heartbeat, order, coverage = _load_snapshot(result)
    assert state["resting_stop"]["venue_order_ref"] == snapshot_venue_order_ref("raw-stop-42")
    assert heartbeat["resting_stop"]["venue_order_ref"] == snapshot_venue_order_ref("raw-stop-42")
    assert order["venue_order_ref"] == snapshot_venue_order_ref("raw-order-123")
    assert coverage["capture_status"] == "PASS"
    assert coverage["evidence_completeness"] == "PARTIAL_LEGACY_OPEN"
    assert coverage["stage_a_input_ready"] is True
    assert coverage["stage_a_commit_status"] == "NOT_RUN"
    assert coverage["realized_outcome_count"] == 0
    assert coverage["pnl_available"] is False
    assert coverage["strategy_evaluation_available"] is False
    assert coverage["execution_authority"] == "NONE"


@pytest.mark.parametrize(
    "stage",
    ["kill_switch", "price_unavailable", "qty_below_step", "place"],
)
def test_valid_no_venue_order_outcomes_retain_explicit_null_reference(
    tmp_path: Path,
    stage: str,
) -> None:
    paths = _active_fixture(tmp_path)
    _write_jsonl(paths[2], [_failure_order(stage)])
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    orders = parse_jsonl_bytes(
        (result.snapshot_dir / "orders.jsonl").read_bytes(),
        label="sanitized refusal orders",
    )
    assert len(orders) == 1
    assert orders[0]["ok"] is False
    assert orders[0]["stage"] == stage
    assert orders[0]["venue_order_ref"] is None
    if stage == "place":
        assert "error" not in orders[0]


def test_successful_or_created_order_requires_one_identity_and_both_are_rejected(
    tmp_path: Path,
) -> None:
    paths = _active_fixture(tmp_path)
    order = json.loads(paths[2].read_text(encoding="utf-8"))
    order.pop("order_id")
    _write_jsonl(paths[2], [order])
    with pytest.raises(DemoSnapshotError, match="requires order_id or venue_order_ref"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    order["order_id"] = "raw"
    order["venue_order_ref"] = snapshot_venue_order_ref("raw")
    _write_jsonl(paths[2], [order])
    with pytest.raises(DemoSnapshotError, match="both"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)


def test_capture_uses_exact_eight_read_bracket_and_is_byte_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _active_fixture(tmp_path)
    calls: list[str] = []
    real_read = adapter._read_entry

    def observed_read(descriptor: int, name: str, *, byte_limit: int):  # type: ignore[no-untyped-def]
        calls.append(name)
        return real_read(descriptor, name, byte_limit=byte_limit)

    monkeypatch.setattr(adapter, "_read_entry", observed_read)
    first = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    first_bytes = {path.name: path.read_bytes() for path in first.snapshot_dir.iterdir()}
    second = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert calls[:8] == [
        "lane_state.json",
        "heartbeat.json",
        "orders.jsonl",
        "lane_state.json",
        "heartbeat.json",
        "orders.jsonl",
        "lane_state.json",
        "heartbeat.json",
    ]
    assert calls[8:] == calls[:8]
    assert second.snapshot_id == first.snapshot_id
    assert {path.name: path.read_bytes() for path in second.snapshot_dir.iterdir()} == first_bytes


@pytest.mark.parametrize("fault", ["byte_rewrite", "byte_identical_inode_replacement"])
def test_bracket_rejects_prefix_rewrite_and_byte_identical_identity_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    _active_fixture(tmp_path)
    calls = 0
    real_read = adapter._read_entry

    def changed_read(descriptor: int, name: str, *, byte_limit: int):  # type: ignore[no-untyped-def]
        nonlocal calls
        result = real_read(descriptor, name, byte_limit=byte_limit)
        slot = calls % 8
        calls += 1
        if slot != 5:
            return result
        if fault == "byte_rewrite":
            return adapter._StableRead(result.data + b" ", result.metadata)
        metadata = list(result.metadata)
        metadata[1] += 1
        return adapter._StableRead(result.data, tuple(metadata))

    monkeypatch.setattr(adapter, "_read_entry", changed_read)
    with pytest.raises(DemoSnapshotError, match="UNSTABLE_ACTIVE_SOURCE"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert calls == 24


def test_semantic_mismatch_retries_three_whole_attempts_then_halts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _active_fixture(tmp_path)
    heartbeat = json.loads(paths[1].read_text(encoding="utf-8"))
    heartbeat["latest_closed_bar"] = "2026-07-23T06:50:00Z"
    paths[1].write_text(json.dumps(heartbeat) + "\n", encoding="utf-8")
    attempts = 0
    real_bracket = adapter._read_bracket

    def observed_bracket(repo_root: Path) -> tuple[bytes, bytes, bytes]:
        nonlocal attempts
        attempts += 1
        return real_bracket(repo_root)

    monkeypatch.setattr(adapter, "_read_bracket", observed_bracket)
    with pytest.raises(DemoSnapshotError, match="UNSTABLE_ACTIVE_SOURCE"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert attempts == 3
    assert not (tmp_path / "artifacts/evidence").exists()


@pytest.mark.parametrize("fault", ["symlink", "hardlink"])
def test_active_sources_must_be_real_single_link_files(tmp_path: Path, fault: str) -> None:
    paths = _active_fixture(tmp_path)
    state = paths[0]
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(state.read_bytes())
    state.unlink()
    if fault == "symlink":
        state.symlink_to(replacement)
    else:
        os.link(replacement, state)
    with pytest.raises(DemoSnapshotError, match="safely|single-link"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)


def test_orders_requires_strict_utf8_jsonl_terminal_newline(tmp_path: Path) -> None:
    paths = _active_fixture(tmp_path)
    paths[2].write_bytes(paths[2].read_bytes().rstrip(b"\n"))
    with pytest.raises(DemoSnapshotError, match="terminal newline"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    paths[2].write_bytes(b"\xff\n")
    with pytest.raises(DemoSnapshotError, match="UTF-8"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)


def test_blank_jsonl_rows_duplicate_keys_and_byte_limit_fail_closed(tmp_path: Path) -> None:
    paths = _active_fixture(tmp_path)
    paths[2].write_bytes(paths[2].read_bytes() + b"\n")
    with pytest.raises(DemoSnapshotError, match="blank lines"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    paths = _active_fixture(tmp_path / "duplicate")
    paths[0].write_bytes(
        paths[0]
        .read_bytes()
        .replace(
            b'"cursor":"2026-07-23T06:55:00Z",',
            b'"cursor":"2026-07-23T06:55:00Z","cursor":"2026-07-23T06:55:00Z",',
        )
    )
    with pytest.raises(DemoSnapshotError, match="duplicate key"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path / "duplicate")
    paths = _active_fixture(tmp_path / "oversize")
    paths[0].write_bytes(b" " * (adapter.MAX_SNAPSHOT_BYTES + 1))
    with pytest.raises(DemoSnapshotError, match="byte limit"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path / "oversize")


def test_capture_time_and_current_long_stop_invariants_fail_closed(tmp_path: Path) -> None:
    _active_fixture(tmp_path / "time")
    with pytest.raises(DemoSnapshotError, match="UNSTABLE_ACTIVE_SOURCE"):
        capture_demo_snapshot(
            captured_at="2026-07-23T06:59:00Z",
            repo_root=tmp_path / "time",
        )

    mutations = (
        ("mark_price", "0"),
        ("risk_fraction", "1.1"),
        ("price_tick", "0"),
        ("position_base_qty", "0.1"),
        ("base_qty", "0.1"),
        ("risk_boundary_price", "1600"),
        ("trigger_price", "1900"),
    )
    for index, (field, value) in enumerate(mutations):
        root = tmp_path / f"stop-{index}"
        paths = _active_fixture(root)
        heartbeat = json.loads(paths[1].read_text(encoding="utf-8"))
        state = json.loads(paths[0].read_text(encoding="utf-8"))
        if field == "mark_price":
            heartbeat[field] = value
        else:
            state["resting_stop"][field] = value
            heartbeat["resting_stop"][field] = value
        paths[0].write_text(json.dumps(state) + "\n", encoding="utf-8")
        paths[1].write_text(json.dumps(heartbeat) + "\n", encoding="utf-8")
        with pytest.raises(DemoSnapshotError, match="UNSTABLE_ACTIVE_SOURCE"):
            capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=root)


def test_profitable_long_trailing_stop_above_entry_is_accepted(tmp_path: Path) -> None:
    paths = _active_fixture(tmp_path)
    state = json.loads(paths[0].read_text(encoding="utf-8"))
    heartbeat = json.loads(paths[1].read_text(encoding="utf-8"))
    heartbeat["mark_price"] = "2100"
    for source in (state, heartbeat):
        source["resting_stop"]["trigger_price"] = "2000"
    paths[0].write_text(json.dumps(state) + "\n", encoding="utf-8")
    paths[1].write_text(json.dumps(heartbeat) + "\n", encoding="utf-8")
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert result.coverage["stop_coverage"] == "CURRENT_STATE_ONLY"


def test_endpoint_like_allowed_text_is_rejected_before_publication(tmp_path: Path) -> None:
    paths = _active_fixture(tmp_path)
    order = json.loads(paths[2].read_text(encoding="utf-8"))
    order["reason"] = "https://demo.invalid/v5/order"
    _write_jsonl(paths[2], [order])
    with pytest.raises(DemoSnapshotError, match="bounded safe token"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert not (tmp_path / "artifacts/evidence/private_demo").exists()


def test_incomplete_matching_snapshot_completes_but_unexpected_entry_halts(
    tmp_path: Path,
) -> None:
    _active_fixture(tmp_path)
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    manifest_bytes = (result.snapshot_dir / "manifest.json").read_bytes()
    (result.snapshot_dir / "manifest.json").unlink()
    assert capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path).snapshot_id == (
        result.snapshot_id
    )
    assert (result.snapshot_dir / "manifest.json").read_bytes() == manifest_bytes
    (result.snapshot_dir / "manifest.json").unlink()
    extra = result.snapshot_dir / "unexpected.bin"
    extra.write_bytes(b"x")
    os.chmod(extra, 0o600)
    with pytest.raises(DemoSnapshotError, match="unexpected"):
        capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)


def test_known_external_temp_hardlink_crash_is_recovered_before_manifest_validation(
    tmp_path: Path,
) -> None:
    _active_fixture(tmp_path)
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    manifest = result.snapshot_dir / "manifest.json"
    temporary = result.snapshot_dir.parent / (f".{result.snapshot_id}.manifest.json.tmp-999999")
    os.link(manifest, temporary)
    assert manifest.stat().st_nlink == 2
    replay = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert replay.snapshot_id == result.snapshot_id
    assert not temporary.exists()
    assert manifest.stat().st_nlink == 1
    assert {path.name for path in result.snapshot_dir.iterdir()} == adapter._FINAL_FILES


def test_pending_data_and_manifest_temporaries_recover_data_first(tmp_path: Path) -> None:
    _active_fixture(tmp_path)
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    root = result.snapshot_dir.parent
    retained = {
        name: (result.snapshot_dir / name).read_bytes()
        for name in ("orders.jsonl", "manifest.json")
    }
    for name, payload in retained.items():
        (result.snapshot_dir / name).unlink()
        temporary = root / f".{result.snapshot_id}.{name}.tmp-999998"
        temporary.write_bytes(payload)
        os.chmod(temporary, 0o600)
    replay = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    assert replay.snapshot_id == result.snapshot_id
    assert {path.name for path in replay.snapshot_dir.iterdir()} == adapter._FINAL_FILES
    assert not list(root.glob(f".{result.snapshot_id}.*.tmp-*"))
    assert all(
        (replay.snapshot_dir / name).read_bytes() == payload for name, payload in retained.items()
    )


def test_adapter_venue_refs_are_accepted_by_stage_a_without_double_hashing(
    tmp_path: Path,
) -> None:
    _active_fixture(tmp_path)
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    state = parse_json_bytes((result.snapshot_dir / "lane_state.json").read_bytes(), label="state")
    heartbeat = parse_json_bytes(
        (result.snapshot_dir / "heartbeat.json").read_bytes(), label="heartbeat"
    )
    orders = parse_jsonl_bytes((result.snapshot_dir / "orders.jsonl").read_bytes(), label="orders")
    refs = result.manifest["sanitized_files"][:3]
    projection, _ = build_legacy_projection(
        state,
        heartbeat,
        orders,
        source_refs=refs,
        captured_at=CAPTURED_AT,
        source_label="adapter-test",
    )
    retained = projection["episodes"][0]["attempts"][0]["venue_order_ref"]
    assert retained == orders[0]["venue_order_ref"]
    retained_signal = projection["episodes"][0]["attempts"][0]["signal_ref_sha256"]
    assert retained_signal == orders[0]["signal_ref_sha256"]


def test_full_capture_stage_a_commit_and_replay_are_idempotent(tmp_path: Path) -> None:
    _active_fixture(tmp_path)
    snapshot = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    output = tmp_path / "artifacts/evidence/private_demo/stage_a"
    arguments = {
        "lane_state_path": snapshot.snapshot_dir / "lane_state.json",
        "heartbeat_path": snapshot.snapshot_dir / "heartbeat.json",
        "orders_path": snapshot.snapshot_dir / "orders.jsonl",
        "output_dir": output,
        "source_label": "snapshot-integration",
        "captured_at": CAPTURED_AT,
        "repo_root": tmp_path,
    }
    first = run_bridge(**arguments)
    first_export = first.export_path.read_bytes()
    replay = run_bridge(**arguments)
    assert first.appended_event_count == len(first.events)
    assert replay.appended_event_count == 0
    assert replay.export_path.read_bytes() == first_export
    assert replay.projection["realized_outcome_count"] == 0


def test_large_many_frame_ledger_preserves_all_safe_observations(tmp_path: Path) -> None:
    paths = _active_fixture(tmp_path)
    base = datetime(2026, 7, 23, 0, 0, tzinfo=UTC)
    rows: list[dict[str, object]] = [
        {
            "schema_version": "v1",
            "recorded_at": base.isoformat().replace("+00:00", "Z"),
            "symbol": "ETHUSDT",
            "side": "Buy",
            "unit": "base",
            "signal_ref": "frame-success",
            "reason": "ENTRY_SIGNAL",
            "environment": "VENUE_DEMO",
            "real_money": False,
            "promotion_eligible": False,
            "validation_state": "UNVALIDATED",
            "ok": True,
            "stage": "done",
            "order_id": "large-ledger-order",
            "qty": "0.01341033",
            "avg_price": "1862.3700",
            "cum_exec_qty": "0.01341033",
            "fee": "0.00000420",
        }
    ]
    stages = ("kill_switch", "price_unavailable", "qty_below_step", "place")
    for index in range(1, 513):
        row = _failure_order(stages[index % len(stages)], index=index % 60)
        row["recorded_at"] = (base + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
        row["signal_ref"] = f"frame-{index}"
        rows.append(row)
    _write_jsonl(paths[2], rows)
    result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    retained = parse_jsonl_bytes(
        (result.snapshot_dir / "orders.jsonl").read_bytes(),
        label="large sanitized ledger",
    )
    assert len(retained) == 513
    assert retained[0]["venue_order_ref"] == snapshot_venue_order_ref("large-ledger-order")
    assert all(row["venue_order_ref"] is None for row in retained[1:])
    assert len({row["signal_ref_sha256"] for row in retained}) == 513
    arguments = {
        "lane_state_path": result.snapshot_dir / "lane_state.json",
        "heartbeat_path": result.snapshot_dir / "heartbeat.json",
        "orders_path": result.snapshot_dir / "orders.jsonl",
        "output_dir": tmp_path / "artifacts/evidence/private_demo/large_stage_a",
        "source_label": "large-ledger",
        "captured_at": CAPTURED_AT,
        "repo_root": tmp_path,
    }
    first = run_bridge(**arguments)
    export_bytes = first.export_path.read_bytes()
    replay = run_bridge(**arguments)
    assert len(first.events) == 514
    assert first.appended_event_count == 514
    assert replay.appended_event_count == 0
    assert replay.export_path.read_bytes() == export_bytes


def test_stage_a_rejects_ambiguous_order_identity() -> None:
    ref = snapshot_venue_order_ref("raw")
    sources = [
        {"kind": "lane_state", "label": "test.lane", "sha256": "a" * 64, "byte_count": 1},
        {"kind": "heartbeat", "label": "test.heartbeat", "sha256": "b" * 64, "byte_count": 1},
        {"kind": "orders", "label": "test.orders", "sha256": "c" * 64, "byte_count": 1},
    ]
    with pytest.raises(DemoDecisionBridgeError, match="both"):
        build_legacy_projection(
            {"lane_base": "1"},
            {},
            [{"order_id": "raw", "venue_order_ref": ref}],
            source_refs=sources,
            captured_at=CAPTURED_AT,
        )


def test_cli_has_fixed_sources_and_requires_only_explicit_capture_time(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli.main([], repo_root=tmp_path)
    _active_fixture(tmp_path)
    assert cli.main(["--captured-at", CAPTURED_AT], repo_root=tmp_path) == 0
    response = json.loads(capsys.readouterr().out)
    assert "status" not in response
    assert response["capture_status"] == "PASS"
    assert response["evidence_completeness"] == "PARTIAL_LEGACY_OPEN"
    assert response["stage_a_commit_status"] == "NOT_RUN"
    assert response["promotion_eligible"] is False
    assert response["execution_authority"] == "NONE"
    with pytest.raises(SystemExit):
        cli.main(["--captured-at", CAPTURED_AT, "--lane-state", "other"], repo_root=tmp_path)


def test_adapter_and_cli_have_no_network_order_transport_or_demo_runtime_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden_roots = {"urllib", "requests", "httpx", "websockets", "socket"}
    forbidden_modules = {
        "scripts.demo_eth_lane",
        "tios.services.dashboard_api.demo_lane",
        "tios.adapters",
    }
    for path in (
        root / "src/tios/evidence/demo_snapshot_adapter.py",
        root / "scripts/capture_demo_decision_snapshot.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not {item.split(".")[0] for item in imported} & forbidden_roots
        assert not imported & forbidden_modules


def test_private_modes_are_exact_under_restrictive_umask(tmp_path: Path) -> None:
    _active_fixture(tmp_path)
    evidence = tmp_path / "artifacts/evidence"
    evidence.mkdir(mode=0o755)
    old_umask = os.umask(0o777)
    try:
        result = capture_demo_snapshot(captured_at=CAPTURED_AT, repo_root=tmp_path)
    finally:
        os.umask(old_umask)
    private_root = tmp_path / "artifacts/evidence/private_demo"
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o700
        for path in (private_root, result.snapshot_dir.parent, result.snapshot_dir)
    )
    assert all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in result.snapshot_dir.iterdir())


def test_tracked_nested_ignore_pattern_excludes_private_demo_in_fresh_repo(
    tmp_path: Path,
) -> None:
    source = Path(__file__).resolve().parents[1] / "artifacts/evidence/.gitignore"
    nested = tmp_path / "artifacts/evidence/.gitignore"
    nested.parent.mkdir(parents=True)
    nested.write_bytes(source.read_bytes())
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    result = subprocess.run(
        [
            "git",
            "check-ignore",
            "--no-index",
            "-v",
            "artifacts/evidence/private_demo/snapshots/example/manifest.json",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.startswith("artifacts/evidence/.gitignore:2:private_demo/")
