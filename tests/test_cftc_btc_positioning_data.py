"""Fail-closed checks for the CFTC Bitcoin-positioning data package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_cftc_btc_positioning_data as cftc_data  # noqa: E402


def test_tracked_cftc_positioning_package_verifies_offline() -> None:
    assert cftc_data.verify() == {
        "package_id": "DATA-CFTC-BTC-POSITIONING-SPOT-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "cftc_observations": 431,
        "mapped_cftc_observations": 428,
        "publication_exceptions": 30,
        "spot_rows": 72225,
        "spot_gap_count": 25,
    }


def test_deliberate_cftc_byte_drift_fails_closed(tmp_path: Path) -> None:
    package = cftc_data.load_package()
    source = package["cftc_feature"]["sources"][0]
    root = tmp_path / "repo"
    target = root / source["base64_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / source["base64_path"]).read_bytes() + b"drift")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        cftc_data.decode_source(source, root)


def test_deliberate_exception_ledger_drift_fails_closed(tmp_path: Path) -> None:
    package = cftc_data.load_package()
    package["cftc_feature"]["publication_exceptions_sha256"] = "0" * 64
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        cftc_data.verify(changed, ROOT)


def test_deliberate_mapping_count_drift_fails_closed(tmp_path: Path) -> None:
    package = cftc_data.load_package()
    package["spot_execution"]["mapped_cftc_observations"] = 431
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mapping differs"):
        cftc_data.verify(changed, ROOT)
