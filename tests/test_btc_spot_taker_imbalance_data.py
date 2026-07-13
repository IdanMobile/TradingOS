"""Fail-closed checks for the BTC Spot taker-imbalance data package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_btc_spot_taker_imbalance_data as taker_data  # noqa: E402


def test_tracked_taker_imbalance_package_verifies_offline() -> None:
    assert taker_data.verify() == {
        "package_id": "DATA-BTC-SPOT-TAKER-IMBALANCE-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "spot_rows": 72225,
        "valid_feature_rows": 72221,
        "invalid_feature_rows": 4,
        "strict_later_mappings": 72220,
        "spot_gap_count": 25,
    }


def test_deliberate_taker_archive_drift_fails_closed(tmp_path: Path) -> None:
    archive = taker_data.load_package()["spot_data"]["early_archives"][0]
    root = tmp_path / "repo"
    target = root / archive["base64_path"]
    target.parent.mkdir(parents=True)
    target.write_bytes((ROOT / archive["base64_path"]).read_bytes() + b"drift")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        taker_data._decode(archive, root)


def test_deliberate_taker_feature_hash_drift_fails_closed(tmp_path: Path) -> None:
    package = taker_data.load_package()
    package["spot_data"]["feature_logical_sha256"] = "0" * 64
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="feature logical content"):
        taker_data.verify(changed, ROOT)


def test_deliberate_taker_mapping_count_drift_fails_closed(tmp_path: Path) -> None:
    package = taker_data.load_package()
    package["spot_data"]["strict_later_mappings"] += 1
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mapping count differs"):
        taker_data.verify(changed, ROOT)
