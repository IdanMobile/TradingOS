"""Focused fail-closed checks for the calendar-family data package."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_calendar_utc_data as calendar_data  # noqa: E402


def test_tracked_calendar_package_verifies_offline() -> None:
    result = calendar_data.verify()
    assert result == {
        "package_id": "DATA-CALENDAR-UTC-BTCUSDT-1H-V1",
        "status": "PASS",
        "mode": "VERIFIED_OFFLINE",
        "network_allowed": False,
        "raw_archives": 66,
        "rows": 48154,
        "gaps": 7,
        "calendar_timezone": "UTC",
    }


def test_deliberate_byte_drift_fails_closed(tmp_path: Path) -> None:
    changed = tmp_path / "changed.bin"
    changed.write_bytes(b"changed")
    expected = hashlib.sha256(b"original").hexdigest()
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        calendar_data.verify_file(changed, expected)
