"""Offline checks for the demo P&L tool (no network, no real key)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.demo_pnl as pnl  # noqa: E402


def test_compute_pnl_win_loss_flat() -> None:
    assert pnl.compute_pnl(50100.0, 1.0, 60000.0) == 100.0  # +100 USDT held as cash -> win
    assert pnl.compute_pnl(50000.0, 1.0, 60000.0) == 0.0  # unchanged -> flat
    # spent USDT on BTC that lost a hair of value to fees -> small loss
    assert pnl.compute_pnl(49972.78, 1.00041, 64310.6) < 0


def test_build_pnl_reads_wallet_and_price() -> None:
    def get(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps(
            {"retCode": 0, "result": {"list": [{"coin": [
                {"coin": "USDT", "walletBalance": "49900"},
                {"coin": "BTC", "walletBalance": "1.001"}]}]}}
        ).encode()  # fmt: skip

    def market(url: str, headers: dict[str, str]) -> bytes:
        return json.dumps({"result": {"list": [{"lastPrice": "60000"}]}}).encode()

    report = pnl.build_pnl(get, market, "k", "s")
    assert report["realized_pnl_usdt"] == pnl.compute_pnl(49900.0, 1.001, 60000.0)
    assert report["result"] in {"WIN", "LOSS", "FLAT"}
    assert report["btc_price"] == 60000.0
