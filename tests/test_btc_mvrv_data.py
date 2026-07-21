"""Fail-closed checks for the Bitcoin MVRV data package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_btc_mvrv_data as mvrv_data  # noqa: E402

# These verify retained data-package byte integrity by decoding large base64
# archives. They are ~94% of total suite runtime and only change when the DATA
# changes, not when code does — so they run in `make check-full`, not `make check`.
pytestmark = pytest.mark.slow


def test_tracked_mvrv_package_verifies_offline() -> None:
    assert mvrv_data.verify() == {
        "package_id": "DATA-BTC-MVRV-SPOT-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "mvrv_observations": 2189,
        "campaign_observations": 2007,
        "known_gap_count": 0,
        "spot_rows": 48154,
        "missing_expected_entry_opens": 0,
    }


def test_deliberate_source_byte_drift_fails_closed(tmp_path: Path) -> None:
    package = mvrv_data.load_package()
    root = tmp_path / "repo"
    raw = root / package["mvrv_feature"]["raw_path"]
    raw.parent.mkdir(parents=True)
    raw.write_bytes((ROOT / package["mvrv_feature"]["raw_path"]).read_bytes() + b"drift")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        mvrv_data.verify_file(raw, package["mvrv_feature"]["tracked_raw_sha256"])


def test_deliberate_catalog_contract_drift_fails_closed(tmp_path: Path) -> None:
    package = mvrv_data.load_package()
    package["mvrv_feature"]["metric_contract"]["unit"] = "USD"
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="catalog contract drift"):
        mvrv_data.verify(changed, ROOT)


def test_deliberate_gap_contract_drift_fails_closed(tmp_path: Path) -> None:
    package = mvrv_data.load_package()
    package["mvrv_feature"]["known_gaps"] = [{"left_utc": "invented"}]
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="gap set"):
        mvrv_data.verify(changed, ROOT)


def test_deliberate_lag_drift_fails_closed(tmp_path: Path) -> None:
    package = mvrv_data.load_package()
    package["mvrv_feature"]["availability_lag_full_utc_days"] = 0
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="availability lag"):
        mvrv_data.verify(changed, ROOT)
