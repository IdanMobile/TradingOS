"""Compress raw aggTrades ticks into per-minute microstructure feature bars.

The point of tick data is its INFORMATION, not its 78 GB. This turns each monthly
aggTrades zip into compact 1-minute bars carrying signals the kline data cannot:
tick-level buy/sell imbalance, VWAP, whale-trade size, and trade intensity. The raw
zip can then be discarded; the ~1 GB feature parquet is what we freeze and backtest
against (checksum-reproducible, per the golden rule).

Binance spot aggTrades CSV columns (no header, historically):
  aggId, price, quantity, firstId, lastId, transact_time, is_buyer_maker, is_best_match
is_buyer_maker == false  => the taker BOUGHT (aggressive buy). Timestamp is ms before
2025-01 and µs after (Amendment A1), detected by magnitude.

Run: uv run python -m tios.dataset.tick_features BTCUSDT
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv
import pyarrow.parquet

from tios.dataset.acquire import RAW_ROOT, months
from tios.dataset.normalize import UNIT_THRESHOLD

OUT_ROOT = Path(__file__).resolve().parents[3] / "data" / "tick_features"
DEC = pa.decimal128(38, 8)
AGG_COLUMNS = [
    "agg_id", "price", "quantity", "first_id", "last_id",
    "transact_time", "is_buyer_maker", "is_best_match",
]  # fmt: skip
AGG_TYPES: dict[str, pa.DataType] = {
    "price": pa.float64(),
    "quantity": pa.float64(),
    "transact_time": pa.int64(),
    "is_buyer_maker": pa.string(),
}


def _read_ticks(zip_path: Path) -> pa.Table:
    with zipfile.ZipFile(zip_path) as z:
        data = z.read(z.namelist()[0])
    skip = 1 if data[:6].lower().startswith(b"agg") or data[:5].lower().startswith(b"price") else 0
    return pyarrow.csv.read_csv(
        io.BytesIO(data),
        read_options=pyarrow.csv.ReadOptions(column_names=AGG_COLUMNS, skip_rows=skip),
        convert_options=pyarrow.csv.ConvertOptions(
            column_types=AGG_TYPES,
            include_columns=["price", "quantity", "transact_time", "is_buyer_maker"],
        ),
    )


def _minute_bars(ticks: pa.Table) -> pa.Table:
    """Aggregate raw ticks into 1-minute microstructure bars."""
    t0 = int(ticks.column("transact_time")[0].as_py())
    to_us = 1 if t0 >= UNIT_THRESHOLD else 1000  # Amendment A1: ms -> µs
    us = pc.multiply(ticks.column("transact_time"), pa.scalar(to_us, pa.int64()))
    minute = pc.multiply(pc.divide(us, pa.scalar(60_000_000)), pa.scalar(60_000_000))
    price = ticks.column("price")
    qty = ticks.column("quantity")
    is_buy = pc.equal(pc.utf8_lower(ticks.column("is_buyer_maker")), pa.scalar("false"))
    buy_qty = pc.if_else(is_buy, qty, pa.scalar(0.0))
    notional = pc.multiply(price, qty)

    table = pa.table(
        {
            "minute_us": minute,
            "price": price,
            "qty": qty,
            "buy_qty": buy_qty,
            "notional": notional,
        }
    )
    # use_threads=False: ordered first/last (open/close) aggregators require it.
    grouped = (
        table.group_by("minute_us", use_threads=False)
        .aggregate(
            [
                ("price", "first"),
                ("price", "max"),
                ("price", "min"),
                ("price", "last"),
                ("qty", "sum"),
                ("buy_qty", "sum"),
                ("notional", "sum"),
                ("qty", "max"),
                ("qty", "count"),
            ]
        )
        .sort_by("minute_us")
    )

    vol = grouped.column("qty_sum")
    return pa.table(
        {
            "timestamp_open_utc": grouped.column("minute_us").cast(pa.timestamp("us", tz="UTC")),
            "open": grouped.column("price_first").cast(DEC),
            "high": grouped.column("price_max").cast(DEC),
            "low": grouped.column("price_min").cast(DEC),
            "close": grouped.column("price_last").cast(DEC),
            "volume_base": vol.cast(DEC),
            "buy_volume_base": grouped.column("buy_qty_sum").cast(DEC),
            "quote_volume": grouped.column("notional_sum").cast(DEC),
            "vwap": pc.divide(grouped.column("notional_sum"), vol).cast(DEC),
            "max_trade_size": grouped.column("qty_max").cast(DEC),
            "trade_count": grouped.column("qty_count").cast(pa.int64()),
        }
    )


def build_pair(symbol: str, keep_raw: bool = True) -> dict[str, object]:
    """Stream each month's ticks -> minute bars, so peak memory is one month."""
    bars: list[pa.Table] = []
    present, missing = [], []
    for month in months():
        zp = RAW_ROOT / "aggTrades" / symbol / f"{symbol}-aggTrades-{month}.zip"
        if not zp.exists():
            missing.append(month)
            continue
        bars.append(_minute_bars(_read_ticks(zp)))
        present.append(month)
        if not keep_raw:
            zp.unlink()  # disk-safe mode: discard raw after extracting features
    if not bars:
        return {"symbol": symbol, "months": 0, "missing": len(missing)}
    merged = pa.concat_tables(bars).sort_by("timestamp_open_utc")
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUT_ROOT / f"{symbol}_1m_microstructure.parquet"
    pyarrow.parquet.write_table(merged, out, compression="zstd")
    return {
        "symbol": symbol,
        "months": len(present),
        "missing": len(missing),
        "rows": merged.num_rows,
        "parquet_mb": round(out.stat().st_size / 1e6, 1),
        "parquet_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "coverage_start_utc": str(merged.column("timestamp_open_utc")[0]),
        "coverage_end_utc": str(merged.column("timestamp_open_utc")[-1]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="aggTrades -> 1m microstructure features.")
    parser.add_argument("symbols", nargs="+")
    parser.add_argument("--drop-raw", action="store_true", help="delete raw zips after extract")
    args = parser.parse_args()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = [build_pair(s, keep_raw=not args.drop_raw) for s in args.symbols]
    (OUT_ROOT / "tick_features_manifest.json").write_text(
        json.dumps({"dataset_id": "DS-CRYPTO-MULTI-V1-TICKFEATURES", "pairs": results}, indent=2)
        + "\n"
    )
    for r in results:
        print(f"  {r}")


if __name__ == "__main__":
    main()
