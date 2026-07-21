"""Offline tests for the demo lane -15% disaster-stop (local + venue-resting). No network, no keys.

Covers the pure decision logic the operator approved on 2026-07-21 (D-104 demo-lane scope):
trigger detection, stop-price computation, entry reconstruction from the ledger, and the
idempotent place/replace/cancel bookkeeping for the venue-resting stop.
"""

from __future__ import annotations

import json
from decimal import Decimal

import scripts.demo_eth_lane as lane


class FakeStopVenue:
    """POST transport stand-in that records conditional-order creates and cancels."""

    def __init__(self, ret_code: int = 0, order_id: str = "STOP-1") -> None:
        self.ret_code = ret_code
        self.order_id = order_id
        self.creates: list[dict] = []
        self.cancels: list[dict] = []

    def post(self, url: str, headers: dict[str, str], body: bytes) -> bytes:
        payload = json.loads(body)
        if url.endswith("/v5/order/create"):
            self.creates.append(payload)
            return json.dumps(
                {"retCode": self.ret_code, "result": {"orderId": self.order_id}}
            ).encode()
        if url.endswith("/v5/order/cancel"):
            self.cancels.append(payload)
            return json.dumps(
                {"retCode": 0, "result": {"orderId": payload.get("orderId")}}
            ).encode()
        raise AssertionError(f"unexpected POST {url}")


# --- stop-price computation ------------------------------------------------------------------


def test_stop_price_is_fifteen_percent_below_entry() -> None:
    assert lane.disaster_stop_price(Decimal("100")) == Decimal("85.00")
    assert lane.disaster_stop_price(Decimal("1862.37")) == Decimal("1583.0145")


def test_stop_pct_constant_is_the_approved_threshold() -> None:
    assert lane.DEMO_DISASTER_STOP_PCT == Decimal("0.15")


# --- trigger detection -----------------------------------------------------------------------


def test_trigger_fires_at_or_below_stop_level() -> None:
    entry = Decimal("1862.37")
    stop = lane.disaster_stop_price(entry)  # 1583.0145
    assert lane.disaster_stop_triggered(entry, stop) is True  # exactly at the level
    assert lane.disaster_stop_triggered(entry, stop - Decimal("1")) is True  # below
    assert lane.disaster_stop_triggered(entry, stop + Decimal("1")) is False  # above
    assert lane.disaster_stop_triggered(entry, entry) is False  # flat


def test_trigger_guards_bad_inputs() -> None:
    assert lane.disaster_stop_triggered(Decimal("0"), Decimal("50")) is False
    assert lane.disaster_stop_triggered(Decimal("100"), Decimal("0")) is False


# --- entry reconstruction from the append-only ledger ----------------------------------------


def test_entry_price_from_ledger_takes_latest_filled_long_entry() -> None:
    records = [
        {"reason": "ENTRY_LONG", "ok": True, "avg_price": "1800"},
        {"reason": "EXIT_LONG", "ok": True, "avg_price": "1900"},
        {"reason": "ENTRY_LONG", "ok": True, "avg_price": "1862.37"},
    ]
    assert lane.entry_price_from_ledger(records) == Decimal("1862.37")


def test_entry_price_from_ledger_ignores_unfilled_and_non_entries() -> None:
    records = [
        {"reason": "ENTRY_LONG", "ok": True, "avg_price": "1800"},
        {"reason": "ENTRY_LONG", "ok": False},  # rejected placement, no fill
        {"reason": "DISASTER_STOP", "ok": True, "avg_price": "1500"},  # a sell, not an entry
    ]
    assert lane.entry_price_from_ledger(records) == Decimal("1800")


def test_entry_price_from_ledger_none_when_no_entry() -> None:
    assert lane.entry_price_from_ledger([]) is None
    assert lane.entry_price_from_ledger([{"reason": "EXIT_LONG", "ok": True}]) is None


def test_resolve_entry_prefers_state_then_falls_back_to_ledger() -> None:
    ledger = [{"reason": "ENTRY_LONG", "ok": True, "avg_price": "1862.37"}]
    assert lane.resolve_entry_price({"entry_price": "1750"}, ledger) == Decimal("1750")
    # A position that predates entry tracking has no state entry — reconstruct from the ledger.
    for empty in (None, "", "0"):
        assert lane.resolve_entry_price({"entry_price": empty}, ledger) == Decimal("1862.37")


# --- idempotent venue-stop bookkeeping decision ----------------------------------------------


