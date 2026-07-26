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
