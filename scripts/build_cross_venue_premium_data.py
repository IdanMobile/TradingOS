"""Build the normalized, performance-free D-075 data package."""

from __future__ import annotations

import base64
import bisect
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Context, Decimal, localcontext
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RAW_BUNDLE = ROOT / "data/raw/coinbase_exchange/cross_venue_premium_v1.json"
BINANCE_PARQUET = ROOT / "data/normalized/BTCUSDT_1h.parquet"
DOSSIER = ROOT / "research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V8.md"
NORMALIZED = ROOT / "data/normalized/cross_venue_btc_premium_1h_v1.parquet"
PACKAGE = ROOT / "research/CROSS_VENUE_BTC_PREMIUM_DATA_PACKAGE_V1.json"
START = datetime(2021, 5, 1, tzinfo=UTC)
END_EXCLUSIVE = datetime(2026, 7, 1, tzinfo=UTC)
ONE_HOUR = timedelta(hours=1)
SOURCE_CLOSE_OFFSET = ONE_HOUR - timedelta(microseconds=1)
LN_QUANTUM = Decimal("0.000000000000000001")

SCHEMA = pa.schema(
    [
        pa.field("timestamp_open_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("source_close_utc", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("coinbase_btcusd_close", pa.decimal128(38, 8), nullable=False),
        pa.field("coinbase_usdtusd_close", pa.decimal128(38, 8), nullable=False),
        pa.field("binance_btcusdt_open", pa.decimal128(38, 8), nullable=False),
        pa.field("binance_btcusdt_close", pa.decimal128(38, 8), nullable=False),
        pa.field("coinbase_implied_btcusdt", pa.decimal128(38, 8), nullable=False),
        pa.field("log_premium", pa.decimal128(38, 18), nullable=False),
    ]
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _decode_body(item: dict[str, Any]) -> bytes:
    body = base64.b64decode(item["body_base64"], validate=True)
    if len(body) != item["body_bytes"] or sha256_bytes(body) != item["body_sha256"]:
        raise RuntimeError(f"raw response byte mismatch: {item['url']}")
    if item["status"] != 200:
        raise RuntimeError(f"non-200 retained response: {item['url']}")
    return body


def load_raw_bundle(path: Path = RAW_BUNDLE) -> dict[str, Any]:
    bundle: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if bundle.get("schema") != "tios-coinbase-cross-venue-raw-bundle-v1":
        raise ValueError("unsupported Coinbase raw bundle")
    safety = bundle.get("safety", {})
    if safety.get("authenticated") or safety.get("secrets_used"):
        raise ValueError("authenticated source bundle is prohibited")
    if safety.get("performance_computed") or safety.get("execution_authority") != "NONE":
        raise ValueError("source bundle cannot contain performance or authority")
    return bundle


def _validate_sources(bundle: dict[str, Any]) -> dict[str, str]:
    products: dict[str, str] = {}
    docs = 0
    for source in bundle["sources"]:
        body = _decode_body(source)
        if source["kind"] == "OFFICIAL_DOCUMENTATION":
            if b"Coinbase" not in body and b"coinbase" not in body:
                raise RuntimeError("official documentation identity missing")
            docs += 1
        elif source["kind"] == "PRODUCT_IDENTITY":
            payload = json.loads(body, parse_float=Decimal)
            product = source["product_id"]
            if payload.get("id") != product or payload.get("status") != "online":
                raise RuntimeError(f"invalid product identity: {product}")
            products[product] = source["body_sha256"]
    if docs != 2 or set(products) != {"BTC-USD", "USDT-USD"}:
        raise RuntimeError("incomplete Coinbase source identities")
    return products


def _decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _validate_candle(row: list[object], product: str) -> tuple[int, tuple[Decimal, ...]]:
    if len(row) != 6:
        raise RuntimeError(f"unexpected Coinbase candle width: {product}")
    if not isinstance(row[0], int):
        raise RuntimeError(f"invalid Coinbase candle timestamp: {product}")
    timestamp = row[0]
    if timestamp % 3600:
        raise RuntimeError(f"non-hour Coinbase timestamp: {product} {timestamp}")
    low, high, opened, closed, volume = (_decimal(value) for value in row[1:])
    if low <= 0 or high <= 0 or opened <= 0 or closed <= 0 or volume < 0:
        raise RuntimeError(f"invalid Coinbase candle value: {product} {timestamp}")
    if low > high or not low <= opened <= high or not low <= closed <= high:
        raise RuntimeError(f"invalid Coinbase OHLC bounds: {product} {timestamp}")
    return timestamp, (low, high, opened, closed, volume)


def parse_coinbase(
    bundle: dict[str, Any],
) -> tuple[dict[str, dict[datetime, tuple[Decimal, ...]]], dict[str, Any]]:
    products: dict[str, dict[int, tuple[Decimal, ...]]] = {
        "BTC-USD": {},
        "USDT-USD": {},
    }
    raw_rows = {product: 0 for product in products}
    duplicates = {product: 0 for product in products}
    window_counts = {product: 0 for product in products}
    for item in bundle["candle_windows"]:
        product = item["product_id"]
        if product not in products or item["granularity_seconds"] != 3600:
            raise RuntimeError("unexpected product or granularity")
        window_counts[product] += 1
        body = _decode_body(item)
        rows = json.loads(body, parse_float=Decimal)
        if not isinstance(rows, list) or len(rows) > 300:
            raise RuntimeError("invalid Coinbase candle response")
        raw_rows[product] += len(rows)
        for row in rows:
            if not isinstance(row, list):
                raise RuntimeError("invalid Coinbase candle row")
            timestamp, values = _validate_candle(row, product)
            previous = products[product].get(timestamp)
            if previous is not None:
                duplicates[product] += 1
                if previous != values:
                    raise RuntimeError(f"conflicting Coinbase duplicate: {product} {timestamp}")
            products[product][timestamp] = values
    if window_counts != {"BTC-USD": 189, "USDT-USD": 189}:
        raise RuntimeError("unexpected Coinbase window population")

    normalized: dict[str, dict[datetime, tuple[Decimal, ...]]] = {}
    gaps: dict[str, list[dict[str, object]]] = {}
    for product, rows in products.items():
        filtered = {
            datetime.fromtimestamp(timestamp, UTC): values
            for timestamp, values in rows.items()
            if START.timestamp() <= timestamp < END_EXCLUSIVE.timestamp()
        }
        timestamps = sorted(filtered)
        product_gaps = []
        for left, right in zip(timestamps, timestamps[1:], strict=False):
            if right - left != ONE_HOUR:
                product_gaps.append(
                    {
                        "left_utc": left.isoformat(),
                        "right_utc": right.isoformat(),
                        "missing_hours": int((right - left) / ONE_HOUR) - 1,
                    }
                )
        normalized[product] = filtered
        gaps[product] = product_gaps
    return normalized, {
        "raw_rows": raw_rows,
        "duplicate_rows": duplicates,
        "unique_rows": {product: len(rows) for product, rows in normalized.items()},
        "coverage": {
            product: {
                "start_utc": min(rows).isoformat(),
                "end_utc": max(rows).isoformat(),
            }
            for product, rows in normalized.items()
        },
        "gaps": gaps,
        "gaps_sha256": sha256_bytes(
            json.dumps(gaps, sort_keys=True, separators=(",", ":")).encode()
        ),
    }


def _logical_hash(table: pa.Table) -> str:
    digest = hashlib.sha256()
    columns = [table.column(name).to_pylist() for name in table.schema.names]
    for row in zip(*columns, strict=True):
        digest.update(("|".join(str(value) for value in row) + "\n").encode())
    return digest.hexdigest()


def derive(
    raw_path: Path = RAW_BUNDLE, binance_path: Path = BINANCE_PARQUET
) -> tuple[pa.Table, dict[str, Any]]:
    bundle = load_raw_bundle(raw_path)
    product_hashes = _validate_sources(bundle)
    coinbase, source_summary = parse_coinbase(bundle)
    binance = pq.read_table(binance_path)  # type: ignore[no-untyped-call]
    if set(("timestamp_open_utc", "open", "close")) - set(binance.schema.names):
        raise RuntimeError("Binance normalized schema incomplete")
    binance_rows = {
        row["timestamp_open_utc"].astimezone(UTC): (row["open"], row["close"])
        for row in binance.select(["timestamp_open_utc", "open", "close"]).to_pylist()
    }
    common = sorted(set(coinbase["BTC-USD"]) & set(coinbase["USDT-USD"]) & set(binance_rows))
    if not common:
        raise RuntimeError("no aligned cross-venue rows")

    rows: list[dict[str, object]] = []
    context = Context(prec=50)
    for timestamp in common:
        btcusd = coinbase["BTC-USD"][timestamp][3]
        usdtusd = coinbase["USDT-USD"][timestamp][3]
        binance_open, binance_close = binance_rows[timestamp]
        with localcontext(context):
            implied = btcusd / usdtusd
            premium = (implied / binance_close).ln().quantize(LN_QUANTUM)
        rows.append(
            {
                "timestamp_open_utc": timestamp,
                "source_close_utc": timestamp + SOURCE_CLOSE_OFFSET,
                "coinbase_btcusd_close": btcusd.quantize(Decimal("0.00000001")),
                "coinbase_usdtusd_close": usdtusd.quantize(Decimal("0.00000001")),
                "binance_btcusdt_open": binance_open,
                "binance_btcusdt_close": binance_close,
                "coinbase_implied_btcusdt": implied.quantize(Decimal("0.00000001")),
                "log_premium": premium,
            }
        )
    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    opens = table.column("timestamp_open_utc").to_pylist()
    aligned_gaps = [
        {
            "left_utc": left.isoformat(),
            "right_utc": right.isoformat(),
            "missing_hours": int((right - left) / ONE_HOUR) - 1,
        }
        for left, right in zip(opens, opens[1:], strict=False)
        if right - left != ONE_HOUR
    ]
    all_binance_opens = sorted(binance_rows)
    mappings = 0
    for row in rows:
        close = row["source_close_utc"]
        if not isinstance(close, datetime):
            raise AssertionError("source close must be datetime")
        index = bisect.bisect_right(all_binance_opens, close)
        if index < len(all_binance_opens):
            if all_binance_opens[index] <= close:
                raise RuntimeError("non-causal strict-later mapping")
            mappings += 1
    summary = {
        "raw_bundle_sha256": sha256_file(raw_path),
        "raw_bundle_bytes": raw_path.stat().st_size,
        "source_response_count": len(bundle["sources"]),
        "candle_response_count": len(bundle["candle_windows"]),
        "product_identity_body_sha256": product_hashes,
        "coinbase": source_summary,
        "binance_parquet_sha256": sha256_file(binance_path),
        "binance_rows": binance.num_rows,
        "aligned_rows": table.num_rows,
        "aligned_start_utc": opens[0].isoformat(),
        "aligned_end_utc": opens[-1].isoformat(),
        "aligned_gaps": aligned_gaps,
        "aligned_gaps_sha256": sha256_bytes(
            json.dumps(aligned_gaps, sort_keys=True, separators=(",", ":")).encode()
        ),
        "strict_later_mappings": mappings,
        "logical_content_sha256": _logical_hash(table),
    }
    return table, summary


def build() -> dict[str, Any]:
    table, summary = derive()
    NORMALIZED.parent.mkdir(parents=True, exist_ok=True)
    temporary = NORMALIZED.with_suffix(NORMALIZED.suffix + f".tmp.{os.getpid()}")
    pq.write_table(table, temporary, compression="zstd", version="2.6")  # type: ignore[no-untyped-call]
    os.replace(temporary, NORMALIZED)
    package = {
        "schema": "tios-cross-venue-btc-premium-data-package-v1",
        "package_id": "DATA-CROSS-VENUE-BTC-PREMIUM-1H-V1",
        "decision": "D-075",
        "status": "VERIFIED_OFFLINE",
        "created_from_retrieval_utc": load_raw_bundle()["retrieval_completed_utc"],
        "source_dossier": {
            "path": str(DOSSIER.relative_to(ROOT)),
            "sha256": sha256_file(DOSSIER),
        },
        "raw_bundle": {
            "path": str(RAW_BUNDLE.relative_to(ROOT)),
            "sha256": summary["raw_bundle_sha256"],
            "bytes": summary["raw_bundle_bytes"],
        },
        "binance_source": {
            "path": str(BINANCE_PARQUET.relative_to(ROOT)),
            "sha256": summary["binance_parquet_sha256"],
            "scope": "retained normalized BTCUSDT hourly source only; no closed-family result",
        },
        "normalized": {
            "path": str(NORMALIZED.relative_to(ROOT)),
            "sha256": sha256_file(NORMALIZED),
            "bytes": NORMALIZED.stat().st_size,
            "schema": str(SCHEMA),
            "logical_content_sha256": summary["logical_content_sha256"],
        },
        "summary": summary,
        "semantics": {
            "feature": (
                "ln((coinbase_btcusd_close / coinbase_usdtusd_close) / binance_btcusdt_close)"
            ),
            "coinbase_candle_close_boundary": "bucket_start_plus_one_hour_minus_one_microsecond",
            "availability": "after latest complete source candle only",
            "fill_mapping": "first retained Binance hourly open strictly after source_close_utc",
            "gap_policy": (
                "no fill, no carry, reset baseline; held pulse exits at first retained Binance open"
            ),
            "network_during_verify_or_campaign": False,
        },
        "safety": {
            "performance_computed": False,
            "strategy_scored": False,
            "sealed_v2_holdout_accessed": False,
            "venue_connection": "NONE",
            "execution_authority": "NONE",
        },
    }
    PACKAGE.write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"package": str(PACKAGE), **summary}, sort_keys=True, default=str))
    return package


if __name__ == "__main__":
    build()
