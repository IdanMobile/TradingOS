#!/usr/bin/env python3
"""Deterministic per-trade win/loss report over the demo lane's order ledger.

Zero AI, no network, no venue call: it reads the append-only `orders.jsonl` the demo
lane already writes and folds the fills into buy->sell round trips per (symbol, strategy)
(a trailing unmatched buy is the open one, a repeat buy aggregates into that position's cost
basis, a sell with no entry — or a partial fill the venue then cancelled — is reported as an
UNMATCHED fill rather than dropped), then
reports each trade's realised P&L and a summary. Realised P&L uses the reconciled deltas as the
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


# The one terminal venue status besides "Filled" where quantity genuinely executed
# (`demo_eth_lane._TERMINAL_STATUS_MAP`): part of the order filled, the remainder was cancelled.
PARTIAL_FILL_STATUS = "PartiallyFilledCanceled"


def _wallet_moved(row: dict[str, Any]) -> bool:
    """True when the order's before/after reconciliation shows a coin balance actually changed."""
    reconcile = row.get("reconcile") or {}
    return any(
        name.endswith("_delta") and _number(value) != 0.0 for name, value in reconcile.items()
    )


def load_filled(orders_path: Path) -> list[dict[str, Any]]:
    """Orders whose wallet actually moved, oldest first — what the fold below folds over.

    That is every `Filled` order, PLUS a terminal `PartiallyFilledCanceled` one that really settled.
    The lane writes `ok: status.orderStatus == "Filled"` (`demo_eth_lane.place`), so a partial fill
    lands with `ok: False` and was dropped here — BEFORE the fold, which is why v8.152's "nothing
    vanishes silently" guarantee stopped at the fold loop instead of covering the whole
    ledger -> report pipeline. Real (fake-money) wallet movement appeared as neither a round trip
    nor an unmatched fill.

    The admission test is non-zero reconciled deltas, and that is exactly what keeps every other
    `ok: False` record out: the `kill_switch` / `price_unavailable` / `qty_below_step` / `place`
    records carry no `reconcile` key at all, and a plain `Cancelled` / `Rejected` `done` record
    reconciles to zero on both coins. Rejected and failed orders therefore still cannot become
    trades, and the trade counts and win rate are unaffected.
    """
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
        elif row.get("order_status") == PARTIAL_FILL_STATUS and _wallet_moved(row):
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


def _scale_in(entry: dict[str, Any], order: dict[str, Any], money: dict[str, float]) -> None:
    """Merge a second buy on an already-open key into that position's cost basis, in place.

    COST-BASIS AGGREGATION, not a FIFO lot queue, because that is what the lane actually does: an
    entry only fires when the per-key `lane_base` is 0 and an exit always sells the WHOLE
    `lane_base` in one order (`demo_eth_lane.run_cycle`: `side == "BUY" and lane_base == 0` /
    `LaneIntent("Sell", lane_base, "baseCoin", ...)`), so a position is one economic unit and there
    is no per-lot exit to match. FIFO would pair a whole-position exit's proceeds against only the
    oldest lot's spend and OVER-report that trip's P&L while parking the rest as still-open; summing
    the spend cannot over- or under-report, since `pnl = usd_received - usd_spent` then compares the
    same wallet's total out against its total in. (The pre-fix `open_entries[key] = {...}` overwrote
    the first buy outright, dropping its spend, size and fees from the report entirely.)
    """
    prior = entry["money"]
    size = round(prior["base_delta"] + money["base_delta"], 8)
    if size > 0:
        # Size-weighted average fill price. Only reached on a real scale-in, so a single-buy
        # position keeps its raw `avg_price` and the legacy fold stays byte-identical.
        entry["entry_price"] = round(
            (
                entry["entry_price"] * prior["base_delta"]
                + _number(order.get("avg_price")) * money["base_delta"]
            )
            / size,
            8,
        )
    entry["money"] = {
        "usd_spent": round(prior["usd_spent"] + money["usd_spent"], 4),
        "usd_received": 0.0,
        "base_delta": size,
        "fee_usd": round(prior["fee_usd"] + money["fee_usd"], 4),
    }


def _unmatched(order: dict[str, Any], money: dict[str, float], reason: str) -> dict[str, Any]:
    """A filled order this fold could not attach to a position — reported, never priced.

    No `pnl_usd`: inventing one for a sell whose entry is missing would fabricate a trade. The
    identifying detail is what a reconciliation actually needs to go find the fill in the ledger.
    """
    return {
        "reason": reason,
        "symbol": order.get("symbol"),
        "strategy": order.get("strategy"),
        "at": order.get("recorded_at"),
        "side": order.get("side"),
        "size_base": money["base_delta"],
        "price_usd": _number(order.get("avg_price")),
        "spent_usd": money["usd_spent"],
        "received_usd": money["usd_received"],
        "fees_usd": money["fee_usd"],
        "signal_ref": order.get("signal_ref"),
    }


