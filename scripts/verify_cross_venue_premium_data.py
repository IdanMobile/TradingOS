"""Verify the frozen D-075 cross-venue data package with no network access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build_cross_venue_premium_data as builder
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "research/CROSS_VENUE_BTC_PREMIUM_DATA_PACKAGE_V1.json"


def _verify_file(path: Path, expected: str) -> None:
    if not path.is_file() or builder.sha256_file(path) != expected:
        raise RuntimeError(f"SHA-256 mismatch for {path}")


def load_package(path: Path = PACKAGE) -> dict[str, Any]:
    package: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if package.get("schema") != "tios-cross-venue-btc-premium-data-package-v1":
        raise ValueError("unsupported cross-venue data package")
    safety = package.get("safety", {})
    if safety.get("performance_computed") or safety.get("strategy_scored"):
        raise ValueError("data package cannot contain performance")
    if safety.get("execution_authority") != "NONE" or safety.get("venue_connection") != "NONE":
        raise ValueError("data package cannot contain trading authority")
    return package


def verify(package_path: Path = PACKAGE, root: Path = ROOT) -> dict[str, object]:
    package = load_package(package_path)
    dossier = package["source_dossier"]
    raw = package["raw_bundle"]
    binance = package["binance_source"]
    normalized = package["normalized"]
    dossier_path = root / dossier["path"]
    raw_path = root / raw["path"]
    binance_path = root / binance["path"]
    normalized_path = root / normalized["path"]
    _verify_file(dossier_path, dossier["sha256"])
    _verify_file(raw_path, raw["sha256"])
    _verify_file(binance_path, binance["sha256"])
    _verify_file(normalized_path, normalized["sha256"])
    if (
        raw_path.stat().st_size != raw["bytes"]
        or normalized_path.stat().st_size != normalized["bytes"]
    ):
        raise RuntimeError("tracked data byte size differs from package")

    derived, summary = builder.derive(raw_path, binance_path)
    if summary != package["summary"]:
        raise RuntimeError("derived cross-venue summary differs from package")
    retained = pq.read_table(normalized_path)  # type: ignore[no-untyped-call]
    if retained.schema != builder.SCHEMA or not retained.equals(derived):
        raise RuntimeError("normalized cross-venue table differs from source reconstruction")
    if builder._logical_hash(retained) != normalized["logical_content_sha256"]:
        raise RuntimeError("normalized logical content differs from package")
    return {
        "package_id": package["package_id"],
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "source_responses": summary["source_response_count"] + summary["candle_response_count"],
        "aligned_rows": summary["aligned_rows"],
        "aligned_gaps": len(summary["aligned_gaps"]),
        "strict_later_mappings": summary["strict_later_mappings"],
        "performance_computed": False,
        "execution_authority": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
