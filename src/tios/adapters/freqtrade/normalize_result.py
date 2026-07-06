"""Freqtrade result normalization (T-006-02; EngineAdapter.normalize).

Reads the exported backtest zip and produces canonical artifacts in the run dir:
trades.parquet, equity.parquet (decimal128), normalized_metrics.json — plus a
fee/PnL recomputation audit (blueprint gate "Fee modeling": net results must
reflect configured costs; deviations are itemized, never smoothed over).

Run: uv run python -m tios.adapters.freqtrade.normalize_result
     --run-dir artifacts/bakeoff/freqtrade/B2/F0_S0/run1
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.feather
import pyarrow.parquet

DEC = pa.decimal128(38, 8)
TS = pa.timestamp("us", tz="UTC")

TRADES_SCHEMA = pa.schema(
    [
        ("ts_fill", TS),
        ("side", pa.string()),
        ("pair", pa.string()),
        ("price", DEC),
        ("qty", DEC),
        ("fee", DEC),  # absolute quote-currency fee (converted from freqtrade's ratio)
        ("trade_id", pa.int64()),  # freqtrade round-trip index (buy+sell share one id)
    ]
)


def d(x: float | int | str) -> Decimal:
    return Decimal(str(x))


Q8 = Decimal("0.00000001")


def q8(x: Decimal) -> Decimal:
    """Quantize to the artifact scale decimal128(38,8). Explicit rounding step:
    derived fees can carry >8 fractional digits (price*qty*ratio)."""
    return x.quantize(Q8)


def load_zip(run_dir: Path) -> tuple[dict[str, Any], pa.Table]:
    zips = sorted(run_dir.glob("backtest-result-*.zip"))
    if not zips:
        raise SystemExit(f"no backtest-result zip in {run_dir}")
    with zipfile.ZipFile(zips[-1]) as z:
        names = z.namelist()
        result_json = next(n for n in names if n.endswith(".json") and "config" not in n)
        raw = json.loads(z.read(result_json))
        wallet_name = next(n for n in names if n.endswith("_wallet.feather"))
        wallet = pyarrow.feather.read_table(io.BytesIO(z.read(wallet_name)))
    return raw, wallet


def normalize(run_dir: Path) -> dict[str, Any]:
    raw, wallet = load_zip(run_dir)
    strat_name, res = next(iter(raw["strategy"].items()))

    fills: list[dict[str, Any]] = []
    fee_audit_max_dev = Decimal(0)
    open_trades = 0
    for i, t in enumerate(res["trades"]):
        qty = d(t["amount"])
        open_fee_abs = d(t["open_rate"]) * qty * d(t["fee_open"])
        fills.append(
            {
                "ts_fill": t["open_date"],
                "side": "buy",
                "pair": t["pair"],
                "price": q8(d(t["open_rate"])),
                "qty": q8(qty),
                "fee": q8(open_fee_abs),
                "trade_id": i,
            }
        )
        if t["is_open"]:
            open_trades += 1
            continue
        close_fee_abs = d(t["close_rate"]) * qty * d(t["fee_close"])
        fills.append(
            {
                "ts_fill": t["close_date"],
                "side": "sell",
                "pair": t["pair"],
                "price": q8(d(t["close_rate"])),
                "qty": q8(qty),
                "fee": q8(close_fee_abs),
                "trade_id": i,
            }
        )
        # fee/PnL recomputation: (close-open)*qty - fees must equal profit_abs
        recomputed = (d(t["close_rate"]) - d(t["open_rate"])) * qty - open_fee_abs - close_fee_abs
        dev = abs(recomputed - d(t["profit_abs"]))
        fee_audit_max_dev = max(fee_audit_max_dev, dev)

    trades_table = pa.Table.from_pylist(
        [{**f, "ts_fill": f["ts_fill"].replace(" ", "T")} for f in fills],
        schema=pa.schema(
            [
                ("ts_fill", pa.string()),
                ("side", pa.string()),
                ("pair", pa.string()),
                ("price", DEC),
                ("qty", DEC),
                ("fee", DEC),
                ("trade_id", pa.int64()),
            ]
        ),
    )
    ts = trades_table.column("ts_fill").cast(TS)
    trades_table = trades_table.set_column(0, "ts_fill", ts).cast(TRADES_SCHEMA)
    pyarrow.parquet.write_table(trades_table, run_dir / "trades.parquet", compression="zstd")

    # equity: wallet rows are per-currency; total_quote on USDT rows is total account value
    import pyarrow.compute as pc

    usdt = wallet.filter(pc.equal(wallet.column("currency"), pa.scalar("USDT")))
    equity = pa.table(
        {
            "ts": usdt.column("date").cast(TS),
            "equity": usdt.column("total_quote").cast(pa.float64()).cast(DEC),
        }
    )
    pyarrow.parquet.write_table(equity, run_dir / "equity.parquet", compression="zstd")

    # float tolerance: freqtrade computes in float64; 1e-6 quote units is far below a cent
    fee_audit_ok = fee_audit_max_dev < Decimal("0.000001")
    metrics = {
        "engine": "freqtrade",
        "strategy": strat_name,
        "trades_roundtrips": len(res["trades"]),
        "fills": len(fills),
        "left_open_trades": open_trades,
        "profit_total_abs": str(d(res["profit_total_abs"])),
        "cagr": str(d(res.get("cagr", 0))),
        "max_drawdown_abs": str(d(res.get("max_drawdown_abs", 0))),
        "wins": res.get("wins"),
        "losses": res.get("losses"),
        "fee_audit": {
            "max_pnl_deviation_quote": str(fee_audit_max_dev),
            "status": "PASS" if fee_audit_ok else "FAIL",
        },
        "semantic_notes": [
            "ts_signal not exposed per trade; freqtrade evaluates signals at prior bar close "
            "and fills at next bar open (open_date == fill time)",
            "fees converted from freqtrade per-side ratios to absolute quote amounts",
            "prices float64 at engine boundary (declared converter loss)",
        ],
    }
    (run_dir / "normalized_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    # register normalized artifacts in the run manifest
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in ("trades.parquet", "equity.parquet", "normalized_metrics.json"):
        p = run_dir / name
        entry = {"path": name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        manifest["files"] = [f for f in manifest["files"] if f["path"] != name] + [entry]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    m = normalize(Path(args.run_dir))
    audit = m["fee_audit"]
    print(
        f"{m['strategy']}: fills={m['fills']} roundtrips={m['trades_roundtrips']} "
        f"fee_audit={audit['status']} (max dev {audit['max_pnl_deviation_quote']})"
    )


if __name__ == "__main__":
    main()
