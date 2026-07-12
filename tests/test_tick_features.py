"""Check aggTrades -> 1-minute microstructure aggregation (no files, no network).

Money/data path: a wrong buy/sell split or VWAP would silently corrupt every
microstructure signal built on it. Hand-built ticks with known answers guard it.
"""

from __future__ import annotations

from decimal import Decimal

import pyarrow as pa

from tios.dataset import tick_features as tf


def _ticks(rows: list[tuple[float, float, int, str]]) -> pa.Table:
    return pa.table(
        {
            "price": pa.array([r[0] for r in rows], pa.float64()),
            "quantity": pa.array([r[1] for r in rows], pa.float64()),
            "transact_time": pa.array([r[2] for r in rows], pa.int64()),
            "is_buyer_maker": pa.array([r[3] for r in rows], pa.string()),
        }
    )


def test_minute_bar_aggregates_flow_and_vwap() -> None:
    ms = 1_609_459_200_000  # 2021-01-01 00:00:00 UTC, all in one minute
    # (price, qty, time, is_buyer_maker) — "false" => taker BOUGHT.
    bars = tf._minute_bars(
        _ticks(
            [
                (100.0, 1.0, ms, "false"),  # buy
                (102.0, 2.0, ms + 1000, "true"),  # sell
                (101.0, 1.0, ms + 2000, "false"),  # buy
            ]
        )
    )
    assert bars.num_rows == 1
    r = bars.to_pylist()[0]
    assert r["open"] == Decimal("100") and r["close"] == Decimal("101")
    assert r["high"] == Decimal("102") and r["low"] == Decimal("100")
    assert r["volume_base"] == Decimal("4")
    assert r["buy_volume_base"] == Decimal("2")  # the two "false" (taker-buy) ticks
    assert r["quote_volume"] == Decimal("405")  # 100 + 204 + 101
    assert r["vwap"] == Decimal("101.25")  # 405 / 4
    assert r["max_trade_size"] == Decimal("2")
    assert r["trade_count"] == 3


def test_two_minutes_split_into_two_bars() -> None:
    ms = 1_609_459_200_000
    bars = tf._minute_bars(_ticks([(100.0, 1.0, ms, "false"), (200.0, 1.0, ms + 60_000, "true")]))
    assert bars.num_rows == 2
    assert bars.column("open").to_pylist() == [Decimal("100"), Decimal("200")]
