"""Segment executed B2 holdout trades by ex-post observable regimes."""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "validation" / "B2_F0_S0"


def main() -> None:
    trades = pyarrow.parquet.read_table(BASE / "runs" / "holdout" / "trades.parquet").to_pylist()
    grouped: dict[int, list[dict]] = defaultdict(list)
    for row in trades:
        grouped[int(row["trade_id"])].append(row)
    entries = []
    pnl_by_id = {}
    for trade_id, fills in grouped.items():
        buys = [row for row in fills if row["side"] == "buy"]
        sells = [row for row in fills if row["side"] == "sell"]
        if not buys or not sells:
            continue
        buy, sell = buys[0], sells[-1]
        pnl_by_id[trade_id] = (
            (Decimal(str(sell["price"])) - Decimal(str(buy["price"]))) * Decimal(str(buy["qty"]))
            - Decimal(str(buy["fee"]))
            - Decimal(str(sell["fee"]))
        )
        entries.append(
            {
                "trade_id": trade_id,
                "ts": buy["ts_fill"],
                "instrument": buy["pair"].replace("/", ""),
            }
        )
    conn = duckdb.connect()
    paths = [
        str(ROOT / "data" / "normalized" / "BTCUSDT_5m.parquet"),
        str(ROOT / "data" / "normalized" / "ETHUSDT_5m.parquet"),
    ]
    quoted = ", ".join(f"'{path}'" for path in paths)
    conn.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW features AS
        WITH source AS (
          SELECT timestamp_open_utc AS ts, instrument,
                 CAST(close AS DOUBLE) AS close, CAST(volume_base AS DOUBLE) AS volume
          FROM read_parquet([{quoted}])
          WHERE timestamp_open_utc >= TIMESTAMPTZ '2025-05-25T00:00:00Z'
            AND timestamp_open_utc <= TIMESTAMPTZ '2026-06-30T23:55:00Z'
        ), returns AS (
          SELECT *,
                 LN(close / LAG(close) OVER (PARTITION BY instrument ORDER BY ts)) AS log_ret,
                 close / LAG(close, 12) OVER (PARTITION BY instrument ORDER BY ts) - 1 AS trend
          FROM source
        )
        SELECT *,
               STDDEV_SAMP(log_ret) OVER (
                 PARTITION BY instrument ORDER BY ts ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
               ) AS realized_vol
        FROM returns
        """
    )
    thresholds = conn.execute(
        """
        SELECT median(realized_vol), median(abs(trend)), median(volume)
        FROM features
        WHERE realized_vol IS NOT NULL AND trend IS NOT NULL
        """
    ).fetchone()
    vol_threshold, trend_threshold, volume_threshold = thresholds
    entry_table = pa.table(
        {
            "trade_id": [row["trade_id"] for row in entries],
            "ts": pa.array([row["ts"] for row in entries]),
            "instrument": [row["instrument"] for row in entries],
        }
    )
    conn.register("entries", entry_table)
    regime_rows = conn.execute(
        """
        SELECT e.trade_id,
               COALESCE(f.realized_vol >= ?, false) AS vol_high,
               COALESCE(f.trend >= 0, false) AS trend_positive,
               COALESCE(f.volume >= ?, false) AS volume_high
        FROM entries e
        LEFT JOIN features f ON f.ts = e.ts AND f.instrument = e.instrument
        """,
        [vol_threshold, volume_threshold],
    ).fetchall()
    by_regime: dict[str, list[Decimal]] = defaultdict(list)
    for trade_id, vol_high, trend_positive, volume_high in regime_rows:
        label = "_".join(
            [
                "vol_high" if vol_high else "vol_low",
                "trend_pos" if trend_positive else "trend_neg",
                "volume_high" if volume_high else "volume_low",
            ]
        )
        by_regime[label].append(pnl_by_id[int(trade_id)])
    regimes = [
        {
            "regime": label,
            "trades": len(values),
            "net_pnl_quote": str(sum(values, Decimal(0))),
            "average_pnl_quote": str(sum(values, Decimal(0)) / len(values)),
        }
        for label, values in sorted(by_regime.items())
    ]
    payload = {
        "status": "COMPLETE_EX_POST_SEGMENTATION",
        "dataset": "DS-CRYPTO-SPOT-BAKEOFF-V1",
        "strategy": "B2MaCrossover",
        "window": "2025-05-25 to 2026-06-30",
        "method": (
            "12-bar realized volatility, 12-bar close trend, and volume medians; "
            "descriptive ex-post labels only"
        ),
        "thresholds": {
            "realized_vol_median": str(vol_threshold),
            "absolute_trend_median": str(trend_threshold),
            "volume_median": str(volume_threshold),
        },
        "regimes": regimes,
        "interpretation": (
            "Regime labels describe observed conditions; they are not predictive claims."
        ),
    }
    (BASE / "regime_report.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {BASE / 'regime_report.json'} ({len(regimes)} regimes)")


if __name__ == "__main__":
    main()