def fold_fills(filled: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fold fills into (round trips, unmatched fills); unmatched buys stay OPEN (no mark).

    Entries are held PER (symbol, strategy), not in one global slot: the multi-coin and confluence
    lanes hold many positions at once on one shared ledger, so a single slot silently dropped every
    open but the last and could pair coin A's exit against coin B's entry (wrong P&L). `strategy` is
    always part of the key so the breakout and confluence lanes never cross-pair on a shared symbol;
    untagged legacy records read as None and pair only with each other, so an ETH-only ledger folds
    byte-identically to before. A repeat buy on an open key aggregates into its cost basis
    (`_scale_in`); a sell with no open entry, a fill with neither side, or a partially-filled-then-
    cancelled order is returned as an UNMATCHED fill instead of being dropped silently — money
    moved, so the report has to say so.
    """
    trips: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    open_entries: dict[tuple[Any, Any], dict[str, Any]] = {}
    for order in filled:
        money = _order_money(order)
        key = (order.get("symbol"), order.get("strategy"))
        side = order.get("side")
        if order.get("order_status") == PARTIAL_FILL_STATUS:
            # UNMATCHED, not folded, because THE LANE ITSELF does not treat this fill as a position
            # event: `demo_eth_lane.run_cycle` only credits `lane_base` under
            # `if action.get("ok"): lane_base += reconcile[f"{base}_delta"]`, and
            # `entry_price_from_ledger` likewise requires `record.get("ok")` — both False here.
            # Folding it as an entry would invent a position no exit will ever close (an exit sells
            # only the `lane_base` the lane believes it holds), and folding it as an exit would book
            # a whole position's cost basis against a fraction of its proceeds — a fabricated P&L
            # in the flattering direction. Surfacing it keeps the wallet movement visible and
            # leaves the trip pairing, trade counts and win rate untouched. The exact status test
            # (not `!= "Filled"`) means rows without the field fold exactly as they always did.
            unmatched.append(_unmatched(order, money, "partial_fill_cancelled"))
        elif side == "Buy":
            if (open_entry := open_entries.get(key)) is not None:
                _scale_in(open_entry, order, money)
            else:
                open_entries[key] = {
                    "order": order,
                    "money": money,
                    "entry_price": _number(order.get("avg_price")),
                }
        elif side != "Sell":
            unmatched.append(_unmatched(order, money, "unknown_side"))
        elif (entry := open_entries.pop(key, None)) is None:
            # Entry predates this ledger window, a duplicate/double exit, or a genuine
            # reconciliation fault. All three are real problems; none may pass silently.
            unmatched.append(_unmatched(order, money, "orphan_sell"))
        else:
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
                    "entry_price_usd": entry["entry_price"],
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
                "entry_price_usd": entry["entry_price"],
                "spent_usd": entry["money"]["usd_spent"],
                "fees_usd": entry["money"]["fee_usd"],
                "pnl_usd": None,  # unrealised: needs a live mark, which this offline report omits
                "outcome": "OPEN",
                "signal_ref": entry["order"].get("signal_ref"),
            }
        )
    return trips, unmatched


def round_trips(filled: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The round trips only (see `fold_fills` for the unmatched fills alongside them)."""
    return fold_fills(filled)[0]


def summarize(
    trips: list[dict[str, Any]], unmatched: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Totals over the trip list. `unmatched` (from `fold_fills`) adds the reconciliation counters;
    omitting it reports them as None — "not measured" rather than a false "none found"."""
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
        # Reconciliation counters. Non-zero means money moved on a fill this fold could not attach
        # to a position, so the realised total above is incomplete until it is explained. The fees
        # are kept OUT of `total_fees_usd` (its definition is unchanged: trips only) and surfaced
        # here instead, so the spend is still visible rather than lost.
        "unmatched_fills": None if unmatched is None else len(unmatched),
        "unmatched_fees_usd": None
        if unmatched is None
        else round(sum(u["fees_usd"] for u in unmatched), 4),
    }


def build_report(orders_path: Path = DEFAULT_ORDERS) -> dict[str, Any]:
    """Pure: the full per-trade report as data. IO lives in the CLI below."""
    trips, unmatched = fold_fills(load_filled(orders_path))
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
        "unmatched_fills": unmatched,
        "summary": summarize(trips, unmatched),
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
    unmatched = report.get("unmatched_fills") or []
    if unmatched:
        # Only rendered when non-zero: a clean ledger reads exactly as it did before.
        lines += [
            "",
            f"## Unmatched fills — {len(unmatched)} (RECONCILE)",
            "",
            "Filled orders that could not be attached to a position: money moved and no trade "
            "above accounts for it, so the realised total is incomplete until each is explained. "
            f"No P&L is invented for them; their fees total "
            f"${report['summary']['unmatched_fees_usd']}.",
            "",
            "| # | Reason | Coin | Strategy | At | Side | Spent $ | Recv $ | Fees $ |",
            "|--|--|--|--|--|--|--|--|--|",
        ]
        for i, u in enumerate(unmatched, 1):
            lines.append(
                f"| {i} | {u['reason']} | {u.get('symbol') or ''} | {u.get('strategy') or ''} | "
                f"{u.get('at') or ''} | {u.get('side') or ''} | {u['spent_usd']} | "
                f"{u['received_usd']} | {u['fees_usd']} |"
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
