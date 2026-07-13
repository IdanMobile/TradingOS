"""Verify the frozen BTC Spot taker-imbalance package offline."""

from __future__ import annotations

import base64
import bisect
import hashlib
import json
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from tios.dataset.normalize import (  # type: ignore[import-untyped]
    content_sha256,
    dedup_sorted,
    parse_zip,
    to_canonical,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/BTC_SPOT_TAKER_IMBALANCE_DATA_PACKAGE_V1.json"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _verify_file(path: Path, expected: str) -> None:
    if not path.is_file() or _sha256(path.read_bytes()) != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}")


def load_package(path: Path = PACKAGE) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if package.get("schema") != "tios-btc-spot-taker-imbalance-data-package-v1":
        raise ValueError("unsupported Spot taker-imbalance data package")
    safety = package.get("safety", {})
    if safety.get("execution_authority") != "NONE" or safety.get("venue_connection") != "NONE":
        raise ValueError("data package cannot contain trading authority")
    return package


def _decode(archive: dict[str, Any], root: Path) -> bytes:
    path = root / archive["base64_path"]
    _verify_file(path, archive["base64_sha256"])
    encoded = path.read_bytes()
    if len(encoded) != archive["base64_bytes"]:
        raise RuntimeError("base64 archive byte size differs from package")
    decoded = base64.b64decode(encoded)
    if len(decoded) != archive["decoded_bytes"] or _sha256(decoded) != archive["decoded_sha256"]:
        raise RuntimeError("decoded archive differs from package")
    return decoded


def _gap_evidence(table: pa.Table) -> tuple[int, str]:
    opens = table.column("timestamp_open_utc").to_pylist()
    gaps = [
        {"left_utc": left.isoformat(), "right_utc": right.isoformat()}
        for left, right in zip(opens, opens[1:], strict=False)
        if right - left != timedelta(hours=1)
    ]
    return len(gaps), _sha256(json.dumps(gaps, sort_keys=True, separators=(",", ":")).encode())


def _feature_logical_hash(table: pa.Table) -> str:
    digest = hashlib.sha256()
    columns = [
        table.column(name).to_pylist()
        for name in (
            "timestamp_open_utc",
            "open",
            "close",
            "close_timestamp_utc",
            "quote_volume",
            "taker_buy_quote_volume",
        )
    ]
    for row in zip(*columns, strict=True):
        values = [
            row[0].isoformat(),
            str(row[1]),
            str(row[2]),
            row[3].isoformat(),
            str(row[4]),
            str(row[5]),
        ]
        digest.update(("|".join(values) + "\n").encode())
    return digest.hexdigest()


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    spot = package["spot_data"]
    early_tables: list[pa.Table] = []
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        for archive in spot["early_archives"]:
            decoded = _decode(archive, root)
            checksum_path = root / archive["checksum_base64_path"]
            _verify_file(checksum_path, archive["checksum_base64_sha256"])
            checksum = base64.b64decode(checksum_path.read_bytes()).decode().split()[0]
            if checksum != archive["official_sha256"] or checksum != archive["decoded_sha256"]:
                raise RuntimeError("Binance official checksum mismatch")
            zip_path = temp / Path(archive["base64_path"]).name.removesuffix(".base64")
            zip_path.write_bytes(decoded)
            raw, detection = parse_zip(zip_path, archive["month"])
            early_tables.append(to_canonical(raw, detection.detected_unit, "BTCUSDT", "1h"))

    early, dropped = dedup_sorted(pa.concat_tables(early_tables).sort_by("timestamp_open_utc"))
    if (
        dropped
        or early.num_rows != spot["early_rows"]
        or content_sha256(early) != spot["early_logical_content_sha256"]
    ):
        raise RuntimeError("early Spot logical content differs from package")
    if _gap_evidence(early) != (spot["early_gap_count"], spot["early_gaps_sha256"]):
        raise RuntimeError("early Spot gap evidence differs from package")

    _verify_file(root / spot["existing_manifest_path"], spot["existing_manifest_sha256"])
    existing_path = root / spot["existing_normalized_path"]
    _verify_file(existing_path, spot["existing_normalized_sha256"])
    existing = pq.read_table(existing_path)  # type: ignore[no-untyped-call]
    combined, dropped = dedup_sorted(
        pa.concat_tables([early, existing]).sort_by("timestamp_open_utc")
    )
    if (
        dropped
        or combined.num_rows != spot["combined_rows"]
        or content_sha256(combined) != spot["combined_logical_content_sha256"]
    ):
        raise RuntimeError("combined Spot logical content differs from package")
    if _gap_evidence(combined) != (spot["feature_gap_count"], spot["combined_gaps_sha256"]):
        raise RuntimeError("combined Spot gap evidence differs from package")
    if _feature_logical_hash(combined) != spot["feature_logical_sha256"]:
        raise RuntimeError("Spot taker feature logical content differs from package")

    opens = combined.column("timestamp_open_utc").to_pylist()
    closes = combined.column("close_timestamp_utc").to_pylist()
    quote = combined.column("quote_volume").to_pylist()
    taker_buy = combined.column("taker_buy_quote_volume").to_pylist()
    invalid: list[str] = []
    mapped = 0
    for opened, closed, total, bought in zip(opens, closes, quote, taker_buy, strict=True):
        if total <= 0 or not Decimal(0) <= bought <= total or closed < opened:
            invalid.append(opened.isoformat())
            continue
        feature = (Decimal(2) * bought / total) - Decimal(1)
        if not Decimal(-1) <= feature <= Decimal(1):
            raise RuntimeError("Spot taker feature outside [-1, 1]")
        index = bisect.bisect_right(opens, closed)
        if index < len(opens):
            if opens[index] <= closed:
                raise RuntimeError("same-open feature fill mapping")
            mapped += 1
    if invalid != spot["invalid_feature_rows"]:
        raise RuntimeError("invalid feature-row ledger differs from package")
    if (
        len(opens) - len(invalid) != spot["valid_feature_rows"]
        or mapped != spot["strict_later_mappings"]
    ):
        raise RuntimeError("feature row or strict-later mapping count differs from package")
    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "spot_rows": len(opens),
        "valid_feature_rows": len(opens) - len(invalid),
        "invalid_feature_rows": len(invalid),
        "strict_later_mappings": mapped,
        "spot_gap_count": spot["feature_gap_count"],
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
