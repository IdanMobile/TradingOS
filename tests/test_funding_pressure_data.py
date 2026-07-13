"""Fail-closed checks for the funding-pressure data package."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_funding_pressure_data as funding_data  # noqa: E402


def test_tracked_funding_pressure_package_verifies_offline() -> None:
    assert funding_data.verify() == {
        "package_id": "DATA-FUNDING-PRESSURE-BTCUSDT-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "funding_archives": 66,
        "funding_observations": 6021,
        "spot_rows": 48154,
        "missing_expected_entry_opens": 0,
    }


def test_deliberate_archive_byte_drift_fails_closed(tmp_path: Path) -> None:
    source = ROOT / "data/raw/fundingRate/BTCUSDT"
    changed_root = tmp_path / "repo"
    changed = changed_root / "data/raw/fundingRate/BTCUSDT"
    shutil.copytree(source, changed)
    target = changed / "BTCUSDT-fundingRate-2021-01.zip"
    target.write_bytes(target.read_bytes() + b"drift")
    package = funding_data.load_package()
    with pytest.raises(RuntimeError, match="manifest root"):
        funding_data._verify_funding(package, changed_root)


def test_deliberate_schema_drift_fails_closed(tmp_path: Path) -> None:
    package = funding_data.load_package()
    package["funding_feature"]["csv_header"] = ["calc_time", "last_funding_rate"]
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="schema drift"):
        loaded = funding_data.load_package(changed)
        funding_data._verify_funding(loaded, ROOT)


def test_deliberate_timestamp_contract_drift_fails_closed(tmp_path: Path) -> None:
    package = funding_data.load_package()
    package["funding_feature"]["first_calc_time_ms"] += 1
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="timestamp coverage"):
        loaded = funding_data.load_package(changed)
        funding_data._verify_funding(loaded, ROOT)


def test_sha256_helper_rejects_changed_bytes(tmp_path: Path) -> None:
    changed = tmp_path / "changed.bin"
    changed.write_bytes(b"changed")
    expected = hashlib.sha256(b"original").hexdigest()
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        funding_data.verify_file(changed, expected)