def _resting(entry: Decimal, qty: Decimal) -> dict:
    return {
        "order_id": "OLD",
        "trigger_price": str(lane.disaster_stop_price(entry)),
        "base_qty": str(qty),
    }


def test_reconcile_flat_cancels_only_when_a_stop_rests() -> None:
    assert lane.stop_reconcile_action(Decimal("0"), None, None) == "noop"
    assert (
        lane.stop_reconcile_action(Decimal("0"), None, _resting(Decimal("1862"), Decimal("0.01")))
        == "cancel"
    )


def test_reconcile_open_places_then_is_idempotent() -> None:
    entry, qty = Decimal("1862.37"), Decimal("0.0134")
    assert lane.stop_reconcile_action(qty, entry, None) == "place"
    matching = _resting(entry, qty)
    assert (
        lane.stop_reconcile_action(qty, entry, matching) == "noop"
    )  # already correct -> no re-place


def test_reconcile_replaces_on_stale_level_or_qty() -> None:
    entry, qty = Decimal("1862.37"), Decimal("0.0134")
    assert (
        lane.stop_reconcile_action(qty, entry, _resting(Decimal("1500"), qty)) == "replace"
    )  # stale level
    assert (
        lane.stop_reconcile_action(qty, entry, _resting(entry, Decimal("0.02"))) == "replace"
    )  # stale qty


def test_reconcile_noop_when_entry_unknown() -> None:
    # No entry basis -> can't price a stop; local stop still guards, so leave the venue alone.
    assert lane.stop_reconcile_action(Decimal("0.0134"), None, None) == "noop"


# --- venue-stop adapter + decision execution -------------------------------------------------


def test_place_stop_order_builds_a_sell_stop_below_market() -> None:
    venue = FakeStopVenue()
    lane.place_stop_order(
        Decimal("0.0134"), Decimal("1583.0145"), "k", "s", post_transport=venue.post
    )
    order = venue.creates[0]
    assert order["side"] == "Sell" and order["orderFilter"] == "StopOrder"
    assert order["triggerDirection"] == "2"  # fire when price falls through the trigger
    assert order["triggerPrice"] == "1583.0145" and order["qty"] == "0.0134"


def test_apply_place_records_new_resting_stop() -> None:
    venue = FakeStopVenue(order_id="STOP-1")
    entry, qty = Decimal("1862.37"), Decimal("0.0134")
    resting = lane.apply_stop_decision(
        "place", None, qty, entry, "k", "s", post_transport=venue.post
    )
    assert resting == {
        "order_id": "STOP-1",
        "trigger_price": str(lane.disaster_stop_price(entry)),
        "base_qty": "0.0134",
    }
    assert len(venue.creates) == 1 and venue.cancels == []


def test_apply_replace_cancels_old_then_places_new() -> None:
    venue = FakeStopVenue(order_id="STOP-2")
    entry, qty = Decimal("1862.37"), Decimal("0.0134")
    old = {"order_id": "OLD", "trigger_price": "1500", "base_qty": "0.01"}
    resting = lane.apply_stop_decision(
        "replace", old, qty, entry, "k", "s", post_transport=venue.post
    )
    assert venue.cancels[0]["orderId"] == "OLD"
    assert (
        resting is not None and resting["order_id"] == "STOP-2" and resting["base_qty"] == "0.0134"
    )


def test_apply_cancel_clears_resting_stop() -> None:
    venue = FakeStopVenue()
    old = {"order_id": "OLD", "trigger_price": "1583", "base_qty": "0.0134"}
    resting = lane.apply_stop_decision(
        "cancel", old, Decimal("0"), None, "k", "s", post_transport=venue.post
    )
    assert resting is None
    assert venue.cancels[0]["orderId"] == "OLD" and venue.creates == []


def test_apply_noop_leaves_state_and_venue_untouched() -> None:
    venue = FakeStopVenue()
    existing = {"order_id": "X", "trigger_price": "1583", "base_qty": "0.0134"}
    resting = lane.apply_stop_decision(
        "noop", existing, Decimal("0.0134"), Decimal("1862"), "k", "s", post_transport=venue.post
    )
    assert resting == existing
    assert venue.creates == [] and venue.cancels == []


def test_apply_place_rejected_by_venue_returns_none() -> None:
    venue = FakeStopVenue(ret_code=10001)  # non-zero retCode = rejected
    resting = lane.apply_stop_decision(
        "place", None, Decimal("0.0134"), Decimal("1862.37"), "k", "s", post_transport=venue.post
    )
    assert resting is None  # nothing recorded; next cycle retries. Local stop remains primary.
