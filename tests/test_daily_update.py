"""Pure-logic checks for the daily updater (no network).

Guards the two things that would silently corrupt a refresh: REST-row -> canonical
conversion, and the append/dedup that must not double-count an overlapping bar.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pyarrow as pa

from tios.dataset.daily_update import _append_dedup, _klines_json_to_raw
from tios.dataset.normalize import to_canonical

HOUR_MS = 3_600_000


def _row(open_ms: int, close: str) -> list[Any]:
    # open,high,low,close,volume, closeTime, quoteVol, count, takerBase, takerQuote, ignore
    return [open_ms, "100", "110", "90", close, "5", open_ms + HOUR_MS - 1,
            "500", 42, "2", "200", "0"]  # fmt: skip


def _canon(open_ms_list: list[int]) -> pa.Table:
    raw = _klines_json_to_raw([_row(ms, "101") for ms in open_ms_list])
    return to_canonical(raw, "ms", "BTCUSDT", "1h")


def test_rest_row_converts_to_canonical() -> None:
    t = _canon([1_609_459_200_000])  # 2021-01-01 00:00:00 UTC
    r = t.to_pylist()[0]
    assert str(r["timestamp_open_utc"]) == "2021-01-01 00:00:00+00:00"
    assert r["open"] == Decimal("100") and r["close"] == Decimal("101")
    assert r["trade_count"] == 42
    assert r["instrument"] == "BTCUSDT" and r["interval"] == "1h"


def test_append_dedup_drops_the_overlapping_bar() -> None:
    base = 1_609_459_200_000
    existing = _canon([base, base + HOUR_MS])  # t0, t1
    fresh = _canon([base + HOUR_MS, base + 2 * HOUR_MS])  # t1 (overlap), t2
    merged, dropped = _append_dedup(existing, fresh)
    assert dropped == 1  # the repeated t1 is dropped
    assert merged.num_rows == 3  # t0, t1, t2
    opens = merged.column("timestamp_open_utc").to_pylist()
    assert opens == sorted(opens) and len(set(opens)) == 3
