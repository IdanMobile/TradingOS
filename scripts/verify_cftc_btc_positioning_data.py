"""Verify the frozen CFTC Bitcoin-positioning plus Spot package offline."""

from __future__ import annotations

import base64
import bisect
import csv
import hashlib
import io
import json
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from tios.dataset.arrow_time import utc_datetimes
from tios.dataset.normalize import (  # type: ignore[import-untyped]
    content_sha256,
    dedup_sorted,
    parse_zip,
    to_canonical,
)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/CFTC_BTC_POSITIONING_DATA_PACKAGE_V1.json"
CORE_FIELDS = (
    "id",
    "report_date_as_yyyy_mm_dd",
    "cftc_contract_market_code",
    "open_interest_all",
    "noncomm_positions_long_all",
    "noncomm_positions_short_all",
    "noncomm_postions_spread_all",
    "contract_units",
    "futonly_or_combined",
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def verify_file(path: Path, expected: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing pinned file: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}: expected {expected}, found {actual}")


def load_package(path: Path = PACKAGE) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if package.get("schema") != "tios-cftc-btc-positioning-data-package-v1":
        raise ValueError("unsupported CFTC positioning data package")
    if package.get("execution_authority") != "NONE" or package.get("venue_connection") != "NONE":
        raise ValueError("CFTC package cannot contain trading authority")
    return package


def decode_source(source: dict[str, Any], root: Path = ROOT) -> bytes:
    encoded_path = root / source["base64_path"]
    verify_file(encoded_path, source["base64_sha256"])
    encoded = encoded_path.read_bytes()
    if len(encoded) != source["base64_bytes"]:
        raise RuntimeError("base64 source byte size differs from package")
    decoded = base64.b64decode(encoded, validate=False)
    if len(decoded) != source["decoded_bytes"] or sha256_bytes(decoded) != source["decoded_sha256"]:
        raise RuntimeError("decoded source bytes differ from package")
    return decoded


def _availability(report_date: str, exceptions: dict[str, str]) -> datetime:
    report = datetime.fromisoformat(report_date[:10]).replace(tzinfo=UTC)
    available = report + timedelta(days=8)
    actual = exceptions.get(report_date[:10])
    if actual is not None:
        available = max(
            available,
            datetime.fromisoformat(actual).replace(tzinfo=UTC) + timedelta(days=1),
        )
    return available


def _gap_evidence(table: pa.Table) -> tuple[int, str]:
    opens = utc_datetimes(table.column("timestamp_open_utc"))
    gaps = [
        {"left_utc": left.isoformat(), "right_utc": right.isoformat()}
        for left, right in zip(opens, opens[1:], strict=False)
        if right - left != timedelta(hours=1)
    ]
    encoded = json.dumps(gaps, sort_keys=True, separators=(",", ":")).encode()
    return len(gaps), sha256_bytes(encoded)


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    feature = package["cftc_feature"]
    decoded_sources = [decode_source(source, root) for source in feature["sources"]]
    csv_bytes, metadata_bytes = decoded_sources[:2]

    metadata = json.loads(metadata_bytes)
    if metadata.get("id") != feature["dataset_id"]:
        raise RuntimeError("CFTC dataset metadata identity drift")
    if len(metadata.get("columns", [])) != feature["columns"]:
        raise RuntimeError("CFTC dataset metadata column drift")

    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    if len(rows) != feature["observations"] or len(rows[0]) != feature["columns"]:
        raise RuntimeError("CFTC row or column count differs from package")
    dates: list[datetime] = []
    logical_rows: list[dict[str, str]] = []
    for row in rows:
        if row["cftc_contract_market_code"] != feature["contract_market_code"]:
            raise RuntimeError("CFTC contract identity drift")
        if row["futonly_or_combined"] != "FutOnly" or row["contract_units"] != "(5 Bitcoins)":
            raise RuntimeError("CFTC report or contract-unit drift")
        open_interest = Decimal(row["open_interest_all"])
        long = Decimal(row["noncomm_positions_long_all"])
        short = Decimal(row["noncomm_positions_short_all"])
        if open_interest <= 0 or min(long, short) < 0:
            raise RuntimeError("invalid CFTC positioning arithmetic input")
        _ = (long - short) / open_interest
        dates.append(datetime.fromisoformat(row["report_date_as_yyyy_mm_dd"]).replace(tzinfo=UTC))
        logical_rows.append({key: row[key] for key in CORE_FIELDS})
    if len({row["id"] for row in rows}) != len(rows) or any(
        right <= left for left, right in zip(dates, dates[1:], strict=False)
    ):
        raise RuntimeError("CFTC identifiers or report dates are duplicate/non-monotone")
    logical = json.dumps(logical_rows, sort_keys=True, separators=(",", ":")).encode()
    if sha256_bytes(logical) != feature["logical_core_sha256"]:
        raise RuntimeError("CFTC logical core differs from package")
    if (
        dates[0].date().isoformat() != feature["coverage_start_report_date"]
        or dates[-1].date().isoformat() != feature["coverage_end_report_date"]
    ):
        raise RuntimeError("CFTC report coverage differs from package")

    exceptions_path = root / feature["publication_exceptions_path"]
    verify_file(exceptions_path, feature["publication_exceptions_sha256"])
    ledger = json.loads(exceptions_path.read_text(encoding="utf-8"))
    exceptions: dict[str, str] = ledger["exceptions"]
    if not set(exceptions).issubset({value.date().isoformat() for value in dates}):
        raise RuntimeError("publication exception does not map to a retained CFTC report")
    if _availability("2023-01-31", exceptions) != datetime(2023, 2, 25, tzinfo=UTC):
        raise RuntimeError("CFTC delayed-publication semantics drift")

    spot = package["spot_execution"]
    early_tables: list[pa.Table] = []
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        for archive in spot["early_archives"]:
            decoded = decode_source(archive, root)
            checksum_path = root / archive["checksum_base64_path"]
            checksum_encoded = checksum_path.read_bytes()
            checksum_source = {
                "base64_path": archive["checksum_base64_path"],
                "base64_sha256": archive["checksum_base64_sha256"],
                "base64_bytes": checksum_path.stat().st_size,
                "decoded_sha256": archive["checksum_decoded_sha256"],
                "decoded_bytes": len(base64.b64decode(checksum_encoded)),
            }
            checksum = decode_source(checksum_source, root).decode("utf-8").split()[0]
            if checksum != archive["official_sha256"] or checksum != archive["decoded_sha256"]:
                raise RuntimeError("Binance official checksum mismatch")
            zip_path = temp / Path(archive["base64_path"]).name.removesuffix(".base64")
            zip_path.write_bytes(decoded)
            raw, detection = parse_zip(zip_path, archive["month"])
            early_tables.append(to_canonical(raw, detection.detected_unit, "BTCUSDT", "1h"))
    early = pa.concat_tables(early_tables).sort_by("timestamp_open_utc")
    early, dropped = dedup_sorted(early)
    early_mismatch = (
        dropped
        or early.num_rows != spot["early_rows"]
        or content_sha256(early) != spot["early_logical_content_sha256"]
    )
    if early_mismatch:
        raise RuntimeError("early Spot logical content differs from package")
    early_gap_count, early_gap_hash = _gap_evidence(early)
    if (early_gap_count, early_gap_hash) != (spot["early_gap_count"], spot["early_gaps_sha256"]):
        raise RuntimeError("early Spot gap evidence differs from package")

    verify_file(root / spot["existing_manifest_path"], spot["existing_manifest_sha256"])
    existing_path = root / spot["existing_normalized_path"]
    verify_file(existing_path, spot["existing_normalized_sha256"])
    existing = pq.read_table(existing_path)  # type: ignore[no-untyped-call]
    combined = pa.concat_tables([early, existing]).sort_by("timestamp_open_utc")
    combined, dropped = dedup_sorted(combined)
    combined_mismatch = (
        dropped
        or combined.num_rows != spot["combined_rows"]
        or content_sha256(combined) != spot["combined_logical_content_sha256"]
    )
    if combined_mismatch:
        raise RuntimeError("combined Spot logical content differs from package")
    combined_gap_count, combined_gap_hash = _gap_evidence(combined)
    if (combined_gap_count, combined_gap_hash) != (
        spot["combined_gap_count"],
        spot["combined_gaps_sha256"],
    ):
        raise RuntimeError("combined Spot gap evidence differs from package")

    opens = utc_datetimes(combined.column("timestamp_open_utc"))
    mapped = 0
    unmapped: list[str] = []
    for row in rows:
        available = _availability(row["report_date_as_yyyy_mm_dd"], exceptions)
        index = bisect.bisect_right(opens, available)
        if index == len(opens):
            unmapped.append(row["report_date_as_yyyy_mm_dd"][:10])
        else:
            if opens[index] <= available:
                raise RuntimeError("same-open CFTC fill mapping")
            mapped += 1
    if mapped != spot["mapped_cftc_observations"] or unmapped != spot["unmapped_report_dates"]:
        raise RuntimeError("CFTC-to-Spot mapping differs from package")
    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "cftc_observations": len(rows),
        "mapped_cftc_observations": mapped,
        "publication_exceptions": len(exceptions),
        "spot_rows": combined.num_rows,
        "spot_gap_count": combined_gap_count,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
