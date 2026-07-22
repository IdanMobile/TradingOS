from __future__ import annotations

import fcntl
import hashlib
import inspect
import json
import os
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
from typing import Any

import pyarrow.parquet
import pytest

from tios.dataset import repair_normalized_multi as repair
from tios.dataset.daily_update import _klines_json_to_raw
from tios.dataset.normalize import content_sha256, to_canonical


@pytest.fixture(scope="module")
def retained_plan() -> tuple[dict[str, object], bytes, str]:
    return repair.build_plan()


def test_retained_plan_has_exact_deterministic_scope_and_no_network(
    monkeypatch: pytest.MonkeyPatch,
    retained_plan: tuple[dict[str, object], bytes, str],
) -> None:
    monkeypatch.setattr(repair.urllib.request, "urlopen", lambda *_a, **_k: pytest.fail("network"))
    plan, encoded, digest = retained_plan
    assert hashlib.sha256(encoded).hexdigest() == digest
    assert encoded == repair._canonical(plan)
    assert plan["counts"] == {
        "tables_total": 69,
        "tables_affected": 64,
        "coordinates": 640,
        "retained_rest": 576,
        "manifest_only": 64,
        "1d": 370,
        "1h": 140,
        "4h": 130,
    }
    rows = plan["coordinates"]
    assert isinstance(rows, list)
    assert len({(row["table"], row["open_ms"]) for row in rows}) == 640
    assert sum(row["evidence"]["class"] == "RETAINED_REST" for row in rows) == 576
    assert sum(row["evidence"]["class"] == "MANIFEST_ONLY" for row in rows) == 64
    assert plan["excluded_stale_tables"] == sorted(repair.STALE_TABLES)


def test_semantically_fabricated_content_addressed_plan_is_rejected(
    retained_plan: tuple[dict[str, object], bytes, str],
) -> None:
    plan = deepcopy(retained_plan[0])
    coordinates = plan["coordinates"]
    assert isinstance(coordinates, list) and isinstance(coordinates[0], dict)
    coordinates[0]["open_ms"] += 1
    with pytest.raises(repair.RepairError, match="exact current deterministic derivation"):
        repair.verify_plan_inputs(plan)


def test_archive_and_retained_raw_bytes_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "data"
    dataset = root / "normalized_multi"
    path = root / "raw" / "rest_klines" / "BTCUSDT" / "1d" / ("a" * 64 + ".json")
    path.parent.mkdir(parents=True)
    path.write_text("[]\n")
    item = {
        "rest_update_source": {
            "endpoint": repair.REST,
            "source_pages": [
                {"path": path.relative_to(root / "raw").as_posix(), "sha256": "a" * 64}
            ],
        }
    }
    with pytest.raises(repair.RepairError, match="digest mismatch"):
        repair._raw_evidence(dataset, "BTCUSDT_1d", 1, item)


def test_strict_regular_rejects_symlink_and_hardlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_text("x")
    symlink = tmp_path / "symlink"
    symlink.symlink_to(source)
    with pytest.raises(repair.RepairError, match="single-link regular"):
        repair._read_bound(symlink)
    hardlink = tmp_path / "hardlink"
    os.link(source, hardlink)
    with pytest.raises(repair.RepairError, match="single-link regular"):
        repair._read_bound(source)


