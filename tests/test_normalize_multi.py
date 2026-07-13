"""Check the multi-dataset normalizer's missing-data handling (no network).

The new logic beyond the reused, already-tested primitives is: a pair/interval with
no downloaded months yields None (not a crash), so coins listed mid-window don't
break a normalize run. Fixture-free — uses a symbol that will never have raw files.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet

from tios.dataset import normalize_multi as nm
from tios.dataset.normalize import CANONICAL_SCHEMA


def test_absent_pair_returns_none() -> None:
    assert nm.normalize_pair("NOSUCHCOINUSDT", "1d") is None


def test_scope_constants_are_wired() -> None:
    # The normalizer walks the same pair/timeframe scope the acquirer downloads.
    assert "BTCUSDT" in nm.TOP_PAIRS and "ETHUSDT" in nm.TOP_PAIRS
    assert nm.TIMEFRAMES == ("1m", "5m", "15m", "1h", "4h", "1d")


def test_existing_snapshot_records_output_range_hashes_and_source_refs(
    tmp_path, monkeypatch
) -> None:
    norm, raw = tmp_path / "normalized", tmp_path / "raw"
    norm.mkdir()
    source = raw / "klines" / "BTCUSDT" / "1h" / "BTCUSDT-1h-2021-01.zip"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"raw")
    row = {
        "timestamp_open_utc": [0],
        "open": [1],
        "high": [1],
        "low": [1],
        "close": [1],
        "volume_base": [1],
        "close_timestamp_utc": [1],
        "quote_volume": [1],
        "trade_count": [1],
        "taker_buy_base_volume": [1],
        "taker_buy_quote_volume": [1],
        "source": ["binance-public-data:spot/monthly/klines"],
        "instrument": ["BTCUSDT"],
        "interval": ["1h"],
    }
    table = pa.table(row, schema=CANONICAL_SCHEMA)
    parquet = norm / "BTCUSDT_1h.parquet"
    pyarrow.parquet.write_table(table, parquet)
    (norm / "daily_update_status.json").write_text(
        json.dumps(
            {
                "last_run_utc": datetime.now(tz=UTC).isoformat(),
                "updated": [{"file": parquet.name, "added_rows": 1}],
            }
        )
    )
    monkeypatch.setattr(nm, "NORM_ROOT", norm)
    monkeypatch.setattr(nm, "NORM_MANIFEST", norm / "normalized_multi_manifest.json")
    monkeypatch.setattr(nm, "RAW_ROOT", raw)

    snapshot = nm.snapshot_existing()
    info = snapshot["tables"]["BTCUSDT_1h"]
    assert snapshot["lineage_status"] == "reconstructed_from_retained_files"
    assert info["parquet_sha256"] == hashlib.sha256(parquet.read_bytes()).hexdigest()
    assert info["coverage_start_utc"] == "1970-01-01 00:00:00+00:00"
    assert info["source_files"][0]["path"] == "klines/BTCUSDT/1h/BTCUSDT-1h-2021-01.zip"
    assert info["source_files"][0]["sha256"] == hashlib.sha256(b"raw").hexdigest()
    assert info["rest_update_source"]["payloads_retained"] is False
    assert "REST append response payloads were not retained" in snapshot["lineage_limitation"]

    archive = nm.write_manifest(snapshot)
    assert archive.exists()
    assert nm.write_manifest(snapshot) == archive
    assert archive.stem.endswith(hashlib.sha256(archive.read_bytes()).hexdigest())
    assert json.loads(nm.NORM_MANIFEST.read_text())["tables"]["BTCUSDT_1h"] == info
    assert nm.verify_manifest() == []

    source.write_bytes(b"drift")
    assert nm.verify_manifest() == [f"sha256 mismatch: {source}"]
