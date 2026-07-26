#!/usr/bin/env python3
"""Deterministic per-trade win/loss report over the demo lane's order ledger.

Zero AI, no network, no venue call: it reads the append-only `orders.jsonl` the demo
lane already writes and folds the fills into buy->sell round trips (one closed position
per pair, a trailing unmatched buy is the open one), then reports each trade's realised
P&L and a summary. Realised P&L uses the venue-reconciled wallet deltas as the source of
truth (`pnl = usd_received - usd_spent`), so the numbers can never disagree with the
fills underneath them. This is the ONLY round-trip folder in the repo: the dashboard's
old private copy was deleted, since a second implementation is a second place to drift.
Fees are charged in the base coin on a buy and the quote coin on a sell; both are in USD.

This is a read-only reporting function. It has no order, credential, venue, or execution
authority and changes no lane state.

Usage:
    uv run python scripts/report_demo_trades.py            # print + write default artifacts
    uv run python scripts/report_demo_trades.py --orders <path> --json <path> --md <path>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORDERS = ROOT / "artifacts" / "trading_domain" / "demo_lane" / "orders.jsonl"
DEFAULT_JSON = ROOT / "artifacts" / "reports" / "DEMO_TRADE_REPORT.json"
DEFAULT_MD = ROOT / "artifacts" / "reports" / "DEMO_TRADE_REPORT.md"


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_filled(orders_path: Path) -> list[dict[str, Any]]:
    """Filled orders only, oldest first — the ledger order the round trips fold over."""
    if not orders_path.is_file():
        return []
    orders: list[dict[str, Any]] = []
    for line in orders_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("ok") is True and row.get("order_status") == "Filled":
            orders.append(row)
    orders.sort(key=lambda o: str(o.get("recorded_at") or ""))
    return orders


def _base_delta(order: dict[str, Any], reconcile: dict[str, Any]) -> float:
    """The traded coin's wallet delta. The venue reconciles per base coin (`AAVE_delta`,
    `ETH_delta`, ...), so a hardcoded `ETH_delta` read 0 for every non-ETH position."""
    symbol = str(order.get("symbol") or "")
    if symbol.endswith("USDT"):
        keyed = reconcile.get(f"{symbol[:-4]}_delta")
        if keyed is not None:
            return _number(keyed)
    # Fallback: the single non-quote delta the venue reported for this fill.
    for name, value in reconcile.items():
        if name.endswith("_delta") and name != "USDT_delta":
            return _number(value)
    return 0.0


def _order_money(order: dict[str, Any]) -> dict[str, float]:
    """Cash/base movement for one order from reconciled wallet deltas (fee already in the delta)."""
    reconcile = order.get("reconcile") or {}
    quote_delta = _number(reconcile.get("USDT_delta"))
    base_delta = _base_delta(order, reconcile)
    price = _number(order.get("avg_price"))
    fee = _number(order.get("fee"))
    return {
        "usd_spent": round(-quote_delta, 4) if quote_delta < 0 else 0.0,
        "usd_received": round(quote_delta, 4) if quote_delta > 0 else 0.0,
        "base_delta": round(base_delta, 8),
        "fee_usd": round(fee * price if order.get("side") == "Buy" else fee, 4),
    }


def round_trips(filled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold fills into buy->sell round trips; unmatched buys stay OPEN (no mark).

    Entries are held PER (symbol, strategy), not in one global slot: the multi-coin and confluence
    lanes hold many positions at once on one shared ledger, so a single slot silently dropped every
    open but the last and could pair coin A's exit against coin B's entry (wrong P&L). `strategy` is
    always part of the key so the breakout and confluence lanes never cross-pair on a shared symbol;
    untagged legacy records read as None and pair only with each other, so an ETH-only ledger folds
    byte-identically to before.
    """
    trips: list[dict[str, Any]] = []
    open_entries: dict[tuple[Any, Any], dict[str, Any]] = {}
    for order in filled:
        money = _order_money(order)
        key = (order.get("symbol"), order.get("strategy"))
        if order.get("side") == "Buy":
            open_entries[key] = {"order": order, "money": money}
        elif (entry := open_entries.pop(key, None)) is not None:
            spent = entry["money"]["usd_spent"]
            received = money["usd_received"]
            pnl = round(received - spent, 4)
            fees = round(entry["money"]["fee_usd"] + money["fee_usd"], 4)
            trips.append(
                {
                    "status": "CLOSED",
                    "symbol": entry["order"].get("symbol"),
                    "strategy": entry["order"].get("strategy"),
                    "opened_at": entry["order"].get("recorded_at"),
                    "closed_at": order.get("recorded_at"),
                    "size_base": entry["money"]["base_delta"],
                    "entry_price_usd": _number(entry["order"].get("avg_price")),
                    "exit_price_usd": _number(order.get("avg_price")),
                    "spent_usd": spent,
                    "received_usd": received,
                    "fees_usd": fees,
                    "pnl_usd": pnl,
                    "pnl_pct": round(pnl / spent * 100, 2) if spent > 0 else None,
                    "outcome": "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT",
                    "signal_ref": entry["order"].get("signal_ref"),
                }
            )
    # Every still-unmatched entry is a live position; insertion order keeps them oldest-first.
    for entry in open_entries.values():
        trips.append(
            {
                "status": "OPEN",
                "symbol": entry["order"].get("symbol"),
                "strategy": entry["order"].get("strategy"),
                "opened_at": entry["order"].get("recorded_at"),
                "size_base": entry["money"]["base_delta"],
                "entry_price_usd": _number(entry["order"].get("avg_price")),
                "spent_usd": entry["money"]["usd_spent"],
                "fees_usd": entry["money"]["fee_usd"],
                "pnl_usd": None,  # unrealised: needs a live mark, which this offline report omits
                "outcome": "OPEN",
                "signal_ref": entry["order"].get("signal_ref"),
            }
        )
    return trips


