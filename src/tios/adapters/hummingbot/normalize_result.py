"""Hummingbot result normalization (T-006-05; EngineAdapter.normalize).

Reads raw.json (executors + pnl_timeseries, see engines/hummingbot/_run_template.py)
and produces canonical artifacts in the run dir: trades.parquet, equity.parquet
(decimal128), normalized_metrics.json — plus a fee/PnL recomputation audit, same
convention as src/tios/adapters/freqtrade/normalize_result.py.

Run: uv run python -m tios.adapters.hummingbot.normalize_result
     --run-dir artifacts/bakeoff/hummingbot/B2/F0_S0/run1
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
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
        ("fee", DEC),
        ("trade_id", pa.int64()),
    ]
)


def d(x: float | int | str) -> Decimal:
    return Decimal(str(x))


Q8 = Decimal("0.00000001")


def q8(x: Decimal) -> Decimal:
    return x.quantize(Q8)


def epoch_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def normalize(run_dir: Path) -> dict[str, Any]:
    raw = json.loads((run_dir / "raw.json").read_text())
    trade_cost = d(raw["trade_cost"])
    fills: list[dict[str, Any]] = []
    fee_audit_max_dev = Decimal(0)
    open_executors = 0

    for i, ex in enumerate(raw["executors"]):
        cfg = ex["config"]
        entry_price = d(cfg["entry_price"])
        qty = d(cfg["amount"])
        side = "buy" if "BUY" in cfg["side"] else "sell"
        # PositionExecutorSimulator.simulate: filled_amount_quote is fixed at
        # entry notional (entry_price * qty); both legs' fees use that same
        # notional (cum_fees_quote == 2 * trade_cost * entry_price * qty).
        leg_fee = q8(trade_cost * entry_price * qty)
        fills.append(
            {
                "ts_fill": epoch_to_iso(ex["timestamp"]),
                "side": side,
                "pair": cfg["trading_pair"],
                "price": q8(entry_price),
                "qty": q8(qty),
                "fee": leg_fee,
                "trade_id": i,
            }
        )
        if ex["status"] != "RunnableStatus.TERMINATED":
            open_executors += 1
            continue
        close_price = d(ex["custom_info"]["close_price"])
        close_side = "sell" if side == "buy" else "buy"
        fills.append(
            {
                "ts_fill": epoch_to_iso(ex["close_timestamp"]),
                "side": close_side,
                "pair": cfg["trading_pair"],
                "price": q8(close_price),
                "qty": q8(qty),
                "fee": leg_fee,
                "trade_id": i,
            }
        )
        # fee/PnL recomputation: (close-open)*qty*side_sign - fees must equal net_pnl_quote
        side_sign = 1 if side == "buy" else -1
        recomputed = (close_price - entry_price) * qty * side_sign - 2 * leg_fee
        dev = abs(recomputed - d(ex["net_pnl_quote"]))
        fee_audit_max_dev = max(fee_audit_max_dev, dev)

    trades_table = pa.Table.from_pylist(
        fills,
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

    # equity: no native account-balance series exposed; reconstruct from
    # pnl_timeseries.total_pnl relative to the configured starting notional
    # (documented assumption, see semantic_notes). Matches
    # engines/hummingbot/_run_template.py build_config's fixed total_amount_quote;
    # not present in the executor config dict, so it isn't read back from raw.json.
    starting_quote = Decimal("1000")
    equity_rows = [
        {"ts": epoch_to_iso(p["timestamp"]), "equity": q8(starting_quote + d(p["total_pnl"]))}
        for p in raw["pnl_timeseries"]
    ]
    equity_table = pa.Table.from_pylist(
        [{"ts": r["ts"], "equity": r["equity"]} for r in equity_rows],
        schema=pa.schema([("ts", pa.string()), ("equity", DEC)]),
    )
    equity_table = equity_table.set_column(0, "ts", equity_table.column("ts").cast(TS))
    pyarrow.parquet.write_table(equity_table, run_dir / "equity.parquet", compression="zstd")

    fee_audit_ok = fee_audit_max_dev < Decimal("0.000001")
    results = raw["results"]
    metrics = {
        "engine": "hummingbot",
        "baseline": raw["baseline"],
        "trades_roundtrips": len(raw["executors"]),
        "fills": len(fills),
        "left_open_executors": open_executors,
        "net_pnl_quote": str(d(results["net_pnl_quote"])),
        "max_drawdown_usd": str(d(results.get("max_drawdown_usd", 0))),
        "sharpe_ratio": str(d(results.get("sharpe_ratio", 0))),
        "total_fees_quote": str(d(results.get("total_fees_quote", 0))),
        "close_types": results.get("close_types", {}),
        "fee_audit": {
            "max_pnl_deviation_quote": str(fee_audit_max_dev),
            "status": "PASS" if fee_audit_ok else "FAIL",
        },
        "semantic_notes": [
            "ts_signal not exposed per executor; controller evaluates signal at "
            "current bar and the engine fills at the same bar's close (no separate "
            "order-placement lag modeled by BacktestingEngineBase)",
            "fee per leg recomputed as trade_cost * entry_price * qty (matches "
            "PositionExecutorSimulator's fixed-notional fee model exactly)",
            "equity_curve reconstructed as configured total_amount_quote + "
            "cumulative total_pnl (no native account-balance series exposed by "
            "BacktestingEngineBase)",
            "prices float64 at engine boundary (declared converter loss, C-hb)",
        ],
    }
    (run_dir / "normalized_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        scenario = next(
            (part.replace("_", "/") for part in run_dir.parts if part.startswith("F")),
            "UNKNOWN",
        )
        raw_path = run_dir / "raw.json"
        manifest = {
            "artifact_id": f"hummingbot-{raw['baseline']}-{raw['trading_pair']}-{scenario}",
            "produced_by": "T-006-05-recovery",
            "status": "RECOVERED_FROM_COMPLETE_RAW",
            "engine": "hummingbot",
            "engine_version": "2.15.0",
            "scenario": scenario,
            "fee_rate_per_side": str(raw["trade_cost"]),
            "input_refs": ["DS-CRYPTO-SPOT-BAKEOFF-V1"],
            "recovery_note": (
                "Host manifest creation was interrupted after raw.json completed; "
                "command provenance is unavailable and is not reconstructed."
            ),
            "files": [
                {"path": "raw.json", "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest()}
            ],
            "schema_version": 1,
        }
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
        f"{m['baseline']}: fills={m['fills']} roundtrips={m['trades_roundtrips']} "
        f"fee_audit={audit['status']} (max dev {audit['max_pnl_deviation_quote']})"
    )


if __name__ == "__main__":
    main()
