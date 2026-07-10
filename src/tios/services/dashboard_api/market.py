"""Read-only market and retained-trade projection for the dashboard."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import duckdb

SYMBOLS = {"BTCUSDT": "BTC/USDT", "ETHUSDT": "ETH/USDT"}
INTERVALS = {"5m", "15m", "1h"}
ANCHORS = {"evidence", "latest"}


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError(f"artifact manifest is missing or malformed: {path.name}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"artifact manifest is malformed: {path.name}")
    return cast(dict[str, Any], payload)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as artifact:
            while chunk := artifact.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise ValueError(f"artifact is unavailable: {path.name}") from error
    return digest.hexdigest()


def _expected_hash(manifest: dict[str, Any], artifact_name: str) -> str:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("fill manifest files are missing")
    match = next(
        (row for row in files if isinstance(row, dict) and row.get("path") == artifact_name),
        None,
    )
    expected = match.get("sha256") if match else None
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f"fill manifest hash is missing for {artifact_name}")
    return expected


def build_market_snapshot(
    root: Path,
    symbol: str = "BTCUSDT",
    interval: str = "5m",
    limit: int = 240,
    anchor: str = "evidence",
) -> dict[str, Any]:
    """Return canonical candles and matching retained backtest fills."""
    if symbol not in SYMBOLS:
        raise ValueError(f"unsupported symbol: {symbol}")
    if interval not in INTERVALS:
        raise ValueError(f"unsupported interval: {interval}")
    if not 50 <= limit <= 1000:
        raise ValueError("limit must be between 50 and 1000")
    if anchor not in ANCHORS:
        raise ValueError(f"unsupported anchor: {anchor}")

    dataset_manifest_path = (
        root / "artifacts" / "datasets" / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
    )
    dataset_manifest = _json(dataset_manifest_path)
    dataset_id = dataset_manifest.get("dataset_id")
    source = dataset_manifest.get("source")
    tables = dataset_manifest.get("tables")
    table_key = f"{symbol}_{interval}"
    table = tables.get(table_key) if isinstance(tables, dict) else None
    if (
        not isinstance(dataset_id, str)
        or not isinstance(source, str)
        or not isinstance(table, dict)
    ):
        raise ValueError("frozen dataset manifest does not match the requested market")
    parquet_name = table.get("parquet")
    candle_hash = table.get("parquet_sha256")
    if parquet_name != f"{table_key}.parquet" or not isinstance(candle_hash, str):
        raise ValueError("frozen dataset manifest candle identity is invalid")
    candle_path = root / "data" / "normalized" / parquet_name
    if _sha256(candle_path) != candle_hash:
        raise ValueError("canonical candle artifact hash does not match its manifest")

    fill_root = root / "artifacts" / "validation" / "B2_F0_S0" / "runs" / "holdout"
    trades_path = fill_root / "trades.parquet"
    fill_manifest_path = fill_root / "manifest.json"
    fill_status = "MISSING"
    fill_hash: str | None = None
    if trades_path.exists() != fill_manifest_path.exists():
        raise ValueError("retained fill artifact and manifest are incomplete")
    if trades_path.exists():
        fill_manifest = _json(fill_manifest_path)
        fill_hash = _expected_hash(fill_manifest, trades_path.name)
        if fill_manifest.get("status") != "OK" or fill_manifest.get("dataset_id") != dataset_id:
            raise ValueError("retained fill manifest status or dataset linkage is invalid")
        if _sha256(trades_path) != fill_hash:
            raise ValueError("retained fill artifact hash does not match its manifest")
        fill_status = "VERIFIED"

    connection = duckdb.connect()
    try:
        end_epoch = None
        if anchor == "evidence" and fill_status == "VERIFIED":
            result = connection.execute(
                "SELECT max(epoch(ts_fill)) FROM read_parquet(?) WHERE pair = ?",
                [str(trades_path), SYMBOLS[symbol]],
            ).fetchone()
            end_epoch = result[0] if result else None
        rows = connection.execute(
            """
            SELECT CAST(epoch(timestamp_open_utc) AS BIGINT),
                   CAST(open AS DOUBLE), CAST(high AS DOUBLE), CAST(low AS DOUBLE),
                   CAST(close AS DOUBLE), CAST(volume_base AS DOUBLE)
            FROM read_parquet(?)
            WHERE (? IS NULL OR epoch(timestamp_open_utc) <= ?)
            ORDER BY timestamp_open_utc DESC
            LIMIT ?
            """,
            [str(candle_path), end_epoch, end_epoch, limit],
        ).fetchall()
        rows.reverse()
        candles = [
            {
                "time": row[0],
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            }
            for row in rows
        ]

        markers: list[dict[str, Any]] = []
        if candles and fill_status == "VERIFIED":
            fills = connection.execute(
                """
                SELECT CAST(epoch(ts_fill) AS BIGINT), side, CAST(price AS DOUBLE),
                       CAST(qty AS DOUBLE), trade_id
                FROM read_parquet(?)
                WHERE pair = ? AND epoch(ts_fill) BETWEEN ? AND ?
                ORDER BY ts_fill
                LIMIT 500
                """,
                [
                    str(trades_path),
                    SYMBOLS[symbol],
                    candles[0]["time"],
                    candles[-1]["time"],
                ],
            ).fetchall()
            markers = [
                {
                    "time": row[0],
                    "side": row[1],
                    "price": row[2],
                    "qty": row[3],
                    "trade_id": row[4],
                    "environment": "backtest",
                    "strategy": "B2MaCrossover",
                }
                for row in fills
            ]
            if not markers:
                fill_status = "VERIFIED_NO_MATCHING_FILLS"
    finally:
        connection.close()
    if not markers and fill_status == "VERIFIED":
        fill_status = "VERIFIED_NO_MATCHING_FILLS"

    return {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "symbol": symbol,
        "interval": interval,
        "anchor": anchor,
        "dataset": dataset_id,
        "source": source,
        "freshness": "HISTORICAL_FROZEN",
        "candles": candles,
        "markers": markers,
        "capabilities": {
            "market_chart": "AVAILABLE" if candles else "NOT_AVAILABLE",
            "trade_markers": "AVAILABLE" if markers else "NOT_AVAILABLE",
            "take_profit_stop_loss": "NOT_AVAILABLE",
            "paper_orders": "DISABLED",
            "live_orders": "DISABLED",
        },
        "evidence": {
            "candles": str(candle_path.relative_to(root)),
            "fills": str(trades_path.relative_to(root)) if fill_status != "MISSING" else None,
        },
        "provenance": {
            "dataset_manifest": {
                "path": str(dataset_manifest_path.relative_to(root)),
                "status": "VERIFIED",
                "dataset_id": dataset_id,
                "source": source,
                "frozen_at": dataset_manifest.get("frozen_utc"),
            },
            "candle_artifact": {
                "path": str(candle_path.relative_to(root)),
                "status": "VERIFIED",
                "sha256": candle_hash,
                "manifest_key": table_key,
            },
            "fill_artifact": {
                "path": (str(trades_path.relative_to(root)) if fill_status != "MISSING" else None),
                "manifest": (
                    str(fill_manifest_path.relative_to(root)) if fill_status != "MISSING" else None
                ),
                "status": fill_status,
                "sha256": fill_hash,
                "matching_fills": len(markers),
            },
        },
    }
