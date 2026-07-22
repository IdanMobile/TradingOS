"""Closed-bar, overlap, pagination, locking, and publication checks."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet
import pytest

from tios.dataset import daily_update as du
from tios.dataset.daily_update import _append_dedup, _klines_json_to_raw
from tios.dataset.normalize import to_canonical

HOUR_MS = 3_600_000
BASE_MS = 1_609_459_200_000


def _row(open_ms: int, close: str, *, close_ms: int | None = None) -> list[Any]:
    return [
        open_ms,
        "100",
        "110",
        "90",
        close,
        "5",
        close_ms if close_ms is not None else open_ms + HOUR_MS - 1,
        "500",
        42,
        "2",
        "200",
        "0",
    ]


def _canon(rows: list[list[Any]]) -> pa.Table:
    return to_canonical(_klines_json_to_raw(rows), "ms", "BTCUSDT", "1h")


def _write(path: Path, rows: list[list[Any]]) -> None:
    pyarrow.parquet.write_table(_canon(rows), path)


def _cutoff(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def _no_retain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        du,
        "_retain_page",
        lambda _symbol, _interval, start, rows: {"start": start, "rows": len(rows)},
    )


def _update_result(path: Path) -> dict[str, object]:
    return {
        "file": path.name,
        "added_rows": 0,
        "revised_rows": 0,
        "excluded_open_rows": 0,
        "resume_open_ms": BASE_MS,
        "parquet_directory_fsync": "CONFIRMED",
    }


def test_rest_row_converts_to_canonical() -> None:
    row = _canon([_row(BASE_MS, "101")]).to_pylist()[0]
    assert str(row["timestamp_open_utc"]) == "2021-01-01 00:00:00+00:00"
    assert row["open"] == Decimal("100") and row["close"] == Decimal("101")
    assert row["trade_count"] == 42


def test_append_dedup_prefers_fresh_overlap() -> None:
    existing = _canon([_row(BASE_MS, "101"), _row(BASE_MS + HOUR_MS, "102")])
    fresh = _canon([_row(BASE_MS + HOUR_MS, "999"), _row(BASE_MS + 2 * HOUR_MS, "103")])
    merged, dropped = _append_dedup(existing, fresh)
    assert dropped == 1
    assert merged.num_rows == 3
    assert merged.column("close").to_pylist() == [Decimal("101"), Decimal("999"), Decimal("103")]


def test_open_current_bar_is_retained_raw_but_excluded(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    pages = [[_row(BASE_MS, "109"), _row(BASE_MS + HOUR_MS, "110")]]
    retained: list[list[list[Any]]] = []
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: pages.pop(0))
    monkeypatch.setattr(
        du,
        "_retain_page",
        lambda _s, _i, _start, rows: retained.append(rows.copy()) or {"rows": len(rows)},
    )

    result = du.update_file(path, _cutoff(BASE_MS + HOUR_MS - 1))

    table = pyarrow.parquet.read_table(path)
    assert table.num_rows == 1
    assert table.column("close")[0].as_py() == Decimal("109")
    assert result["added_rows"] == 0 and result["revised_rows"] == 1
    assert len(retained[0]) == 2


def test_close_exactly_at_cutoff_is_accepted(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    close_ms = BASE_MS + HOUR_MS - 1
    _write(path, [_row(BASE_MS, "101", close_ms=close_ms)])
    monkeypatch.setattr(
        du, "fetch_klines", lambda *_args: [_row(BASE_MS, "109", close_ms=close_ms)]
    )
    _no_retain(monkeypatch)

    result = du.update_file(path, _cutoff(close_ms))

    assert result["revised_rows"] == 1
    assert pyarrow.parquet.read_table(path).column("close")[0].as_py() == Decimal("109")


def test_overlap_replacement_and_added_counts(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101"), _row(BASE_MS + HOUR_MS, "102")])
    page = [_row(BASE_MS + HOUR_MS, "109"), _row(BASE_MS + 2 * HOUR_MS, "103")]
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: page)
    _no_retain(monkeypatch)

    result = du.update_file(path, _cutoff(BASE_MS + 3 * HOUR_MS))

    table = pyarrow.parquet.read_table(path)
    assert result["added_rows"] == 1 and result["revised_rows"] == 1
    assert table.num_rows == 3
    assert table.column("close").to_pylist()[-2:] == [Decimal("109"), Decimal("103")]


def test_existing_and_incoming_open_rows_are_not_published(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    cutoff = BASE_MS + HOUR_MS - 1
    _write(
        path,
        [
            _row(BASE_MS, "101", close_ms=cutoff),
            _row(BASE_MS + HOUR_MS, "999", close_ms=cutoff + HOUR_MS),
        ],
    )
    page = [
        _row(BASE_MS, "101", close_ms=cutoff),
        _row(BASE_MS + HOUR_MS, "110", close_ms=cutoff + HOUR_MS),
    ]
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: page)
    _no_retain(monkeypatch)

    result = du.update_file(path, _cutoff(cutoff))

    table = pyarrow.parquet.read_table(path)
    assert result["excluded_open_rows"] == 1
    assert result["added_rows"] == 0 and result["revised_rows"] == 0
    assert table.num_rows == 1
    assert all(
        close <= _cutoff(cutoff) for close in table.column("close_timestamp_utc").to_pylist()
    )


def test_identical_overlap_is_not_revised_or_rewritten(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    row = _row(BASE_MS, "101")
    _write(path, [row])
    before = path.read_bytes()
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: [row])
    monkeypatch.setattr(
        du,
        "_atomic_write_parquet",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected rewrite")),
    )
    _no_retain(monkeypatch)

    result = du.update_file(path, _cutoff(BASE_MS + HOUR_MS))

    assert result["revised_rows"] == 0 and result["added_rows"] == 0
    assert path.read_bytes() == before


def test_forward_pagination_is_bounded_and_advances(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    monkeypatch.setattr(du, "PAGE_LIMIT", 2)
    calls: list[int] = []

    def fetch(_symbol: str, _interval: str, since: int, _limit: int) -> list[list[Any]]:
        calls.append(since)
        if len(calls) == 1:
            return [_row(BASE_MS, "109"), _row(BASE_MS + HOUR_MS, "102")]
        return [_row(BASE_MS + 2 * HOUR_MS, "103")]

    monkeypatch.setattr(du, "fetch_klines", fetch)
    _no_retain(monkeypatch)

    result = du.update_file(path, _cutoff(BASE_MS + 4 * HOUR_MS))

    assert calls == [BASE_MS, BASE_MS + HOUR_MS + 1]
    assert result["added_rows"] == 2 and result["revised_rows"] == 1
    assert pyarrow.parquet.read_table(path).num_rows == 3


def test_nonadvancing_full_page_fails_without_data_loss(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    before = path.read_bytes()
    monkeypatch.setattr(du, "PAGE_LIMIT", 1)
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: [_row(BASE_MS - HOUR_MS, "100")])
    _no_retain(monkeypatch)

    with pytest.raises(ValueError, match="did not advance"):
        du.update_file(path, _cutoff(BASE_MS + HOUR_MS))

    assert path.read_bytes() == before


def test_page_bound_exhaustion_fails_without_data_loss(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    row = _row(BASE_MS, "101")
    _write(path, [row])
    before = path.read_bytes()
    monkeypatch.setattr(du, "PAGE_LIMIT", 1)
    monkeypatch.setattr(du, "MAX_PAGES_PER_FILE", 1)
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: [row])
    _no_retain(monkeypatch)

    with pytest.raises(RuntimeError, match="pagination exceeded"):
        du.update_file(path, _cutoff(BASE_MS + HOUR_MS))

    assert path.read_bytes() == before


def test_oversized_page_and_malformed_row_fail_before_publication(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    before = path.read_bytes()
    monkeypatch.setattr(du, "PAGE_LIMIT", 1)
    monkeypatch.setattr(
        du,
        "fetch_klines",
        lambda *_args: [_row(BASE_MS, "101"), _row(BASE_MS + HOUR_MS, "102")],
    )
    _no_retain(monkeypatch)
    with pytest.raises(ValueError, match="exceeded limit"):
        du.update_file(path, _cutoff(BASE_MS + 2 * HOUR_MS))
    assert path.read_bytes() == before

    monkeypatch.setattr(du, "fetch_klines", lambda *_args: [[]])
    with pytest.raises(ValueError, match="malformed REST page"):
        du.update_file(path, _cutoff(BASE_MS + HOUR_MS))
    assert path.read_bytes() == before

    monkeypatch.setattr(du, "fetch_klines", lambda *_args: [[BASE_MS]])
    with pytest.raises(ValueError, match="malformed REST page"):
        du.update_file(path, _cutoff(BASE_MS + HOUR_MS))
    assert path.read_bytes() == before


def test_naive_cutoff_is_rejected(tmp_path) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    with pytest.raises(ValueError, match="timezone-aware"):
        du.update_file(path, datetime(2021, 1, 1))


def test_fetch_failure_does_not_publish_accumulated_rows(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    before = path.read_bytes()
    monkeypatch.setattr(du, "PAGE_LIMIT", 1)
    calls = 0

    def fetch(*_args: object) -> list[list[Any]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [_row(BASE_MS, "109")]
        raise OSError("network failed")

    monkeypatch.setattr(du, "fetch_klines", fetch)
    _no_retain(monkeypatch)

    with pytest.raises(OSError, match="network failed"):
        du.update_file(path, _cutoff(BASE_MS + HOUR_MS))

    assert path.read_bytes() == before


def test_atomic_replace_failure_preserves_old_parquet(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    _write(path, [_row(BASE_MS, "101")])
    before = path.read_bytes()
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: [_row(BASE_MS, "109")])
    _no_retain(monkeypatch)
    monkeypatch.setattr(du.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace")))

    with pytest.raises(OSError, match="replace"):
        du.update_file(path, _cutoff(BASE_MS + HOUR_MS))

    assert path.read_bytes() == before
    assert not list(tmp_path.glob(".BTCUSDT_1h.parquet.*"))


def test_process_lock_refuses_concurrent_holder(tmp_path) -> None:
    with du._process_lock(tmp_path):
        with pytest.raises(RuntimeError, match="already running"):
            with du._process_lock(tmp_path):
                pass
    assert not (tmp_path / ".daily_update.lock").exists()


def test_rest_page_is_retained_by_content_hash(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(du, "RAW_REST_ROOT", tmp_path / "rest_klines")
    rows = [_row(BASE_MS, "101")]
    ref = du._retain_page("BTCUSDT", "1h", BASE_MS, rows)
    path = du.RAW_REST_ROOT.parent / ref["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ref["sha256"]
    assert ref["rows"] == 1


def test_atomic_status_bytes_never_replace_destination_on_failure(tmp_path, monkeypatch) -> None:
    path = tmp_path / "status.json"
    path.write_text("old")
    monkeypatch.setattr(du.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("replace")))

    with pytest.raises(OSError, match="replace"):
        du._atomic_write_bytes(path, b"new")

    assert path.read_text() == "old"


def test_directory_fsync_failure_reports_degraded_after_committed_replace(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "status.json"
    path.write_text("old")
    monkeypatch.setattr(du, "_fsync_directory", lambda _path: False)

    synced = du._atomic_write_bytes(path, b"new")

    assert synced is False
    assert path.read_bytes() == b"new"


def test_manifest_current_and_archive_match(tmp_path) -> None:
    result: dict[str, object] = {"schema_version": 2, "tables": {}}
    archive, archive_synced, current_synced = du._publish_manifest(tmp_path, result)
    current = tmp_path / "normalized_multi_manifest.json"
    assert archive.read_bytes() == current.read_bytes()
    assert json.loads(current.read_text()) == result
    assert archive_synced and current_synced


def test_manifest_archive_failure_leaves_current_unchanged(tmp_path, monkeypatch) -> None:
    current = tmp_path / "normalized_multi_manifest.json"
    current.write_text("old")
    original = du._atomic_write_bytes

    def fail_archive(path: Path, content: bytes) -> bool:
        if path.parent.name == "manifests":
            raise OSError("archive")
        return original(path, content)

    monkeypatch.setattr(du, "_atomic_write_bytes", fail_archive)
    with pytest.raises(OSError, match="archive"):
        du._publish_manifest(tmp_path, {"tables": {}})
    assert current.read_text() == "old"


def test_manifest_current_failure_retains_archive_and_old_current(tmp_path, monkeypatch) -> None:
    current = tmp_path / "normalized_multi_manifest.json"
    current.write_text("old")
    original = du._atomic_write_bytes

    def fail_current(path: Path, content: bytes) -> bool:
        if path.name == "normalized_multi_manifest.json":
            raise OSError("current")
        return original(path, content)

    monkeypatch.setattr(du, "_atomic_write_bytes", fail_current)
    with pytest.raises(OSError, match="current"):
        du._publish_manifest(tmp_path, {"tables": {}})
    assert current.read_text() == "old"
    assert len(list((tmp_path / "manifests").glob("*.json"))) == 1


def test_main_passes_one_cutoff_to_every_file(tmp_path, monkeypatch) -> None:
    from tios.dataset import normalize_multi

    paths = [tmp_path / "BTCUSDT_1h.parquet", tmp_path / "ETHUSDT_1h.parquet"]
    for path in paths:
        path.touch()
    observed: list[datetime] = []

    def update(path: Path, cutoff: datetime, _resume: int | None) -> dict[str, object]:
        observed.append(cutoff)
        return _update_result(path)

    monkeypatch.setattr(du, "DEFAULT_DIR", tmp_path)
    monkeypatch.setattr(du, "update_file", update)
    monkeypatch.setattr(
        normalize_multi,
        "snapshot_existing",
        lambda: {
            "schema_version": 2,
            "tables": {path.stem: {"rest_update_source": {}} for path in paths},
        },
    )

    du.main()

    assert len(observed) == 2
    assert observed[0] is observed[1]
    assert observed[0].tzinfo is UTC
    status = json.loads((tmp_path / "daily_update_status.json").read_text())
    assert status["closed_bar_cutoff_utc"] == observed[0].isoformat()
    manifest = json.loads((tmp_path / "normalized_multi_manifest.json").read_text())
    for info in manifest["tables"].values():
        lineage = info["rest_update_source"]
        assert lineage["reported_revised_rows"] == 0
        status_path = tmp_path / lineage["status_manifest"]["path"]
        assert status_path.parent.name == "statuses" and status_path.exists()


def test_snapshot_failure_publishes_no_manifest(tmp_path, monkeypatch) -> None:
    from tios.dataset import normalize_multi

    path = tmp_path / "BTCUSDT_1h.parquet"
    path.touch()
    monkeypatch.setattr(du, "DEFAULT_DIR", tmp_path)
    monkeypatch.setattr(du, "update_file", lambda path, _cutoff, _resume: _update_result(path))
    monkeypatch.setattr(
        normalize_multi,
        "snapshot_existing",
        lambda: (_ for _ in ()).throw(RuntimeError("snapshot")),
    )

    with pytest.raises(RuntimeError, match="snapshot"):
        du.main()

    assert (tmp_path / "daily_update_status.json").exists()
    assert len(list((tmp_path / "statuses").glob("*.json"))) == 1
    assert not (tmp_path / "normalized_multi_manifest.json").exists()


def test_status_archive_failure_leaves_current_status_but_no_manifest(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    path.touch()
    monkeypatch.setattr(du, "DEFAULT_DIR", tmp_path)
    monkeypatch.setattr(du, "update_file", lambda path, _cutoff, _resume: _update_result(path))
    monkeypatch.setattr(
        du,
        "_archive_status",
        lambda *_args: (_ for _ in ()).throw(OSError("status archive")),
    )

    with pytest.raises(OSError, match="status archive"):
        du.main()

    assert (tmp_path / "daily_update_status.json").exists()
    assert not (tmp_path / "normalized_multi_manifest.json").exists()


def test_status_failure_publishes_no_status_archive_or_manifest(tmp_path, monkeypatch) -> None:
    path = tmp_path / "BTCUSDT_1h.parquet"
    path.touch()
    monkeypatch.setattr(du, "DEFAULT_DIR", tmp_path)
    monkeypatch.setattr(du, "update_file", lambda path, _cutoff, _resume: _update_result(path))
    original = du._atomic_write_bytes

    def fail_status(path: Path, content: bytes) -> bool:
        if path.name == "daily_update_status.json":
            raise OSError("status")
        return original(path, content)

    monkeypatch.setattr(du, "_atomic_write_bytes", fail_status)
    with pytest.raises(OSError, match="status"):
        du.main()

    assert not (tmp_path / "daily_update_status.json").exists()
    assert not (tmp_path / "statuses").exists()
    assert not (tmp_path / "normalized_multi_manifest.json").exists()


def test_main_all_open_file_publishes_empty_snapshot_safely(tmp_path, monkeypatch) -> None:
    from tios.dataset import normalize_multi

    target, raw = tmp_path / "normalized", tmp_path / "raw"
    target.mkdir()
    path = target / "BTCUSDT_1h.parquet"
    cutoff_ms = BASE_MS + HOUR_MS - 1
    open_row = _row(BASE_MS, "101", close_ms=cutoff_ms + HOUR_MS)
    closed_row = _row(BASE_MS, "109", close_ms=cutoff_ms + HOUR_MS)
    _write(path, [open_row])

    class FixedDatetime(datetime):
        current_ms = cutoff_ms

        @classmethod
        def now(cls, tz=None):
            return _cutoff(cls.current_ms)

    monkeypatch.setattr(du, "datetime", FixedDatetime)
    monkeypatch.setattr(du, "DEFAULT_DIR", target)
    monkeypatch.setattr(du, "RAW_REST_ROOT", raw / "rest_klines")
    pages = [[open_row], [closed_row]]
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: pages.pop(0))
    monkeypatch.setattr(normalize_multi, "NORM_ROOT", target)
    monkeypatch.setattr(normalize_multi, "NORM_MANIFEST", target / "normalized_multi_manifest.json")
    monkeypatch.setattr(normalize_multi, "RAW_ROOT", raw)

    du.main()

    assert pyarrow.parquet.read_table(path).num_rows == 0
    manifest = json.loads((target / "normalized_multi_manifest.json").read_text())
    info = manifest["tables"]["BTCUSDT_1h"]
    assert info["rows"] == 0
    assert info["coverage_start_utc"] is None
    assert info["coverage_end_utc"] is None
    assert info["rest_update_source"]["reported_excluded_open_rows"] == 1

    FixedDatetime.current_ms = cutoff_ms + HOUR_MS
    du.main()

    recovered = pyarrow.parquet.read_table(path)
    assert recovered.num_rows == 1
    assert recovered.column("close")[0].as_py() == Decimal("109")
    status = json.loads((target / "daily_update_status.json").read_text())
    assert status["updated"][0]["resume_open_ms"] == BASE_MS


def test_empty_parquet_recovers_after_status_publication_failure(tmp_path, monkeypatch) -> None:
    from tios.dataset import normalize_multi

    target, raw = tmp_path / "normalized", tmp_path / "raw"
    target.mkdir()
    path = target / "BTCUSDT_1h.parquet"
    cutoff_ms = BASE_MS + HOUR_MS - 1
    open_row = _row(BASE_MS, "101", close_ms=cutoff_ms + HOUR_MS)
    closed_row = _row(BASE_MS, "109", close_ms=cutoff_ms + HOUR_MS)
    _write(path, [open_row])

    class FixedDatetime(datetime):
        current_ms = cutoff_ms

        @classmethod
        def now(cls, tz=None):
            return _cutoff(cls.current_ms)

    monkeypatch.setattr(du, "datetime", FixedDatetime)
    monkeypatch.setattr(du, "DEFAULT_DIR", target)
    monkeypatch.setattr(du, "RAW_REST_ROOT", raw / "rest_klines")
    pages = [[open_row], [closed_row]]
    monkeypatch.setattr(du, "fetch_klines", lambda *_args: pages.pop(0))
    monkeypatch.setattr(normalize_multi, "NORM_ROOT", target)
    monkeypatch.setattr(normalize_multi, "NORM_MANIFEST", target / "normalized_multi_manifest.json")
    monkeypatch.setattr(normalize_multi, "RAW_ROOT", raw)
    original_write = du._atomic_write_bytes

    def fail_current_status(path: Path, content: bytes) -> bool:
        if path.name == "daily_update_status.json":
            raise OSError("status crash")
        return original_write(path, content)

    monkeypatch.setattr(du, "_atomic_write_bytes", fail_current_status)
    with pytest.raises(OSError, match="status crash"):
        du.main()

    committed = pyarrow.parquet.read_table(path)
    assert committed.num_rows == 0
    assert committed.schema.metadata[du._META_CURSOR] == str(BASE_MS).encode()
    assert not (target / "daily_update_status.json").exists()

    monkeypatch.setattr(du, "_atomic_write_bytes", original_write)
    FixedDatetime.current_ms = cutoff_ms + HOUR_MS
    du.main()

    recovered = pyarrow.parquet.read_table(path)
    assert recovered.num_rows == 1
    assert recovered.column("close")[0].as_py() == Decimal("109")


def test_first_empty_file_recovers_after_later_file_fetch_failure(tmp_path, monkeypatch) -> None:
    from tios.dataset import normalize_multi

    target, raw = tmp_path / "normalized", tmp_path / "raw"
    target.mkdir()
    first = target / "AAVEUSDT_1h.parquet"
    second = target / "BTCUSDT_1h.parquet"
    cutoff_ms = BASE_MS + HOUR_MS - 1
    open_row = _row(BASE_MS, "101", close_ms=cutoff_ms + HOUR_MS)
    closed_row = _row(BASE_MS, "109", close_ms=cutoff_ms + HOUR_MS)
    _write(first, [open_row])
    _write(second, [open_row])

    class FixedDatetime(datetime):
        current_ms = cutoff_ms

        @classmethod
        def now(cls, tz=None):
            return _cutoff(cls.current_ms)

    run = 1

    def fetch(symbol: str, *_args) -> list[list[Any]]:
        if run == 1 and symbol == "BTCUSDT":
            raise OSError("later file failed")
        return [open_row if run == 1 else closed_row]

    monkeypatch.setattr(du, "datetime", FixedDatetime)
    monkeypatch.setattr(du, "DEFAULT_DIR", target)
    monkeypatch.setattr(du, "RAW_REST_ROOT", raw / "rest_klines")
    monkeypatch.setattr(du, "fetch_klines", fetch)
    monkeypatch.setattr(normalize_multi, "NORM_ROOT", target)
    monkeypatch.setattr(normalize_multi, "NORM_MANIFEST", target / "normalized_multi_manifest.json")
    monkeypatch.setattr(normalize_multi, "RAW_ROOT", raw)

    with pytest.raises(OSError, match="later file failed"):
        du.main()
    assert pyarrow.parquet.read_table(first).num_rows == 0
    assert (
        pyarrow.parquet.read_table(first).schema.metadata[du._META_CURSOR] == str(BASE_MS).encode()
    )
    assert not (target / "daily_update_status.json").exists()

    run = 2
    FixedDatetime.current_ms = cutoff_ms + HOUR_MS
    du.main()

    assert pyarrow.parquet.read_table(first).column("close")[0].as_py() == Decimal("109")
    assert pyarrow.parquet.read_table(second).column("close")[0].as_py() == Decimal("109")


def test_nonempty_embedded_cursor_supersedes_stale_status_after_partial_run(
    tmp_path, monkeypatch
) -> None:
    from tios.dataset import normalize_multi

    target, raw = tmp_path / "normalized", tmp_path / "raw"
    target.mkdir()
    first = target / "AAVEUSDT_1h.parquet"
    second = target / "BTCUSDT_1h.parquet"
    initial = _row(BASE_MS, "101")
    added = _row(BASE_MS + HOUR_MS, "102")
    _write(first, [initial])
    _write(second, [initial])
    (target / "daily_update_status.json").write_text(
        json.dumps(
            {
                "updated": [
                    {"file": first.name, "resume_open_ms": BASE_MS},
                    {"file": second.name, "resume_open_ms": BASE_MS},
                ]
            }
        )
    )

    run = 1

    def fetch(symbol: str, *_args) -> list[list[Any]]:
        if run == 1 and symbol == "BTCUSDT":
            raise OSError("later file failed")
        if symbol == "AAVEUSDT":
            return [initial, added] if run == 1 else [added]
        return [initial]

    monkeypatch.setattr(du, "DEFAULT_DIR", target)
    monkeypatch.setattr(du, "RAW_REST_ROOT", raw / "rest_klines")
    monkeypatch.setattr(du, "fetch_klines", fetch)
    monkeypatch.setattr(normalize_multi, "NORM_ROOT", target)
    monkeypatch.setattr(normalize_multi, "NORM_MANIFEST", target / "normalized_multi_manifest.json")
    monkeypatch.setattr(normalize_multi, "RAW_ROOT", raw)

    with pytest.raises(OSError, match="later file failed"):
        du.main()
    retained = pyarrow.parquet.read_table(first)
    assert retained.num_rows == 2
    assert retained.schema.metadata[du._META_CURSOR] == str(BASE_MS + HOUR_MS).encode()
    stale_status = json.loads((target / "daily_update_status.json").read_text())
    assert stale_status["updated"][0]["resume_open_ms"] == BASE_MS

    run = 2
    du.main()

    assert pyarrow.parquet.read_table(first).num_rows == 2
    assert pyarrow.parquet.read_table(second).num_rows == 1


def test_empty_parquet_refresh_metadata_missing_corrupt_or_conflicting_fails_closed(
    tmp_path, monkeypatch
) -> None:
    cutoff = _cutoff(BASE_MS + HOUR_MS)
    empty = _canon([_row(BASE_MS, "101")]).slice(0, 0)
    path = tmp_path / "BTCUSDT_1h.parquet"
    pyarrow.parquet.write_table(empty, path)
    monkeypatch.setattr(
        du,
        "fetch_klines",
        lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
    )
    with pytest.raises(ValueError, match="lacks committed refresh metadata"):
        du.update_file(path, cutoff)

    corrupt = empty.replace_schema_metadata(
        {
            du._META_VERSION: b"1",
            du._META_CURSOR: b"not-an-integer",
            du._META_CUTOFF: cutoff.isoformat().encode(),
        }
    )
    pyarrow.parquet.write_table(corrupt, path)
    with pytest.raises(ValueError, match="metadata is malformed"):
        du.update_file(path, cutoff)

    valid = du._with_refresh_metadata(empty, BASE_MS, cutoff)
    pyarrow.parquet.write_table(valid, path)
    with pytest.raises(ValueError, match="status/parquet refresh cursor conflict"):
        du.update_file(path, cutoff, BASE_MS + 1)


def test_embedded_cursor_cannot_exceed_exact_millisecond_cutoff() -> None:
    empty = _canon([_row(BASE_MS, "101")]).slice(0, 0)
    cutoff_2021 = datetime(2021, 1, 1, tzinfo=UTC)
    cursor_2030 = int(datetime(2030, 1, 1, tzinfo=UTC).timestamp()) * 1000
    malicious = du._with_refresh_metadata(empty, cursor_2030, cutoff_2021)
    with pytest.raises(ValueError, match="later than its embedded cutoff"):
        du._embedded_refresh_cursor(malicious, datetime(2031, 1, 1, tzinfo=UTC))

    exact = du._with_refresh_metadata(empty, BASE_MS, cutoff_2021)
    assert du._embedded_refresh_cursor(exact, cutoff_2021) == BASE_MS

    submillisecond = cutoff_2021.replace(microsecond=999)
    still_exact_ms = du._with_refresh_metadata(empty, BASE_MS, submillisecond)
    assert du._embedded_refresh_cursor(still_exact_ms, submillisecond) == BASE_MS
    one_ms_late = du._with_refresh_metadata(empty, BASE_MS + 1, submillisecond)
    with pytest.raises(ValueError, match="later than its embedded cutoff"):
        du._embedded_refresh_cursor(one_ms_late, datetime(2031, 1, 1, tzinfo=UTC))