def test_confined_path_rejects_symlink_parent(tmp_path: Path) -> None:
    base = tmp_path / "base"
    outside = tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    (base / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(repair.RepairError, match="not a real directory"):
        repair._safe_path(base, "linked/file.json")


def _raw_row(open_ms: int, interval: str, close: str = "2") -> list[object]:
    return [
        open_ms,
        "1",
        "3",
        "0.5",
        close,
        "10",
        open_ms + repair.INTERVAL_MS[interval] - 1,
        "20",
        4,
        "5",
        "9",
        "0",
    ]


def _body(open_ms: int, interval: str, close: str = "2") -> bytes:
    return json.dumps([_raw_row(open_ms, interval, close)], separators=(",", ":")).encode()


@pytest.mark.parametrize(
    "body,match",
    [
        (b"[]", "exactly one"),
        (b"{}", "exactly one"),
        (b"not-json", "UTF-8 JSON"),
        (json.dumps([_raw_row(2, "1h")]).encode(), "wrong coordinate"),
        (json.dumps([_raw_row(1, "1h")[:-1]]).encode(), "wrong coordinate"),
    ],
)
def test_fetched_query_response_validation(body: bytes, match: str) -> None:
    with pytest.raises(repair.RepairError, match=match):
        repair._validate_fetched(body, "BTCUSDT", "1h", 1)


def test_exact_replacement_preserves_non_targets_rows_schema_and_coverage() -> None:
    opens = [0, repair.INTERVAL_MS["1h"], 2 * repair.INTERVAL_MS["1h"]]
    original = to_canonical(
        _klines_json_to_raw([_raw_row(value, "1h") for value in opens]),
        "ms",
        "BTCUSDT",
        "1h",
    ).replace_schema_metadata({b"cursor": b"retained"})
    fresh = repair._validate_fetched(_body(opens[1], "1h", "2.5"), "BTCUSDT", "1h", opens[1])
    before_non_target = repair._logical_without(original, frozenset({opens[1]}))
    result = repair._replace_rows(original, [fresh])
    assert result.num_rows == original.num_rows
    assert result.schema == original.schema
    assert (
        result.column("timestamp_open_utc").to_pylist()
        == original.column("timestamp_open_utc").to_pylist()
    )
    assert repair._logical_without(result, frozenset({opens[1]})) == before_non_target
    assert str(result.column("close")[1]) == "2.50000000"


def test_full_column_timestamp_materialization_is_forbidden_in_repair_hot_paths() -> None:
    for function in (repair._logical_without, repair._replace_rows):
        assert ".to_pylist(" not in inspect.getsource(function)


def test_plan_path_is_confined_and_content_addressed(tmp_path: Path) -> None:
    dataset = tmp_path / "normalized_multi"
    plans = dataset / "repair_plans"
    plans.mkdir(parents=True)
    value = repair._canonical({"schema_version": 1})
    digest = hashlib.sha256(value).hexdigest()
    valid = plans / f"repair_plan_{digest}.json"
    valid.write_bytes(value)
    assert repair._load_bound_plan(valid, dataset=dataset)[1] == digest
    escaped = tmp_path / valid.name
    escaped.write_bytes(value)
    with pytest.raises(repair.RepairError, match="outside"):
        repair._load_bound_plan(escaped, dataset=dataset)
    valid.rename(plans / "repair_plan_wrong.json")
    with pytest.raises(repair.RepairError, match="filename/content"):
        repair._load_bound_plan(plans / "repair_plan_wrong.json", dataset=dataset)


def _synthetic_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, dict[str, Any], dict[str, str], list[int]]:
    dataset = tmp_path / "normalized_multi"
    dataset.mkdir()
    active = [f"T{i:02d}USDT_1h" for i in range(64)]
    inactive = [f"STALE{i}_1h" for i in range(5)]
    bindings: list[dict[str, object]] = []
    before: dict[str, str] = {}
    coordinates: list[dict[str, object]] = []
    opens = [index * repair.INTERVAL_MS["1h"] for index in range(10)]
    for name in active + inactive:
        symbol, interval = name.rsplit("_", 1)
        rows = [_raw_row(value, interval) for value in (opens if name in active else [0])]
        table = to_canonical(_klines_json_to_raw(rows), "ms", symbol, interval)
        path = dataset / f"{name}.parquet"
        pyarrow.parquet.write_table(table, path)
        digest = repair._sha256(path)
        before[path.name] = digest
        binding: dict[str, object] = {
            "path": path.name,
            "size": path.stat().st_size,
            "sha256": digest,
            "rows": table.num_rows,
        }
        if name in active:
            binding["non_target_content_sha256"] = content_sha256(table.slice(0, 0))
            coordinates.extend(
                {
                    "table": name,
                    "symbol": symbol,
                    "interval": interval,
                    "open_ms": value,
                    "evidence": {"class": "MANIFEST_ONLY"},
                }
                for value in opens
            )
        bindings.append(binding)
    plan: dict[str, Any] = {
        "coordinates": coordinates,
        "current_state": {"parquets": bindings},
    }
    digest = "d" * 64
    plan_path = dataset / "repair_plans" / f"repair_plan_{digest}.json"
    monkeypatch.setattr(repair, "_load_bound_plan", lambda *_a, **_k: (plan, digest))
    monkeypatch.setattr(repair, "verify_plan_inputs", lambda *_a, **_k: None)
    monkeypatch.setattr(repair, "_apply_guard", lambda *_a, **_k: nullcontext())
    return dataset, plan_path, plan, before, opens


def _rewrite_committed_audit(dataset: Path, transform: Any, *, plan_digest: str = "d" * 64) -> None:
    receipt_path = repair._receipt_path(dataset, plan_digest)
    receipt = json.loads(receipt_path.read_text())
    audit_path = dataset / "repair_audits" / f"repair_audit_{receipt['audit_sha256']}.json"
    audit = json.loads(audit_path.read_text())
    transform(audit["tables"])
    encoded = repair._canonical(audit)
    digest = hashlib.sha256(encoded).hexdigest()
    (dataset / "repair_audits" / f"repair_audit_{digest}.json").write_bytes(encoded)
    receipt["audit_sha256"] = digest
    receipt_path.write_bytes(repair._canonical(receipt))


