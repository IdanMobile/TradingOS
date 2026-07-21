"""Fail-closed checks for the D-075 cross-venue data package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_cross_venue_premium_data as cross_venue_data  # noqa: E402

# These verify retained data-package byte integrity by decoding large base64
# archives. They are ~94% of total suite runtime and only change when the DATA
# changes, not when code does — so they run in `make check-full`, not `make check`.
pytestmark = pytest.mark.slow


def test_tracked_cross_venue_package_verifies_offline() -> None:
    assert cross_venue_data.verify() == {
        "package_id": "DATA-CROSS-VENUE-BTC-PREMIUM-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "source_responses": 382,
        "aligned_rows": 45193,
        "aligned_gaps": 6,
        "strict_later_mappings": 45192,
        "performance_computed": False,
        "execution_authority": "NONE",
    }


def test_deliberate_raw_bundle_drift_fails_closed(tmp_path: Path) -> None:
    package = cross_venue_data.load_package()
    raw = package["raw_bundle"]
    changed = tmp_path / "raw.json"
    changed.write_bytes((ROOT / raw["path"]).read_bytes() + b"drift")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        cross_venue_data._verify_file(changed, raw["sha256"])


def test_deliberate_logical_hash_drift_fails_closed(tmp_path: Path) -> None:
    package = cross_venue_data.load_package()
    package["normalized"]["logical_content_sha256"] = "0" * 64
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="normalized logical content"):
        cross_venue_data.verify(changed, ROOT)


def test_deliberate_mapping_drift_fails_closed(tmp_path: Path) -> None:
    package = cross_venue_data.load_package()
    package["summary"]["strict_later_mappings"] += 1
    changed = tmp_path / "package.json"
    changed.write_text(json.dumps(package), encoding="utf-8")
    with pytest.raises(RuntimeError, match="derived cross-venue summary"):
        cross_venue_data.verify(changed, ROOT)
