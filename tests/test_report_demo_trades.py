"""Deterministic checks for the demo per-trade win/loss report."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.report_demo_trades as rpt  # noqa: E402


def _order(side: str, usdt: float, eth: float, price: str, fee: str, at: str) -> dict[str, object]:
    return {
        "ok": True,
        "order_status": "Filled",
        "side": side,
        "avg_price": price,
        "fee": fee,
        "recorded_at": at,
        "reconcile": {"USDT_delta": usdt, "ETH_delta": eth},
        "signal_ref": "SIG-x",
    }


def _write(tmp_path: Path, rows: list[dict[str, object]]) -> Path:
    p = tmp_path / "orders.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_winning_losing_and_open_round_trips(tmp_path: Path) -> None:
    orders = _write(
        tmp_path,
        [
            # trade 1: buy 25 -> sell 30 = +5 WIN
            _order("Buy", -25.0, 0.0134, "1862.37", "0.0000134", "2026-07-20T14:15:58+00:00"),
            _order("Sell", 30.0, -0.0134, "2238.80", "0.03", "2026-07-20T18:00:00+00:00"),
            # trade 2: buy 25 -> sell 20 = -5 LOSS
            _order("Buy", -25.0, 0.0130, "1923.00", "0.0000130", "2026-07-21T10:00:00+00:00"),
            _order("Sell", 20.0, -0.0130, "1538.00", "0.02", "2026-07-21T12:00:00+00:00"),
            # trade 3: unmatched buy -> OPEN
            _order("Buy", -25.0, 0.0140, "1785.00", "0.0000140", "2026-07-22T09:00:00+00:00"),
        ],
    )
    report = rpt.build_report(orders)
    trips = report["round_trips"]
    assert [t["outcome"] for t in trips] == ["WIN", "LOSS", "OPEN"]
    assert trips[0]["pnl_usd"] == 5.0 and trips[1]["pnl_usd"] == -5.0
    assert trips[2]["status"] == "OPEN" and trips[2]["pnl_usd"] is None

    s = report["summary"]
    assert s["closed_trades"] == 2 and s["wins"] == 1 and s["losses"] == 1
    assert s["win_rate_pct"] == 50.0
    assert s["realised_pnl_usd"] == 0.0  # +5 - 5
    assert s["best_trade_usd"] == 5.0 and s["worst_trade_usd"] == -5.0
    assert s["open_trades"] == 1
    assert report["execution_authority"] == "NONE" and report["real_money"] is False


def test_empty_ledger_is_safe(tmp_path: Path) -> None:
    report = rpt.build_report(tmp_path / "missing.jsonl")
    assert report["round_trips"] == []
    assert report["summary"]["closed_trades"] == 0 and report["summary"]["win_rate_pct"] is None


def test_markdown_renders_header_and_rows(tmp_path: Path) -> None:
    orders = _write(
        tmp_path,
        [
            _order("Buy", -25.0, 0.0134, "1862.37", "0.0000134", "2026-07-20T14:15:58+00:00"),
            _order("Sell", 30.0, -0.0134, "2238.80", "0.03", "2026-07-20T18:00:00+00:00"),
        ],
    )
    md = rpt.render_markdown(rpt.build_report(orders))
    assert "per-trade win/loss report" in md
    assert "authority NONE" in md
    assert "WIN" in md


def _coin_order(
    symbol: str, strategy: str | None, side: str, usdt: float, base: float, at: str
) -> dict[str, object]:
    """A fill on any coin: the venue reconciles the base coin under its own `<COIN>_delta` key."""
    return {
        "ok": True,
        "order_status": "Filled",
        "symbol": symbol,
        "strategy": strategy,
        "side": side,
        "avg_price": "10",
        "fee": "0.001",
        "recorded_at": at,
        "reconcile": {"USDT_delta": usdt, f"{symbol[:-4]}_delta": base},
    }


def test_concurrent_positions_on_many_coins_all_surface(tmp_path: Path) -> None:
    # The multi-coin/confluence lanes hold many positions at once on ONE shared ledger. A single
    # global entry slot silently dropped every open but the last (reporting "1 open" while 3 were
    # live) and could pair one coin's exit against another coin's entry. Pairing is per-symbol.
    rows = [
        _coin_order("BTCUSDT", "ACT", "Buy", -25.0, 0.0004, "2026-07-26T14:53:00+00:00"),
        _coin_order("SOLUSDT", "ACT", "Buy", -25.0, 0.33, "2026-07-26T14:53:10+00:00"),
        _coin_order("LINKUSDT", "ACT", "Buy", -25.0, 2.9, "2026-07-26T14:53:20+00:00"),
        # SOL exits; BTC and LINK must stay open and keep their own entries.
        _coin_order("SOLUSDT", "ACT", "Sell", 26.0, -0.33, "2026-07-26T14:58:00+00:00"),
    ]
    trips = rpt.round_trips(rpt.load_filled(_write(tmp_path, rows)))
    closed = [t for t in trips if t["status"] == "CLOSED"]
    opens = [t for t in trips if t["status"] == "OPEN"]
    assert len(closed) == 1 and closed[0]["symbol"] == "SOLUSDT"
    assert closed[0]["pnl_usd"] == 1.0  # 26.0 received - 25.0 spent, SOL's own entry
    assert [t["symbol"] for t in opens] == ["BTCUSDT", "LINKUSDT"]  # oldest-first, none dropped
    assert rpt.summarize(trips)["open_trades"] == 2


def test_same_coin_in_two_lanes_never_cross_pairs(tmp_path: Path) -> None:
    # ETHUSDT trades in both the legacy breakout lane (untagged) and the confluence lane. An exit in
    # one lane must close ITS OWN entry, never the other lane's, or the P&L is attributed wrongly.
    rows = [
        _coin_order("ETHUSDT", None, "Buy", -25.0, 0.013, "2026-07-26T14:00:00+00:00"),
        _coin_order("ETHUSDT", "ACT", "Buy", -25.0, 0.013, "2026-07-26T14:53:00+00:00"),
        _coin_order("ETHUSDT", "ACT", "Sell", 27.0, -0.013, "2026-07-26T14:58:00+00:00"),
    ]
    trips = rpt.round_trips(rpt.load_filled(_write(tmp_path, rows)))
    closed = [t for t in trips if t["status"] == "CLOSED"]
    opens = [t for t in trips if t["status"] == "OPEN"]
    assert len(closed) == 1 and closed[0]["strategy"] == "ACT" and closed[0]["pnl_usd"] == 2.0
    assert len(opens) == 1 and opens[0]["strategy"] is None  # the legacy position is still open


def test_base_size_reads_the_traded_coins_own_delta(tmp_path: Path) -> None:
    # A hardcoded ETH_delta reported size 0 for every non-ETH position; the size must come from the
    # traded coin's own reconcile key.
    rows = [_coin_order("AAVEUSDT", "ACT", "Buy", -25.0, 0.25945356, "2026-07-26T14:53:00+00:00")]
    trips = rpt.round_trips(rpt.load_filled(_write(tmp_path, rows)))
    assert trips[0]["size_base"] == 0.25945356


def _priced_order(
    symbol: str, side: str, usdt: float, base: float, price: str, fee: str, at: str
) -> dict[str, object]:
    """A tagged fill with an explicit price/fee, for cost-basis and fee-total assertions."""
    return {
        "ok": True,
        "order_status": "Filled",
        "symbol": symbol,
        "strategy": "ACT",
        "side": side,
        "avg_price": price,
        "fee": fee,
        "recorded_at": at,
        "reconcile": {"USDT_delta": usdt, f"{symbol[:-4]}_delta": base},
        "signal_ref": f"SIG-{at}",
    }


def test_scale_in_aggregates_cost_basis_and_never_drops_the_first_buy(tmp_path: Path) -> None:
    # FAILS pre-fix: a second Buy on an already-open (symbol, strategy) did
    # `open_entries[key] = {...}`, overwriting the first buy, so its 25 USDT of spend, its size and
    # its fee vanished and the exit's 60 USDT was booked against 25 spent (+35 instead of +10).
    # The lane exits the WHOLE position in one order, so the exit's proceeds must face the WHOLE
    # cost basis.
    rows = [
        _priced_order("SOLUSDT", "Buy", -25.0, 0.25, "100", "0.0025", "2026-07-26T14:00:00+00:00"),
        _priced_order("SOLUSDT", "Buy", -25.0, 0.20, "125", "0.0020", "2026-07-26T14:10:00+00:00"),
        _priced_order(
            "SOLUSDT", "Sell", 60.0, -0.45, "133.33", "0.06", "2026-07-26T15:00:00+00:00"
        ),
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert unmatched == []
    assert len(trips) == 1
    trip = trips[0]
    assert trip["spent_usd"] == 50.0  # both buys, not just the last one
    assert trip["size_base"] == 0.45
    assert trip["pnl_usd"] == 10.0  # 60 received - 50 spent
    assert trip["pnl_pct"] == 20.0
    # Fees: 0.0025*100 + 0.0020*125 (base-coin buy fees priced at fill) + 0.06 quote sell fee.
    assert trip["fees_usd"] == 0.56
    # Size-weighted average entry: (100*0.25 + 125*0.20) / 0.45.
    assert trip["entry_price_usd"] == round(50.0 / 0.45, 8)
    assert trip["opened_at"] == "2026-07-26T14:00:00+00:00"  # the position opened on the FIRST buy
    summary = rpt.summarize(trips, unmatched)
    assert summary["realised_pnl_usd"] == 10.0 and summary["closed_trades"] == 1
    assert summary["total_fees_usd"] == 0.56  # internally consistent with the trip list
    assert summary["unmatched_fills"] == 0 and summary["unmatched_fees_usd"] == 0.0


def test_scale_in_still_open_reports_the_whole_cost_basis(tmp_path: Path) -> None:
    # FAILS pre-fix: the still-open scaled-in position reported only the last buy (25 spent), so the
    # report understated live exposure by half.
    rows = [
        _priced_order("SOLUSDT", "Buy", -25.0, 0.25, "100", "0.0025", "2026-07-26T14:00:00+00:00"),
        _priced_order("SOLUSDT", "Buy", -25.0, 0.20, "125", "0.0020", "2026-07-26T14:10:00+00:00"),
    ]
    trips = rpt.round_trips(rpt.load_filled(_write(tmp_path, rows)))
    assert len(trips) == 1 and trips[0]["status"] == "OPEN"
    assert trips[0]["spent_usd"] == 50.0 and trips[0]["size_base"] == 0.45
    assert trips[0]["fees_usd"] == 0.5 and trips[0]["pnl_usd"] is None


def test_sell_closes_its_own_key_while_a_scaled_in_position_stays_open(tmp_path: Path) -> None:
    # Under cost-basis aggregation a sell closes the WHOLE position on its own key and touches no
    # other key: BTC's two buys are one open position, SOL's single buy closes cleanly.
    rows = [
        _priced_order("BTCUSDT", "Buy", -25.0, 0.0004, "62500", "0", "2026-07-26T14:00:00+00:00"),
        _priced_order("SOLUSDT", "Buy", -25.0, 0.25, "100", "0", "2026-07-26T14:01:00+00:00"),
        _priced_order("BTCUSDT", "Buy", -25.0, 0.0004, "62500", "0", "2026-07-26T14:02:00+00:00"),
        _priced_order("SOLUSDT", "Sell", 27.0, -0.25, "108", "0", "2026-07-26T14:03:00+00:00"),
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert unmatched == []
    closed = [t for t in trips if t["status"] == "CLOSED"]
    opens = [t for t in trips if t["status"] == "OPEN"]
    assert len(closed) == 1 and closed[0]["symbol"] == "SOLUSDT" and closed[0]["pnl_usd"] == 2.0
    assert len(opens) == 1 and opens[0]["symbol"] == "BTCUSDT" and opens[0]["spent_usd"] == 50.0
    summary = rpt.summarize(trips, unmatched)
    assert summary["closed_trades"] == 1 and summary["open_trades"] == 1
    assert summary["realised_pnl_usd"] == 2.0


def test_orphan_and_duplicate_sells_are_surfaced_never_priced(tmp_path: Path) -> None:
    # FAILS pre-fix: both sells hit the `pop(...) is not None` else-branch and were skipped in
    # total silence — money left the position and the report said nothing. A sell with no entry is
    # an entry outside the window, a double exit, or a reconciliation fault; all must be visible.
    rows = [
        # orphan: the ETH entry predates this ledger window
        _priced_order("ETHUSDT", "Sell", 30.0, -0.013, "2300", "0.03", "2026-07-26T14:00:00+00:00"),
        _priced_order("SOLUSDT", "Buy", -25.0, 0.25, "100", "0", "2026-07-26T14:01:00+00:00"),
        _priced_order("SOLUSDT", "Sell", 27.0, -0.25, "108", "0", "2026-07-26T14:02:00+00:00"),
        # duplicate: SOL already exited above
        _priced_order("SOLUSDT", "Sell", 27.0, -0.25, "108", "0.02", "2026-07-26T14:03:00+00:00"),
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    # Exactly one real trade; neither orphan became a trip or got a P&L number.
    assert [t["status"] for t in trips] == ["CLOSED"]
    assert trips[0]["symbol"] == "SOLUSDT" and trips[0]["pnl_usd"] == 2.0
    assert len(unmatched) == 2
    assert all("pnl_usd" not in u and "outcome" not in u for u in unmatched)
    assert [u["reason"] for u in unmatched] == ["orphan_sell", "orphan_sell"]
    # Identifying detail a reconciliation needs to find the fill in the ledger.
    assert unmatched[0]["symbol"] == "ETHUSDT" and unmatched[0]["strategy"] == "ACT"
    assert unmatched[0]["at"] == "2026-07-26T14:00:00+00:00" and unmatched[0]["side"] == "Sell"
    assert unmatched[0]["received_usd"] == 30.0 and unmatched[0]["fees_usd"] == 0.03
    assert unmatched[1]["symbol"] == "SOLUSDT" and unmatched[1]["at"] == "2026-07-26T14:03:00+00:00"

    summary = rpt.summarize(trips, unmatched)
    assert summary["closed_trades"] == 1 and summary["open_trades"] == 0
    assert summary["wins"] == 1 and summary["losses"] == 0
    assert summary["unmatched_fills"] == 2
    assert summary["unmatched_fees_usd"] == 0.05  # 0.03 + 0.02, kept out of total_fees_usd
    assert summary["total_fees_usd"] == 0.0  # unchanged definition: trips only
    assert summary["realised_pnl_usd"] == 2.0  # no invented P&L from the orphans

    md = rpt.render_markdown(rpt.build_report(_write(tmp_path, rows)))
    assert "## Unmatched fills — 2 (RECONCILE)" in md
    assert "orphan_sell" in md and "2026-07-26T14:03:00+00:00" in md


def test_fill_with_no_recognised_side_is_surfaced_not_dropped(tmp_path: Path) -> None:
    # FAILS pre-fix: a filled record whose side is neither Buy nor Sell fell through the if/elif
    # into nothing at all.
    rows = [_priced_order("SOLUSDT", "", -25.0, 0.25, "100", "0.01", "2026-07-26T14:00:00+00:00")]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert trips == []
    assert [u["reason"] for u in unmatched] == ["unknown_side"]
    assert unmatched[0]["spent_usd"] == 25.0 and unmatched[0]["symbol"] == "SOLUSDT"


def test_clean_ledger_reports_no_unmatched_fills_and_no_markdown_section(tmp_path: Path) -> None:
    rows = [
        _order("Buy", -25.0, 0.0134, "1862.37", "0.0000134", "2026-07-20T14:15:58+00:00"),
        _order("Sell", 30.0, -0.0134, "2238.80", "0.03", "2026-07-20T18:00:00+00:00"),
    ]
    report = rpt.build_report(_write(tmp_path, rows))
    assert report["unmatched_fills"] == []
    assert report["summary"]["unmatched_fills"] == 0
    assert "Unmatched fills" not in rpt.render_markdown(report)
    # summarize() without the unmatched list reports the counters as "not measured", never a
    # false "none found" (the dashboard's equity curve calls it with trips only).
    bare = rpt.summarize(report["round_trips"])
    assert bare["unmatched_fills"] is None and bare["unmatched_fees_usd"] is None
    assert bare["realised_pnl_usd"] == 5.0 and bare["closed_trades"] == 1


def test_legacy_eth_only_ledger_folds_byte_identically(tmp_path: Path) -> None:
    # The untagged single-coin ETH ledger keys (None, None) and must fold EXACTLY as it did before
    # the scale-in/orphan work: same trip list, key for key, value for value.
    rows = [
        _order("Buy", -25.0, 0.0134, "1862.37", "0.0000134", "2026-07-20T14:15:58+00:00"),
        _order("Sell", 30.0, -0.0134, "2238.80", "0.03", "2026-07-20T18:00:00+00:00"),
        _order("Buy", -25.0, 0.0140, "1785.00", "0.0000140", "2026-07-22T09:00:00+00:00"),
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert unmatched == []
    assert trips == [
        {
            "status": "CLOSED",
            "symbol": None,
            "strategy": None,
            "opened_at": "2026-07-20T14:15:58+00:00",
            "closed_at": "2026-07-20T18:00:00+00:00",
            "size_base": 0.0134,
            "entry_price_usd": 1862.37,
            "exit_price_usd": 2238.8,
            "spent_usd": 25.0,
            "received_usd": 30.0,
            "fees_usd": 0.055,
            "pnl_usd": 5.0,
            "pnl_pct": 20.0,
            "outcome": "WIN",
            "signal_ref": "SIG-x",
        },
        {
            "status": "OPEN",
            "symbol": None,
            "strategy": None,
            "opened_at": "2026-07-22T09:00:00+00:00",
            "size_base": 0.014,
            "entry_price_usd": 1785.0,
            "spent_usd": 25.0,
            "fees_usd": 0.025,
            "pnl_usd": None,
            "outcome": "OPEN",
            "signal_ref": "SIG-x",
        },
    ]


def test_partially_filled_cancelled_order_reaches_the_report(tmp_path: Path) -> None:
    # FAILS pre-fix: `load_filled` admitted a row only on `ok is True and order_status == "Filled"`,
    # but demo_eth_lane.place() writes `ok: status.orderStatus == "Filled"`, so a terminal
    # PartiallyFilledCanceled order (part executed, remainder cancelled) lands with ok=False and was
    # dropped BEFORE the fold — real wallet movement appearing as neither a trip nor an unmatched
    # fill. Pre-fix this asserted 0 unmatched and 0 visible dollars.
    partial = _priced_order(
        "SOLUSDT", "Buy", -12.5, 0.125, "100", "0.00125", "2026-07-26T14:00:00+00:00"
    )
    partial["ok"] = False
    partial["order_status"] = "PartiallyFilledCanceled"
    partial["cum_exec_qty"] = "0.125"
    rows = [
        partial,
        _priced_order("SOLUSDT", "Buy", -25.0, 0.25, "100", "0", "2026-07-26T14:01:00+00:00"),
        _priced_order("SOLUSDT", "Sell", 27.0, -0.25, "108", "0", "2026-07-26T14:02:00+00:00"),
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    # Surfaced with its own reason, never priced, never a trip.
    assert [u["reason"] for u in unmatched] == ["partial_fill_cancelled"]
    assert "pnl_usd" not in unmatched[0] and "outcome" not in unmatched[0]
    assert unmatched[0]["spent_usd"] == 12.5 and unmatched[0]["size_base"] == 0.125
    assert unmatched[0]["at"] == "2026-07-26T14:00:00+00:00"
    # ...and it does not contaminate the real trade on the same key: the lane never credited that
    # partial to lane_base (`run_cycle` gates on `action.get("ok")`), so the following buy is the
    # whole cost basis of the following exit.
    assert [t["status"] for t in trips] == ["CLOSED"]
    assert trips[0]["spent_usd"] == 25.0 and trips[0]["pnl_usd"] == 2.0
    summary = rpt.summarize(trips, unmatched)
    assert summary["closed_trades"] == 1 and summary["wins"] == 1  # counts/win rate untouched
    assert summary["realised_pnl_usd"] == 2.0  # no invented P&L
    assert summary["unmatched_fills"] == 1 and summary["unmatched_fees_usd"] == 0.125
    assert "partial_fill_cancelled" in rpt.render_markdown(rpt.build_report(_write(tmp_path, rows)))


def test_failed_orders_never_become_trades(tmp_path: Path) -> None:
    # The other side of the same guard: widening load_filled must NOT let ok=False records that
    # moved no money start counting. The lane's pre-send rejects carry no `reconcile` key at all;
    # a terminal Cancelled/Rejected `done` record reconciles to zero on both coins.
    rejects: list[dict[str, object]] = [
        {"ok": False, "stage": "kill_switch", "side": "Buy", "recorded_at": "2026-07-26T14:00:00Z"},
        {"ok": False, "stage": "place", "side": "Buy", "recorded_at": "2026-07-26T14:01:00Z"},
        {
            "ok": False,
            "stage": "done",
            "order_status": "Rejected",
            "side": "Buy",
            "symbol": "SOLUSDT",
            "recorded_at": "2026-07-26T14:02:00Z",
            "reconcile": {"USDT_delta": 0.0, "SOL_delta": 0.0},
        },
        {
            "ok": False,
            "stage": "done",
            "order_status": "PartiallyFilledCanceled",  # cancelled before anything executed
            "side": "Buy",
            "symbol": "SOLUSDT",
            "recorded_at": "2026-07-26T14:03:00Z",
            "reconcile": {"USDT_delta": 0.0, "SOL_delta": 0.0},
        },
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rejects)))
    assert trips == [] and unmatched == []
    assert rpt.summarize(trips, unmatched)["closed_trades"] == 0


def test_three_successive_scale_ins_keep_the_money_exact(tmp_path: Path) -> None:
    # No test locked 3+ successive scale-ins on one key: each `_scale_in` rounds spend/fees to 4dp
    # and size to 8dp and recomputes a size-weighted entry, so repeated folding is where rounding
    # drift would accumulate. Amounts are deliberately awkward (7 dp of size, 4+ dp of fee).
    buys = [
        ("-33.3333", 0.3333333, "100.0001", "0.0003333", "2026-07-26T14:00:00+00:00"),
        ("-16.6667", 0.1481481, "112.5003", "0.0001481", "2026-07-26T14:10:00+00:00"),
        ("-24.9999", 0.1999992, "125.0000", "0.0002000", "2026-07-26T14:20:00+00:00"),
        ("-11.1111", 0.0793650, "140.0000", "0.0000794", "2026-07-26T14:30:00+00:00"),
    ]
    rows = [
        _priced_order("SOLUSDT", "Buy", float(usdt), base, price, fee, at)
        for usdt, base, price, fee, at in buys
    ]
    trips = rpt.round_trips(rpt.load_filled(_write(tmp_path, rows)))
    assert len(trips) == 1 and trips[0]["status"] == "OPEN"
    open_trip = trips[0]
    total_spent = round(sum(-float(b[0]) for b in buys), 4)
    total_size = round(sum(b[1] for b in buys), 8)
    total_fees = round(sum(float(b[3]) * float(b[2]) for b in buys), 4)
    # EXACT, not approximate: aggregation must not lose or gain a cent across four folds.
    assert open_trip["spent_usd"] == total_spent == 86.111
    assert open_trip["size_base"] == total_size == 0.7608456
    assert open_trip["fees_usd"] == total_fees == 0.0861
    # Size-weighted entry: bounded drift only, since each fold rounds the running average to 8dp.
    exact_vwap = sum(b[1] * float(b[2]) for b in buys) / total_size
    assert abs(open_trip["entry_price_usd"] - exact_vwap) < 1e-6

    # ...and closing it books total received minus total spent, with no drift from the four folds.
    rows.append(
        _priced_order(
            "SOLUSDT", "Sell", 91.1111, -total_size, "119.75", "0.09", "2026-07-26T15:00Z"
        )
    )
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert unmatched == [] and [t["status"] for t in trips] == ["CLOSED"]
    assert trips[0]["spent_usd"] == 86.111 and trips[0]["received_usd"] == 91.1111
    assert trips[0]["pnl_usd"] == round(91.1111 - 86.111, 4) == 5.0001
    assert trips[0]["fees_usd"] == round(total_fees + 0.09, 4)
    assert trips[0]["size_base"] == total_size  # the whole position exits as one unit
    assert rpt.summarize(trips, unmatched)["realised_pnl_usd"] == 5.0001


def test_orphan_sell_does_not_corrupt_a_later_trip_on_the_same_key(tmp_path: Path) -> None:
    # An orphan sell followed by a fresh buy+close on the SAME (symbol, strategy) key: the orphan
    # must not leave residue in `open_entries` that the next buy scales into or the next sell prices
    # against. It pops nothing (there is nothing open) and is reported; the following buy->sell is a
    # clean, independent trip.
    rows = [
        _priced_order("SOLUSDT", "Sell", 30.0, -0.30, "100", "0.03", "2026-07-26T14:00:00+00:00"),
        _priced_order("SOLUSDT", "Buy", -25.0, 0.25, "100", "0.0025", "2026-07-26T14:10:00+00:00"),
        _priced_order("SOLUSDT", "Sell", 27.0, -0.25, "108", "0.027", "2026-07-26T14:20:00+00:00"),
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert [u["reason"] for u in unmatched] == ["orphan_sell"]
    assert unmatched[0]["at"] == "2026-07-26T14:00:00+00:00"
    assert "pnl_usd" not in unmatched[0]  # never priced
    # The later trip is independent: opened by the 14:10 buy, its 25 spend, its own fees.
    assert [t["status"] for t in trips] == ["CLOSED"]
    trip = trips[0]
    assert trip["opened_at"] == "2026-07-26T14:10:00+00:00"
    assert trip["spent_usd"] == 25.0 and trip["received_usd"] == 27.0
    assert trip["size_base"] == 0.25 and trip["entry_price_usd"] == 100.0
    assert trip["pnl_usd"] == 2.0 and trip["outcome"] == "WIN"
    assert trip["fees_usd"] == 0.277  # 0.0025*100 + 0.027 — the orphan's 0.03 is NOT in here
    summary = rpt.summarize(trips, unmatched)
    assert summary["closed_trades"] == 1 and summary["open_trades"] == 0
    assert summary["realised_pnl_usd"] == 2.0  # the orphan's 30.0 never inflates realised P&L
    assert summary["total_fees_usd"] == 0.277 and summary["unmatched_fees_usd"] == 0.03


def test_twelve_concurrent_coins_all_stay_open_and_none_aggregate(tmp_path: Path) -> None:
    # The live lane opened 12 concurrent positions on one shared ledger. Distinct symbols must stay
    # 12 separate positions (aggregation is per key, never across coins), oldest-first, none lost.
    symbols = [
        "AAVEUSDT",
        "APTUSDT",
        "AXSUSDT",
        "BCHUSDT",
        "BNBUSDT",
        "BTCUSDT",
        "ETHUSDT",
        "LINKUSDT",
        "RUNEUSDT",
        "SOLUSDT",
        "TIAUSDT",
        "UNIUSDT",
    ]
    rows = [
        _coin_order(symbol, "ACTIVITY-CONFLUENCE", "Buy", -25.0, 2.5, f"2026-07-26T14:{i:02d}:00Z")
        for i, symbol in enumerate(symbols)
    ]
    trips, unmatched = rpt.fold_fills(rpt.load_filled(_write(tmp_path, rows)))
    assert unmatched == []
    assert [t["symbol"] for t in trips] == symbols
    assert all(t["status"] == "OPEN" and t["spent_usd"] == 25.0 for t in trips)
    summary = rpt.summarize(trips, unmatched)
    assert summary["open_trades"] == 12 and summary["closed_trades"] == 0
    assert summary["total_fees_usd"] == round(12 * 0.001 * 10, 4)  # every entry fee counted
