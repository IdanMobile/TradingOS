"""Amendment A1 golden test (T-004-02 acceptance, D-029, CG-03).

Fixtures are real rows cut from the frozen raw snapshot: the last 3 hourly bars
of 2024-12 (ms timestamps) and the first 3 of 2025-01 (µs timestamps), for both
instruments. Both regimes must converge to identical canonical representation
with exact 1h spacing across the boundary.
"""

from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pytest

from tios.dataset.normalize import (
    dedup_sorted,
    detect_unit,
    expected_unit_for_month,
    parse_zip,
    to_canonical,
)

FX = Path(__file__).resolve().parent.parent / "fixtures" / "binance_boundary"


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


@pytest.mark.parametrize("sym", ["BTCUSDT", "ETHUSDT"])
def test_boundary_converges_to_canonical_utc(sym: str) -> None:
    dec_raw, dec_det = parse_zip(FX / f"{sym}-1h-2024-12.zip", "2024-12")
    jan_raw, jan_det = parse_zip(FX / f"{sym}-1h-2025-01.zip", "2025-01")
    assert dec_det.detected_unit == "ms"
    assert jan_det.detected_unit == "us"

    dec = to_canonical(dec_raw, "ms", sym, "1h")
    jan = to_canonical(jan_raw, "us", sym, "1h")
    assert dec.schema == jan.schema  # both regimes: identical representation

    merged = pa.concat_tables([dec, jan]).sort_by("timestamp_open_utc")
    opens = merged.column("timestamp_open_utc").to_pylist()
    # golden: exact bar opens across the boundary, 21:00 Dec 31 → 02:00 Jan 1
    assert opens == [
        utc("2024-12-31T21:00:00"),
        utc("2024-12-31T22:00:00"),
        utc("2024-12-31T23:00:00"),
        utc("2025-01-01T00:00:00"),
        utc("2025-01-01T01:00:00"),
        utc("2025-01-01T02:00:00"),
    ]
    deltas = {(b - a).total_seconds() for a, b in zip(opens[:-1], opens[1:], strict=True)}
    assert deltas == {3600.0}  # no gap, no overlap at the unit boundary


def test_unit_detection_rules() -> None:
    assert detect_unit(1735678800000) == "ms"  # 2024-12-31T21:00Z in ms
    assert detect_unit(1735689600000000) == "us"  # 2025-01-01T00:00Z in µs
    assert expected_unit_for_month("2024-12") == "ms"
    assert expected_unit_for_month("2025-01") == "us"
    assert expected_unit_for_month("2026-06") == "us"


def test_unit_mismatch_is_rejected() -> None:
    """A µs-looking file in a pre-2025 month must hard-fail, not silently pass."""
    with pytest.raises(ValueError, match="Amendment A1"):
        parse_zip(FX / "BTCUSDT-1h-2025-01.zip", "2024-12")


def test_dedup_is_explicit_and_counted() -> None:
    raw, _ = parse_zip(FX / "BTCUSDT-1h-2025-01.zip", "2025-01")
    t = to_canonical(raw, "us", "BTCUSDT", "1h")
    doubled = pa.concat_tables([t, t]).sort_by("timestamp_open_utc")
    deduped, dropped = dedup_sorted(doubled)
    assert dropped == t.num_rows
    assert deduped.num_rows == t.num_rows