def test_apply_fetches_and_validates_all_before_first_publication_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset, plan_path, _plan, before, _opens = _synthetic_apply(tmp_path, monkeypatch)
    calls: list[int] = []

    def fetch(symbol: str, interval: str, open_ms: int) -> bytes:
        assert all(repair._sha256(dataset / name) == digest for name, digest in before.items())
        calls.append(open_ms)
        return _body(open_ms, interval, "2.5")

    receipt = repair.apply_plan(plan_path=plan_path, dataset=dataset, root=tmp_path, fetch=fetch)
    assert len(calls) == 640
    assert receipt["status"] == "COMMITTED"
    assert receipt["affected_tables"] == 64
    calls.clear()
    assert (
        repair.apply_plan(
            plan_path=plan_path,
            dataset=dataset,
            root=tmp_path,
            fetch=lambda *_a: pytest.fail("idempotent apply fetched"),
        )
        == receipt
    )
    assert calls == []
    committed = next(dataset.glob("T*USDT_1h.parquet"))
    committed_bytes = committed.read_bytes()
    committed.write_bytes(committed_bytes + b"drift")
    with pytest.raises(repair.RepairError, match="bound input drifted"):
        repair.apply_plan(
            plan_path=plan_path,
            dataset=dataset,
            root=tmp_path,
            fetch=lambda *_a: pytest.fail("committed-drift retry fetched"),
        )
    with pytest.raises(repair.RepairError, match="bound input drifted"):
        repair.recover(plan_path=plan_path, dataset=dataset, root=tmp_path)
    committed.write_bytes(committed_bytes)
    audit = next((dataset / "repair_audits").glob("*.json"))
    audit.write_bytes(audit.read_bytes() + b" ")
    with pytest.raises(repair.RepairError, match="audit digest mismatch"):
        repair.apply_plan(
            plan_path=plan_path,
            dataset=dataset,
            root=tmp_path,
            fetch=lambda *_a: pytest.fail("corrupt-receipt retry fetched"),
        )


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate"])
def test_idempotent_receipt_rejects_inexact_audit_table_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    dataset, plan_path, _plan, _before, _opens = _synthetic_apply(tmp_path, monkeypatch)
    repair.apply_plan(
        plan_path=plan_path,
        dataset=dataset,
        root=tmp_path,
        fetch=lambda _s, interval, open_ms: _body(open_ms, interval, "2.5"),
    )

    def mutate(tables: list[dict[str, object]]) -> None:
        if defect == "missing":
            tables.pop()
        elif defect == "extra":
            extra = deepcopy(tables[-1])
            extra["path"] = "EXTRAUSDT_1h.parquet"
            tables.append(extra)
        else:
            tables[1] = deepcopy(tables[0])

    _rewrite_committed_audit(dataset, mutate)
    with pytest.raises(repair.RepairError, match="audit"):
        repair.apply_plan(
            plan_path=plan_path,
            dataset=dataset,
            root=tmp_path,
            fetch=lambda *_a: pytest.fail("inexact-audit retry fetched"),
        )


def test_injected_publication_failure_rolls_back_exact_before_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset, plan_path, _plan, before, _opens = _synthetic_apply(tmp_path, monkeypatch)
    real_replace = repair.os.replace
    publications = 0

    def replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        nonlocal publications
        target = Path(destination)
        if target.parent == dataset and target.suffix == ".parquet":
            publications += 1
            if publications == 3:
                raise OSError("injected replace failure")
        real_replace(source, destination)

    monkeypatch.setattr(repair.os, "replace", replace)
    with pytest.raises(OSError, match="injected"):
        repair.apply_plan(
            plan_path=plan_path,
            dataset=dataset,
            root=tmp_path,
            fetch=lambda _s, interval, open_ms: _body(open_ms, interval, "2.5"),
        )
    assert all(repair._sha256(dataset / name) == digest for name, digest in before.items())
    assert not repair._receipt_path(dataset, "d" * 64).exists()


def test_recovery_fails_closed_on_unknown_third_hash(tmp_path: Path) -> None:
    dataset = tmp_path
    target = dataset / "A.parquet"
    backup = dataset / "backup.parquet"
    target.write_bytes(b"third")
    backup.write_bytes(b"before")
    journal = {
        "files": [
            {
                "path": target.name,
                "backup": backup.name,
                "before_sha256": hashlib.sha256(b"before").hexdigest(),
                "after_sha256": hashlib.sha256(b"after").hexdigest(),
            }
        ]
    }
    with pytest.raises(repair.RepairError, match="unknown third hash"):
        repair._rollback(journal, dataset=dataset)


