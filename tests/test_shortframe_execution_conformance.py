"""Short-frame hierarchy and availability conformance is fixed and fail-closed."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from tios.dataset import shortframe_execution_conformance as conformance
from tios.dataset.normalize import CANONICAL_SCHEMA, content_sha256

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "research/SHORTFRAME_BAR_HIERARCHY_AND_FILL_AVAILABILITY_V1.yaml"
D = Decimal


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _minute_rows(symbol: str, *, absent: set[int] | None = None) -> list[dict[str, Any]]:
    absent = absent or set()
    base = D("100") if symbol == "BTCUSDT" else D("200")
    start = datetime(2021, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(30):
        if index in absent:
            continue
        opened = start + timedelta(minutes=index)
        price = base + D(index)
        rows.append(
            {
                "timestamp_open_utc": opened,
                "open": price,
                "high": price + D("2"),
                "low": price - D("1"),
                "close": price + D("1"),
                "volume_base": D("1.00000000"),
                "close_timestamp_utc": opened + timedelta(seconds=59, milliseconds=999),
                "quote_volume": D("2.00000000"),
                "trade_count": index + 1,
                "taker_buy_base_volume": D("0.40000000"),
                "taker_buy_quote_volume": D("0.80000000"),
                "source": "fixture",
                "instrument": symbol,
                "interval": "1m",
            }
        )
    return rows


def _parent_rows(
    complete_minutes: list[dict[str, Any]],
    symbol: str,
    interval: str,
    *,
    changes: dict[tuple[int, str], Any] | None = None,
) -> list[dict[str, Any]]:
    changes = changes or {}
    width = 5 if interval == "5m" else 15
    rows: list[dict[str, Any]] = []
    for parent_index, offset in enumerate(range(0, 30, width)):
        children = complete_minutes[offset : offset + width]
        opened = children[0]["timestamp_open_utc"]
        row = {
            "timestamp_open_utc": opened,
            "open": children[0]["open"],
            "high": max(item["high"] for item in children),
            "low": min(item["low"] for item in children),
            "close": children[-1]["close"],
            "volume_base": sum((item["volume_base"] for item in children), D(0)),
            "close_timestamp_utc": opened + timedelta(minutes=width) - timedelta(milliseconds=1),
            "quote_volume": sum((item["quote_volume"] for item in children), D(0)),
            "trade_count": sum(item["trade_count"] for item in children),
            "taker_buy_base_volume": sum(
                (item["taker_buy_base_volume"] for item in children), D(0)
            ),
            "taker_buy_quote_volume": sum(
                (item["taker_buy_quote_volume"] for item in children), D(0)
            ),
            "source": "fixture",
            "instrument": symbol,
            "interval": interval,
        }
        for (changed_parent, field), value in changes.items():
            if changed_parent == parent_index:
                row[field] = value(row[field]) if callable(value) else value
        rows.append(row)
    return rows


def _table(rows: list[dict[str, Any]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=CANONICAL_SCHEMA)


def _semantics(row: dict[str, Any], symbol: str, interval: str) -> dict[str, Any]:
    anomaly = {
        "instrument": symbol,
        "interval": interval,
        "timestamp_open_utc": row["timestamp_open_utc"].isoformat(timespec="microseconds"),
        "close_timestamp_utc": row["close_timestamp_utc"].isoformat(timespec="microseconds"),
    }
    return {
        "status": "PASS",
        "anomaly_count": 1,
        "anomalies": [anomaly],
        "inventory": {"status": "PASS"},
    }


def _record(path: Path, table: pa.Table, semantics: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS",
        "rows": table.num_rows,
        "schema": str(table.schema),
        "parquet_sha256": _sha256(path),
        "content_sha256": content_sha256(table.combine_chunks()),
        "close_time_semantics": semantics,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_bytes(_canonical(value))


def _make_fixture(
    tmp_path: Path,
    *,
    absent_by_symbol: dict[str, set[int]] | None = None,
    changes: dict[tuple[str, str], dict[tuple[int, str], Any]] | None = None,
) -> tuple[conformance.ConformancePaths, dict[str, Any]]:
    absent_by_symbol = absent_by_symbol or {}
    changes = changes or {}
    normalized = tmp_path / f"data/normalized/{conformance.DATASET_ID}"
    evidence = tmp_path / "artifacts/datasets"
    research = tmp_path / "research"
    scripts = tmp_path / "scripts"
    source = tmp_path / "src/tios/dataset"
    for directory in (normalized, evidence, research, scripts, source):
        directory.mkdir(parents=True, exist_ok=True)
    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    (research / PROTOCOL.name).write_text(
        yaml.safe_dump(protocol, sort_keys=False), encoding="utf-8"
    )
    (scripts / "verify_shortframe_execution_conformance.py").write_text(
        "# fixture\n", encoding="utf-8"
    )
    (source / "shortframe_execution_conformance.py").write_text("# fixture\n", encoding="utf-8")

    records: dict[str, Any] = {}
    for symbol in conformance.SYMBOLS:
        full_minutes = _minute_rows(symbol)
        retained_minutes = _minute_rows(symbol, absent=absent_by_symbol.get(symbol))
        one_table = _table(retained_minutes)
        one_path = normalized / f"{symbol}_1m.parquet"
        pq.write_table(one_table, one_path)  # type: ignore[no-untyped-call]
        records[f"{symbol}_1m"] = _record(
            one_path,
            one_table,
            {
                "status": "PASS",
                "anomaly_count": 0,
                "anomalies": [],
                "inventory": {"status": "PASS"},
            },
        )
        for interval in ("5m", "15m"):
            rows = _parent_rows(
                full_minutes,
                symbol,
                interval,
                changes=changes.get((symbol, interval)),
            )
            table = _table(rows)
            path = normalized / f"{symbol}_{interval}.parquet"
            pq.write_table(table, path)  # type: ignore[no-untyped-call]
            records[f"{symbol}_{interval}"] = _record(
                path, table, _semantics(rows[0], symbol, interval)
            )

    quality = {
        "dataset_id": conformance.DATASET_ID,
        "overall": "PASS",
        "execution_authority": "NONE",
        "quality_run2": {"tables": records},
    }
    stable_quality = evidence / f"{conformance.DATASET_ID}.QUALITY_REPORT.json"
    _write_json(stable_quality, quality)
    quality_sha = _sha256(stable_quality)
    archived_quality = evidence / (f"{conformance.DATASET_ID}.QUALITY_REPORT_{quality_sha}.json")
    archived_quality.write_bytes(stable_quality.read_bytes())

    manifest = {
        "dataset_id": conformance.DATASET_ID,
        "execution_authority": "NONE",
        "cutoff_utc": conformance.CUTOFF_UTC.isoformat(),
        "quality_report_sha256": quality_sha,
        "tables": records,
    }
    stable_manifest = evidence / f"{conformance.DATASET_ID}.manifest.json"
    _write_json(stable_manifest, manifest)
    manifest_sha = _sha256(stable_manifest)
    archived_manifest = evidence / f"{conformance.DATASET_ID}.manifest_{manifest_sha}.json"
    archived_manifest.write_bytes(stable_manifest.read_bytes())
    paths = conformance.ConformancePaths(
        tmp_path,
        expected_manifest_sha256=manifest_sha,
        expected_quality_sha256=quality_sha,
    )
    return paths, protocol


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key).lower() for key in value} | {
            nested for item in value.values() for nested in _all_keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _all_keys(item)}
    return set()


def _production_payload(tag: str) -> dict[str, Any]:
    return {
        "tag": tag,
        "verification_status": "PASS",
        "hierarchy_status": "SOURCE_DIVERGENCES_PRESENT",
        "status": "PASS",
        "execution_authority": "NONE",
    }


def _append_cutoff_rows(paths: conformance.ConformancePaths) -> None:
    for symbol in conformance.SYMBOLS:
        for interval, opened in (
            ("1m", datetime(2026, 6, 30, 23, 59, tzinfo=UTC)),
            ("5m", datetime(2026, 6, 30, 23, 55, tzinfo=UTC)),
            ("15m", datetime(2026, 6, 30, 23, 45, tzinfo=UTC)),
        ):
            path = paths.dataset_root / f"{symbol}_{interval}.parquet"
            table = pq.read_table(path)  # type: ignore[no-untyped-call]
            row = table.slice(table.num_rows - 1, 1).to_pylist()[0]
            row["timestamp_open_utc"] = opened
            row["close_timestamp_utc"] = (
                opened
                + timedelta(microseconds=conformance.interval_microseconds(interval))
                - timedelta(milliseconds=1)
            )
            appended = pa.concat_tables([table, _table([row])])
            pq.write_table(appended, path)  # type: ignore[no-untyped-call]


@pytest.mark.parametrize("interval", ["1m", "5m", "15m", "1h", "4h", "1d"])
def test_interval_helper_uses_all_six_canonical_frames(interval: str) -> None:
    assert conformance.interval_microseconds(interval) > 0


def test_complete_aggregation_and_deterministic_two_fresh_reads(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    aggregate = result["verification"]["analysis"]["aggregate"]
    assert aggregate["incomplete_windows"] == 0
    assert aggregate["source_divergence_windows"] == 0
    assert result["verification"]["deterministic_equality"] == "PASS"
    assert result["execution_authority"] == "NONE"
    assert result["verification_status"] == "NON_PRODUCTION_FIXTURE"
    assert result["hierarchy_status"] == "UNBOUND_FIXTURE_ANALYSIS"
    five_to_fifteen = [
        item
        for item in result["verification"]["analysis"]["mappings"]
        if item["child_interval"] == "5m" and item["parent_interval"] == "15m"
    ]
    assert len(five_to_fifteen) == 2
    assert all(
        item["classification_counts"]["EXACT_CONFORMANT"] == item["parent_rows"]
        for item in five_to_fifteen
    )


def test_gap_is_incomplete_and_exact_boundary_mapping_is_blocked(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path, absent_by_symbol={"BTCUSDT": {5}})
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    aggregate = result["verification"]["analysis"]["aggregate"]
    assert aggregate["incomplete_windows"] == 2
    assert aggregate["blocked_absent_open"] >= 2
    exceptions = result["verification"]["analysis"]["pinned_inventories"][
        "unavailable_gap_fill_records"
    ]["details"]
    boundary = next(
        item
        for item in exceptions
        if item["instrument"] == "BTCUSDT"
        and item["signal_timeframe"] == "5m"
        and item["signal_open_utc"] == "2021-01-01T00:00:00.000000Z"
    )
    assert boundary["nominal_boundary_utc"] == "2021-01-01T00:05:00.000000Z"
    assert boundary["fill_open_utc"] is None
    minute_table = pq.read_table(  # type: ignore[no-untyped-call]
        paths.dataset_root / "BTCUSDT_1m.parquet"
    )
    assert datetime(2021, 1, 1, 0, 6, tzinfo=UTC) in minute_table["timestamp_open_utc"].to_pylist()


def test_all_six_availability_coordinates_and_cutoffs(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    _append_cutoff_rows(paths)
    checks = [
        conformance._analyze_availability(symbol=symbol, signal_interval=interval, paths=paths)
        for symbol in conformance.SYMBOLS
        for interval in ("1m", "5m", "15m")
    ]
    assert {(item["instrument"], item["signal_timeframe"]) for item in checks} == {
        (symbol, interval) for symbol in conformance.SYMBOLS for interval in ("1m", "5m", "15m")
    }
    outside = [record for item in checks for record in item["outside_window_records"]]
    assert len(outside) == 6
    assert all(record["fill_open_utc"] is None for record in outside)


def test_early_source_close_never_advances_nominal_availability(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    check = result["verification"]["analysis"]["early_close_availability"]
    assert check["audited_rows"] == 4
    assert all(item["source_close_utc"] < item["availability_utc"] for item in check["details"])


def test_early_close_at_boundary_fails(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    quality = json.loads(paths.stable_quality.read_text())
    anomaly = quality["quality_run2"]["tables"]["BTCUSDT_5m"]["close_time_semantics"]["anomalies"][
        0
    ]
    anomaly["close_timestamp_utc"] = "2021-01-01T00:05:00.000000+00:00"
    with pytest.raises(ValueError, match="availability boundary"):
        conformance._verify_early_close_availability(quality)


def test_one_stored_unit_volume_difference_is_source_divergence(tmp_path: Path) -> None:
    paths, _ = _make_fixture(
        tmp_path,
        changes={("BTCUSDT", "5m"): {(0, "volume_base"): lambda value: value + D("0.00000001")}},
    )
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    assert result["verification"]["analysis"]["aggregate"]["source_divergence_windows"] >= 1


@pytest.mark.parametrize(
    ("field", "change", "reported"),
    [
        ("high", lambda value: value + D("1"), "high"),
        ("low", lambda value: value - D("1"), "low"),
        ("open", lambda value: value + D("1"), "open"),
        ("close", lambda value: value + D("1"), "close"),
        (
            "close_timestamp_utc",
            lambda value: value - timedelta(seconds=1),
            "close_timestamp_utc",
        ),
        ("trade_count", lambda value: value + 1, "trade_count"),
        ("volume_base", lambda value: value + D("0.00000002"), "volume_base"),
        ("quote_volume", lambda value: value + D("0.00000001"), "quote_volume"),
        (
            "taker_buy_base_volume",
            lambda value: value + D("0.00000001"),
            "taker_buy_base_volume",
        ),
        (
            "taker_buy_quote_volume",
            lambda value: value + D("0.00000001"),
            "taker_buy_quote_volume",
        ),
    ],
)
def test_source_divergence_is_classified_with_exact_values(
    tmp_path: Path,
    field: str,
    change: Any,
    reported: str,
) -> None:
    paths, _ = _make_fixture(
        tmp_path,
        changes={("BTCUSDT", "5m"): {(0, field): change}},
    )
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    assert result["verification"]["analysis"]["aggregate"]["source_divergence_windows"] >= 1
    details = result["verification"]["analysis"]["pinned_inventories"]["source_divergence_records"][
        "details"
    ]
    target = next(
        item
        for item in details
        if item["child_timeframe"] == "1m" and item["parent_timeframe"] == "5m"
    )
    assert target["mismatch_fields"] == [reported]
    assert set(target["native_values"]) == {reported}
    assert set(target["aggregated_child_values"]) == {reported}


def test_inventory_count_and_digest_are_both_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = [{"coordinate": "A"}, {"coordinate": "B"}]
    digest = hashlib.sha256(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    bindings = dict(conformance.INVENTORY_BINDINGS)
    bindings["source_divergence_records"] = {"count": 2, "sha256": digest}
    monkeypatch.setattr(conformance, "INVENTORY_BINDINGS", bindings)
    exact = conformance._inventory_result(
        "source_divergence_records", records, enforce_binding=True
    )
    assert exact["count"] == 2
    with pytest.raises(ValueError, match="source_divergence_records drift"):
        conformance._inventory_result(
            "source_divergence_records",
            [records[1], records[0]],
            enforce_binding=True,
        )


def test_gap_detail_query_is_bounded(tmp_path: Path) -> None:
    path = tmp_path / "many-gaps.parquet"
    rows = _minute_rows("BTCUSDT")
    seed = rows[0]
    many = []
    for index in range(120):
        opened = datetime(2021, 1, 1, tzinfo=UTC) + timedelta(minutes=index * 2)
        row = dict(seed)
        row["timestamp_open_utc"] = opened
        row["close_timestamp_utc"] = opened + timedelta(seconds=59, milliseconds=999)
        many.append(row)
    pq.write_table(_table(many), path)  # type: ignore[no-untyped-call]
    connection = duckdb.connect()
    try:
        inventory = conformance._bounded_gap_inventory(connection, path, "1m")
    finally:
        connection.close()
    assert inventory["boundary_count"] == 119
    assert inventory["absent_open_count"] == 119
    assert len(inventory["details"]) == conformance.DETAIL_LIMIT
    assert inventory["details_truncated"] is True


def test_parent_missing_classification_fails_closed(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    parent_path = paths.dataset_root / "BTCUSDT_5m.parquet"
    parent = pq.read_table(parent_path)  # type: ignore[no-untyped-call]
    pq.write_table(parent.slice(0, parent.num_rows - 1), parent_path)  # type: ignore[no-untyped-call]
    with pytest.raises(ValueError, match="PARENT_MISSING"):
        conformance._analyze_mapping(
            symbol="BTCUSDT",
            child_interval="1m",
            parent_interval="5m",
            expected_children=5,
            child_early_opens=set(),
            parent_early_opens=set(),
            paths=paths,
        )


def test_evidence_hash_drift_fails_before_analysis(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    paths.stable_manifest.write_bytes(paths.stable_manifest.read_bytes() + b" ")
    with pytest.raises(ValueError, match="binding drift"):
        conformance._verify(paths, require_committed_surface=False, publish=False)


def test_parquet_logical_or_byte_drift_fails(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    target = paths.dataset_root / "BTCUSDT_1m.parquet"
    target.write_bytes(target.read_bytes() + b"drift")
    with pytest.raises(ValueError, match="byte hash drift"):
        conformance._verify(paths, require_committed_surface=False, publish=False)


def test_symlinked_evidence_and_path_escape_fail(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    retained = paths.archived_quality
    copy = tmp_path / "quality-copy.json"
    copy.write_bytes(retained.read_bytes())
    retained.unlink()
    retained.symlink_to(copy)
    with pytest.raises(ValueError, match="symlinked"):
        conformance._verify(paths, require_committed_surface=False, publish=False)
    outside = tmp_path.parent / "outside-conformance"
    outside.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match="escapes"):
        conformance._require_confined_file(outside / "x", root=tmp_path, label="test")


def test_production_gate_rejects_uncommitted_fixture_surface(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    with pytest.raises(ValueError, match="untracked committed surface"):
        conformance._verify(paths, require_committed_surface=True, publish=False)


def test_current_advances_a_to_b_and_recovers_interrupted_advancement(
    tmp_path: Path,
) -> None:
    paths, _ = _make_fixture(tmp_path)
    result_a = _production_payload("A")
    result_b = _production_payload("B")
    first = conformance._publish(paths, result_a)
    assert conformance._publish(paths, result_a) == first
    current = Path(first["current"])
    assert json.loads(current.read_text())["tag"] == "A"
    second = conformance._publish(paths, result_b)
    assert json.loads(current.read_text())["tag"] == "B"
    assert Path(first["content_addressed"]).is_file()
    assert Path(second["content_addressed"]).is_file()

    conformance._atomic_replace_current(
        current,
        conformance._canonical_json(result_a),
        output_root=paths.output_root,
        root=paths.repo_root,
    )
    assert json.loads(current.read_text())["tag"] == "A"
    recovered = conformance._publish(paths, result_b)
    assert recovered == second
    assert json.loads(current.read_text())["tag"] == "B"

    current.unlink()
    assert conformance._publish(paths, result_b) == second
    assert json.loads(current.read_text())["tag"] == "B"


def test_archive_conflict_and_corrupt_current_fail_closed(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    result = _production_payload("A")
    encoded = conformance._canonical_json(result)
    digest = hashlib.sha256(encoded).hexdigest()
    paths.output_root.mkdir()
    archive = paths.output_root / f"shortframe_execution_conformance_{digest}.json"
    archive.write_text("{}\n")
    with pytest.raises(ValueError, match="existing output differs"):
        conformance._publish(paths, result)

    archive.unlink()
    published = conformance._publish(paths, result)
    current = Path(published["current"])
    current.write_text("{}\n")
    with pytest.raises(ValueError, match="archive bound by existing CURRENT"):
        conformance._publish(paths, result)


def test_relaxed_fixture_cannot_publish_or_claim_production_pass(
    tmp_path: Path,
) -> None:
    paths, _ = _make_fixture(tmp_path)
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    assert result["verification_status"] == "NON_PRODUCTION_FIXTURE"
    assert result["hierarchy_status"] == "UNBOUND_FIXTURE_ANALYSIS"
    assert result["status"] == "NON_PRODUCTION"
    analysis = result["verification"]["analysis"]
    assert analysis["verification_status"] == "NON_PRODUCTION_FIXTURE"
    assert analysis["hierarchy_status"] == "UNBOUND_FIXTURE_ANALYSIS"
    with pytest.raises(ValueError, match="production PASS"):
        conformance._publish(paths, result)
    for committed, inventory in ((False, False), (False, True), (True, False)):
        with pytest.raises(ValueError, match="publication requires"):
            conformance._verify(
                paths,
                require_committed_surface=committed,
                enforce_production_inventory=inventory,
                publish=True,
            )


def test_output_has_fixed_schema_and_no_prohibited_fields(tmp_path: Path) -> None:
    paths, _ = _make_fixture(tmp_path)
    result = conformance._verify(paths, require_committed_surface=False, publish=False)
    assert set(result) == conformance.OUTPUT_SCHEMA_KEYS
    assert not (_all_keys(result) & conformance.PROHIBITED_OUTPUT_KEYS)
    assert result["limitations"] == [
        "One-minute bars cannot resolve intraminute path.",
        "One-minute bars cannot resolve spread.",
        "One-minute bars cannot resolve market impact.",
        "One-minute bars cannot resolve latency.",
        "One-minute bars cannot resolve queue priority.",
        "One-minute bars cannot resolve partial fill.",
    ]


def test_source_has_no_campaign_or_trial_budget_dependency() -> None:
    source = (ROOT / conformance.SOURCE_RELATIVE).read_text(encoding="utf-8")
    assert "tios.validation.campaign" not in source
    assert "tios.validation.trial_budget" not in source


def test_cli_is_fixed_and_has_no_arbitrary_path_option() -> None:
    assert conformance.parser().parse_args([]) is not None
    with pytest.raises(SystemExit):
        conformance.parser().parse_args(["--root", "/tmp"])


def test_protocol_is_non_performance_and_non_authoritative() -> None:
    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    conformance._validate_protocol(protocol)
    assert protocol["governance"] == {
        "family_id": "NONE",
        "trial_budget_effect": "NONE",
        "execution_authority": "NONE",
        "strategy_authority": "NONE",
    }
    assert set(protocol["output"]["prohibited_fields"]) == conformance.PROHIBITED_OUTPUT_KEYS
    assert protocol["aggregation"]["complete_window"] == conformance.COMPLETE_WINDOW_RULE


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.__setitem__("objective", "drift"),
        lambda value: value["aggregation"].__setitem__("complete_window", "drift"),
        lambda value: value["authenticated_early_close_check"].__setitem__("requirement", "drift"),
        lambda value: value["limitations"].append("extra"),
        lambda value: value["scope"].__setitem__("extra", True),
        lambda value: value["availability"].__setitem__("extra", True),
        lambda value: value["output"].__setitem__("extra", True),
    ],
)
def test_protocol_mutations_and_extra_nested_keys_fail_closed(
    mutation: Any,
) -> None:
    protocol = deepcopy(yaml.safe_load(PROTOCOL.read_text(encoding="utf-8")))
    mutation(protocol)
    with pytest.raises(ValueError, match="protocol"):
        conformance._validate_protocol(protocol)