def summarize(trips: list[dict[str, Any]]) -> dict[str, Any]:
    closed = [t for t in trips if t["status"] == "CLOSED"]
    wins = [t for t in closed if t["outcome"] == "WIN"]
    losses = [t for t in closed if t["outcome"] == "LOSS"]
    realised = round(sum(t["pnl_usd"] for t in closed), 4)
    fees = round(sum(t["fees_usd"] for t in trips), 4)
    return {
        "closed_trades": len(closed),
        "open_trades": sum(1 for t in trips if t["status"] == "OPEN"),
        "wins": len(wins),
        "losses": len(losses),
        "flats": sum(1 for t in closed if t["outcome"] == "FLAT"),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "realised_pnl_usd": realised,
        "total_fees_usd": fees,
        "best_trade_usd": round(max((t["pnl_usd"] for t in closed), default=0.0), 4)
        if closed
        else None,
        "worst_trade_usd": round(min((t["pnl_usd"] for t in closed), default=0.0), 4)
        if closed
        else None,
    }


def build_report(orders_path: Path = DEFAULT_ORDERS) -> dict[str, Any]:
    """Pure: the full per-trade report as data. IO lives in the CLI below."""
    trips = round_trips(load_filled(orders_path))
    return {
        "schema": "tios.demo_trade_report.v1",
        "source": str(orders_path.relative_to(ROOT))
        if orders_path.is_relative_to(ROOT)
        else str(orders_path),
        "environment": "VENUE_DEMO",
        "real_money": False,
        "execution_authority": "NONE",
        "note": "Read-only diagnostic over fake-money demo fills; realised P&L only.",
        "round_trips": trips,
        "summary": summarize(trips),
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    cols = [
        "#",
        "Coin",
        "Opened",
        "Closed",
        "Entry",
        "Exit",
        "Spent $",
        "Recv $",
        "Fees $",
        "P&L $",
        "P&L %",
        "Outcome",
    ]
    lines = [
        "# Demo lane — per-trade win/loss report",
        "",
        f"Source: `{report['source']}` · fake-money VENUE_DEMO · authority NONE (read-only).",
        "",
        f"**{s['closed_trades']} closed** · {s['wins']}W / {s['losses']}L / {s['flats']}F "
        f"· win rate {s['win_rate_pct']}% · realised P&L ${s['realised_pnl_usd']} "
        f"· fees ${s['total_fees_usd']} · {s['open_trades']} open",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "|".join(["--"] * len(cols)) + "|",
    ]
    for i, t in enumerate(report["round_trips"], 1):
        lines.append(
            f"| {i} | {t.get('symbol') or ''} | {t.get('opened_at', '')} | "
            f"{t.get('closed_at', '')} | "
            f"{t.get('entry_price_usd', '')} | {t.get('exit_price_usd', '')} | "
            f"{t.get('spent_usd', '')} | {t.get('received_usd', '')} | {t.get('fees_usd', '')} | "
            f"{t.get('pnl_usd', '')} | {t.get('pnl_pct', '')} | {t['outcome']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Per-trade win/loss report over the demo order ledger."
    )
    parser.add_argument("--orders", type=Path, default=DEFAULT_ORDERS)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--no-write", action="store_true", help="print only; write no artifacts")
    args = parser.parse_args(argv)

    report = build_report(args.orders)
    print(render_markdown(report))
    if not args.no_write:
        for path, text in (
            (args.json, json.dumps(report, indent=2)),
            (args.md, render_markdown(report)),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        print(f"wrote {args.json} and {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
