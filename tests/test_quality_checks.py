"""Corrupted-fixture tests (T-004-03 acceptance): every quality check must FAIL
on a table deliberately violating exactly its rule, and PASS on a clean one."""

from datetime import UTC, datetime
from decimal import Decimal

import pyarrow as pa

from tios.dataset.normalize import CANONICAL_SCHEMA
from tios.dataset.quality import (
    check_monotonic_unique,
    check_ohlc,
    check_spacing,
    check_timezone,
    check_volumes,
    missing_intervals,
)


def bar(minute: int, **overrides: object) -> dict[str, object]:
    d = Decimal
    row: dict[str, object] = {
        "timestamp_open_utc": datetime(2025, 1, 1, 0, minute, tzinfo=UTC),
        "open": d("100.1"),
        "high": d("101.5"),
        "low": d("99.5"),
        "close": d("100.9"),
        "volume_base": d("5.0"),
        "close_timestamp_utc": datetime(2025, 1, 1, 0, minute + 4, 59, 999999, tzinfo=UTC),
        "quote_volume": d("500.0"),
        "trade_count": 42,
        "taker_buy_base_volume": d("2.0"),
        "taker_buy_quote_volume": d("200.0"),
        "source": "fixture",
        "instrument": "BTCUSDT",
        "interval": "5m",
    }
    row.update(overrides)
    return row


def table(rows: list[dict[str, object]]) -> pa.Table:
    return pa.Table.from_pylist(rows, schema=CANONICAL_SCHEMA)


CLEAN = table([bar(0), bar(5), bar(10)])


def test_all_checks_pass_on_clean_table() -> None:
    for check in (
        check_monotonic_unique(CLEAN),
        check_spacing(CLEAN, "5m"),
        check_ohlc(CLEAN),
        check_volumes(CLEAN),
        check_timezone(CLEAN),
    ):
        assert check["status"] == "PASS", check
    assert missing_intervals(CLEAN, "5m")["details"]["gap_count"] == 0


def test_monotonic_fails_on_duplicate_timestamp() -> None:
    corrupted = table([bar(0), bar(5), bar(5)])
    assert check_monotonic_unique(corrupted)["status"] == "FAIL"


def test_monotonic_fails_on_out_of_order() -> None:
    corrupted = table([bar(5), bar(0)])
    assert check_monotonic_unique(corrupted)["status"] == "FAIL"


def test_spacing_fails_on_non_multiple_step() -> None:
    corrupted = table([bar(0), bar(7)])  # 7 min is not a multiple of 5m
    assert check_spacing(corrupted, "5m")["status"] == "FAIL"


def test_missing_intervals_reports_gap() -> None:
    gapped = table([bar(0), bar(5), bar(20)])  # bars 10,15 missing
    report = missing_intervals(gapped, "5m")
    assert report["details"]["gap_count"] == 1
    assert report["details"]["missing_bars_total"] == 2


def test_ohlc_fails_on_low_above_open() -> None:
    corrupted = table([bar(0, low=Decimal("100.5"), open=Decimal("100.1"))])
    assert check_ohlc(corrupted)["status"] == "FAIL"


def test_ohlc_fails_on_high_below_close() -> None:
    corrupted = table([bar(0, high=Decimal("100.0"), close=Decimal("100.9"))])
    assert check_ohlc(corrupted)["status"] == "FAIL"


def test_volumes_fails_on_negative_volume() -> None:
    corrupted = table([bar(0, volume_base=Decimal("-1"))])
    assert check_volumes(corrupted)["status"] == "FAIL"


def test_volumes_fails_on_negative_trade_count() -> None:
    corrupted = table([bar(0, trade_count=-1)])
    assert check_volumes(corrupted)["status"] == "FAIL"


def test_timezone_fails_on_naive_timestamps() -> None:
    naive = CLEAN.set_column(
        0,
        "timestamp_open_utc",
        CLEAN.column("timestamp_open_utc").cast(pa.timestamp("us")),
    )
    assert check_timezone(naive)["status"] == "FAIL"
