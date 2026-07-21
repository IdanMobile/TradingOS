"""Fail-closed checks for the Bitcoin transaction-activity data package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_btc_tx_activity_data as tx_data  # noqa: E402

# These verify retained data-package byte integrity by decoding large base64
# archives. They are ~94% of total suite runtime and only change when the DATA
# changes, not when code does — so they run in `make check-full`, not `make check`.
pytestmark = pytest.mark.slow


def test_tracked_transaction_activity_package_verifies_offline() -> None:
    assert tx_data.verify() == {
        "package_id": "DATA-BTC-TX-ACTIVITY-SPOT-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "activity_observations": 2187,
        "campaign_observations": 2004,
        "known_gap_count": 1,
        "spot_rows": 48154,
        "missing_expected_entry_opens": 0,
    }


def test_deliberate_source_byte_drift_fails_closed(tmp_path: Path) -> None:
    package = tx_data.load_package()
    root = tmp_path / "repo"
    raw = root / package["activity_feature"]["raw_path"]
    raw.parent.mkdir(parents=True)
    raw.write_bytes((ROOT / package["activity_feature"]["raw_path"]).read_bytes() + b"drift")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        tx_data.verify_file(raw, package["activity_feature"]["raw_sha256"])


def test_deliberate_schema_drift_fails_closed(tmp_path: Path) -> None:
    package = tx_data.load_package()
    package["activity_feature"]["response_contract"]["period"] = "week"
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="metadata drift"):
        tx_data.verify(changed, ROOT)


def test_deliberate_gap_contract_drift_fails_closed(tmp_path: Path) -> None:
    package = tx_data.load_package()
    package["activity_feature"]["known_gaps"] = []
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="gap set"):
        tx_data.verify(changed, ROOT)


def test_deliberate_availability_lag_drift_fails_closed(tmp_path: Path) -> None:
    package = tx_data.load_package()
    package["activity_feature"]["availability_lag_full_utc_days"] = 0
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="availability lag"):
        tx_data.verify(changed, ROOT)
