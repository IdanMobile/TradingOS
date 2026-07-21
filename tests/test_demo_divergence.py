"""T-015-03 measurement-mode divergence report: lane fills vs next-open expectation."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import run_demo_divergence_report as div  # noqa: E402

FILL = {
    "ok": True,
    "side": "Buy",
    "recorded_at": "2026-07-20T14:15:58+00:00",
    "avg_price": "1862.37",
    "cum_exec_qty": "0.0134",
    "fee": "0.0000134",
    "signal_ref": "SIG-1",
}


def _fetch(expected_open: str = "1862.64"):
    def fetch(url: str):
        # Echo the requested start so bar alignment is verified, not assumed.
        start = url.split("start=")[1].split("&")[0]
        return {"result": {"list": [[start, expected_open, "0", "0", "0", "0", "0"]]}}

    return fetch


def test_divergence_is_signed_adverse_positive() -> None:
    """Positive must always mean 'worse than the backtest expected', either side."""
    rows = div.fill_rows([FILL], _fetch())
    row = rows[0]
    # Bought below the expected open: favorable, so negative.
    assert row["divergence_bps_adverse_positive"] == pytest.approx(-1.45, abs=0.01)
    assert row["lag_seconds_after_bar_close"] == 958
    assert row["fee_bps"] == pytest.approx(10.0, abs=0.01)

    sell = {**FILL, "side": "Sell", "avg_price": "1861.00"}
    sold_low = div.fill_rows([sell], _fetch())[0]
    # Sold below expectation: adverse, so positive.
    assert sold_low["divergence_bps_adverse_positive"] > 0


def test_failed_orders_and_missing_bars_are_excluded_not_zeroed() -> None:
    refused = {**FILL, "ok": False}
    assert div.fill_rows([refused], _fetch()) == []

    def no_bar(url: str):
        return {"result": {"list": []}}

    row = div.fill_rows([FILL], no_bar)[0]
    assert row["divergence_bps_adverse_positive"] is None, "no bar means unmeasured, not zero"


def test_report_carries_scope_notes_and_no_authority() -> None:
    report = div.build_report([FILL], _fetch())
    assert report["fills_measured"] == 1
    assert report["execution_authority"] == "NONE"
    assert report["promotion_eligible"] is False
    assert any("Binance" in note for note in report["scope_notes"])