@pytest.mark.parametrize("defect", ["missing", "extra", "duplicate"])
def test_recover_rejects_inexact_journal_before_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    dataset, plan_path, plan, _before, _opens = _synthetic_apply(tmp_path, monkeypatch)
    digest = "d" * 64
    bindings = {item["path"]: item for item in plan["current_state"]["parquets"]}
    affected = sorted({f"{row['table']}.parquet" for row in plan["coordinates"]})
    files = [
        {
            "path": path,
            "backup": f"repair_state/{digest}/backup/{path}",
            "before_sha256": bindings[path]["sha256"],
            "after_sha256": "e" * 64,
        }
        for path in affected
    ]
    if defect == "missing":
        files.pop()
    elif defect == "extra":
        files.append(deepcopy(files[-1]) | {"path": "EXTRAUSDT_1h.parquet"})
    else:
        files[1] = deepcopy(files[0])
    journal = {
        "schema_version": 1,
        "repair_id": repair.REPAIR_ID,
        "plan_sha256": digest,
        "state": "PREPARED",
        "files": files,
    }
    journal_path = repair._journal_path(dataset, digest)
    journal_path.parent.mkdir(parents=True)
    journal_path.write_bytes(repair._canonical(journal))
    monkeypatch.setattr(repair, "build_plan", lambda **_kwargs: (plan, b"", ""))
    monkeypatch.setattr(repair, "_rollback", lambda *_a, **_k: pytest.fail("rollback reached"))
    with pytest.raises(repair.RepairError, match="journal"):
        repair.recover(plan_path=plan_path, dataset=dataset, root=tmp_path)


def test_valid_complete_journal_rolls_back_all_64_files_and_repeats_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset, plan_path, plan, before, _opens = _synthetic_apply(tmp_path, monkeypatch)
    digest = "d" * 64
    bindings = {item["path"]: item for item in plan["current_state"]["parquets"]}
    affected = sorted({f"{row['table']}.parquet" for row in plan["coordinates"]})
    backup = dataset / "repair_state" / digest / "backup"
    backup.mkdir(parents=True)
    files: list[dict[str, object]] = []
    for path in affected:
        target = dataset / path
        backup_path = backup / path
        backup_path.write_bytes(target.read_bytes())
        target.write_bytes(f"after:{path}".encode())
        files.append(
            {
                "path": path,
                "backup": backup_path.relative_to(dataset).as_posix(),
                "before_sha256": bindings[path]["sha256"],
                "after_sha256": repair._sha256(target),
            }
        )
    journal = {
        "schema_version": 1,
        "repair_id": repair.REPAIR_ID,
        "plan_sha256": digest,
        "state": "PREPARED",
        "files": files,
    }
    repair._journal_path(dataset, digest).write_bytes(repair._canonical(journal))
    monkeypatch.setattr(repair, "build_plan", lambda **_kwargs: (plan, b"", ""))
    assert repair.recover(plan_path=plan_path, dataset=dataset, root=tmp_path) == "ROLLED_BACK"
    assert all(repair._sha256(dataset / name) == value for name, value in before.items())
    assert repair.recover(plan_path=plan_path, dataset=dataset, root=tmp_path) == "ROLLED_BACK"
    assert all(repair._sha256(dataset / name) == value for name, value in before.items())


def test_apply_uses_the_daily_update_lock(tmp_path: Path) -> None:
    dataset = tmp_path / "normalized_multi"
    dataset.mkdir()
    identity = hashlib.sha256(os.fsencode(dataset.resolve())).hexdigest()
    lock_path = Path(repair.tempfile.gettempdir()) / f"tios-daily-update-{identity}.lock"
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already running"):
            with repair._apply_guard(dataset):
                pass
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def test_recover_uses_the_daily_update_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "normalized_multi"
    dataset.mkdir()
    monkeypatch.setattr(repair, "_load_bound_plan", lambda *_a, **_k: ({}, "d" * 64))
    identity = hashlib.sha256(os.fsencode(dataset.resolve())).hexdigest()
    lock_path = Path(repair.tempfile.gettempdir()) / f"tios-daily-update-{identity}.lock"
    with lock_path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match="already running"):
            repair.recover(plan_path=tmp_path / "plan", dataset=dataset, root=tmp_path)
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def test_cli_has_no_url_or_dataset_override() -> None:
    parser = repair._parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["plan", "--url", "https://example.test"])
    with pytest.raises(SystemExit):
        parser.parse_args(["apply", "--plan", "x", "--dataset", "/tmp/x"])
