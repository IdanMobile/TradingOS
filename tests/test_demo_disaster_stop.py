"""Offline tests for the demo lane -15% disaster-stop (local + venue-resting). No network, no keys.

Covers the pure decision logic the operator approved on 2026-07-21 (D-104 demo-lane scope):
trigger detection, stop-price computation, entry reconstruction from the ledger, and the
idempotent place/replace/cancel bookkeeping for the venue-resting stop.
"""

from __future__ import annotations

import json
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pytest

import scripts.demo_eth_lane as lane


class FakeStopVenue:
    """POST transport stand-in that records conditional-order creates and cancels."""

    def __init__(
        self,
        ret_code: int = 0,
        order_id: str = "STOP-1",
        cancel_ret_code: int | list[int] = 0,
        create_status: str = "Untriggered",
        cancel_status: str | list[str] = "Cancelled",
        tick_size: object = "0.01",
        qty_step: object = "0.00001",
    ) -> None:
        self.ret_code = ret_code
        self.order_id = order_id
        self.cancel_ret_code = cancel_ret_code
        self.create_status = create_status
        self.cancel_status = cancel_status
        self.tick_size = tick_size
        self.qty_step = qty_step
        self.statuses: dict[str, str] = {}
        self.creates: list[dict] = []
        self.cancels: list[dict] = []
        self.events: list[tuple[str, str]] = []
        self.realtime_omit: set[str] = set()
        self.realtime_overrides: dict[str, object] = {}
        self.realtime_prefix_rows: list[dict[str, object]] = []
        self.realtime_reads = 0

    def post(self, url: str, headers: dict[str, str], body: bytes) -> bytes:
        payload = json.loads(body)
        if url.endswith("/v5/order/create"):
            self.creates.append(payload)
            self.events.append(("create", self.order_id))
            if self.ret_code == 0 and self.order_id:
                self.statuses[self.order_id] = self.create_status
            return json.dumps(
                {"retCode": self.ret_code, "result": {"orderId": self.order_id}}
            ).encode()
        if url.endswith("/v5/order/cancel"):
            self.cancels.append(payload)
            self.events.append(("cancel", str(payload.get("orderId"))))
            cancel_ret_code = (
                self.cancel_ret_code.pop(0)
                if isinstance(self.cancel_ret_code, list)
                else self.cancel_ret_code
            )
            cancel_status = (
                self.cancel_status.pop(0)
                if isinstance(self.cancel_status, list)
                else self.cancel_status
            )
            if cancel_ret_code == 0:
                self.statuses[str(payload.get("orderId"))] = cancel_status
            return json.dumps(
                {
                    "retCode": cancel_ret_code,
                    "retMsg": "cancel rejected" if cancel_ret_code else "OK",
                    "result": {"orderId": payload.get("orderId")},
                }
            ).encode()
        raise AssertionError(f"unexpected POST {url}")

    def get(self, url: str, _headers: dict[str, str]) -> bytes:
        if "/v5/market/instruments-info" in url:
            return instrument_info(self.tick_size, self.qty_step)(url, _headers)
        if "/v5/order/realtime" in url:
            self.realtime_reads += 1
            order_id = parse_qs(urlsplit(url).query).get("orderId", [""])[0]
            status = self.statuses.get(order_id, "")
            placed = self.creates[-1] if self.creates else {}
            row = {
                "orderId": order_id,
                "orderStatus": status,
                "symbol": "ETHUSDT",
                "side": "Sell",
                "orderType": "Market",
                "orderFilter": "StopOrder",
                "triggerDirection": 2,
                "marketUnit": "baseCoin",
                "triggerPrice": placed.get("triggerPrice"),
                "qty": placed.get("qty"),
            }
            row.update(self.realtime_overrides)
            for field in self.realtime_omit:
                row.pop(field, None)
            rows = [*self.realtime_prefix_rows, row] if status else list(self.realtime_prefix_rows)
            return json.dumps({"retCode": 0, "result": {"list": rows}}).encode()
        raise AssertionError(f"unexpected GET {url}")


def instrument_info(tick_size: object = "0.01", qty_step: object = "0.00001"):
    def get(url: str, _headers: dict[str, str]) -> bytes:
        assert "/v5/market/instruments-info" in url
        return json.dumps(
            {
                "result": {
                    "list": [
                        {
                            "priceFilter": {"tickSize": tick_size},
                            "lotSizeFilter": {"basePrecision": qty_step},
                        }
                    ]
                }
            }
        ).encode()

    return get


# --- stop-price computation ------------------------------------------------------------------


def test_stop_price_is_fifteen_percent_below_entry() -> None:
    assert lane.disaster_stop_price(Decimal("100")) == Decimal("85.00")
    assert lane.disaster_stop_price(Decimal("1862.37")) == Decimal("1583.0145")


def test_stop_pct_constant_is_the_approved_threshold() -> None:
    assert lane.DEMO_DISASTER_STOP_PCT == Decimal("0.15")


def test_price_quantization_rounds_long_stop_up_and_preserves_exact_tick() -> None:
    assert lane.quantize_price_up(Decimal("1583.0145"), Decimal("0.01")) == Decimal("1583.02")
    assert lane.quantize_price_up(Decimal("1583.02"), Decimal("0.01")) == Decimal("1583.02")


def test_instrument_price_tick_parses_price_filter() -> None:
    assert lane.instrument_price_tick(instrument_info("0.01")) == Decimal("0.01")


def test_instrument_price_tick_rejects_missing_nonpositive_and_nonfinite_values() -> None:
    bad_payloads = (None, "0", "-0.01", "NaN")
    for bad_tick in bad_payloads:
        try:
            lane.instrument_price_tick(instrument_info(bad_tick))
        except ValueError:
            continue
        raise AssertionError(f"invalid tick accepted: {bad_tick!r}")


def test_stop_quantity_quantization_rounds_down_and_preserves_exact_step() -> None:
    step = Decimal("0.00001")
    assert lane.quantize_stop_qty_down(Decimal("0.01341033"), step) == Decimal("0.01341")
    assert lane.quantize_stop_qty_down(Decimal("0.01341"), step) == Decimal("0.01341")


def test_stop_quantity_quantization_fails_closed_below_step() -> None:
    try:
        lane.quantize_stop_qty_down(Decimal("0.000009"), Decimal("0.00001"))
    except ValueError:
        return
    raise AssertionError("sub-step stop quantity was accepted")


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
    quantized = {**matching, "trigger_price": "1583.02"}
    assert lane.stop_reconcile_action(qty, entry, quantized, Decimal("0.01")) == "noop"


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


def test_place_stop_order_quantizes_trigger_up_in_venue_payload() -> None:
    venue = FakeStopVenue()
    lane.place_stop_order(
        Decimal("0.01341033"),
        Decimal("1583.0145"),
        Decimal("0.01"),
        Decimal("0.00001"),
        "k",
        "s",
        post_transport=venue.post,
    )
    order = venue.creates[0]
    assert order["side"] == "Sell" and order["orderFilter"] == "StopOrder"
    assert order["triggerDirection"] == "2"  # fire when price falls through the trigger
    # 1583.0145 was rejected by Bybit for excess precision; a long stop rounds up so
    # venue protection is never looser than the exact local -15% risk boundary.
    assert order["triggerPrice"] == "1583.02" and order["qty"] == "0.01341"


def test_apply_place_records_new_resting_stop() -> None:
    venue = FakeStopVenue(order_id="STOP-1")
    entry, qty = Decimal("1862.37"), Decimal("0.0134")
    resting = lane.apply_stop_decision(
        "place",
        None,
        qty,
        entry,
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting == {
        "state": "ACTIVE",
        "order_id": "STOP-1",
        "trigger_price": "1583.02",
        "risk_boundary_price": str(lane.disaster_stop_price(entry)),
        "base_qty": "0.0134",
        "position_base_qty": "0.0134",
        "risk_fraction": "0.15",
        "price_tick": "0.01",
    }
    assert len(venue.creates) == 1 and venue.cancels == []


def test_apply_place_filled_after_create_latches_pending_reconciliation() -> None:
    venue = FakeStopVenue(order_id="STOP-FILLED", create_status="Filled")
    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting is not None
    assert resting["state"] == "FILLED_PENDING_RECONCILIATION"
    assert resting["order_id"] == "STOP-FILLED"
    assert resting["filled_order_id"] == "STOP-FILLED"
    assert resting["filled_order_status"] == "Filled"


def test_apply_place_persists_submitted_qty_and_exact_inventory() -> None:
    venue = FakeStopVenue(order_id="STOP-QTY")
    lane_base = Decimal("0.01341033")
    resting = lane.apply_stop_decision(
        "place",
        None,
        lane_base,
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert venue.creates[0]["qty"] == "0.01341"
    assert resting is not None
    assert resting["base_qty"] == "0.01341"
    assert resting["position_base_qty"] == "0.01341033"
    assert resting["risk_fraction"] == "0.15"
    assert resting["price_tick"] == "0.01"


def test_apply_place_persists_the_actual_non_default_price_tick() -> None:
    venue = FakeStopVenue(order_id="STOP-TICK")

    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        price_tick=Decimal("0.1"),
        qty_step=Decimal("0.00001"),
        post_transport=venue.post,
    )

    assert resting is not None
    assert resting["trigger_price"] == "1583.1"
    assert resting["price_tick"] == "0.1"
    assert resting["risk_fraction"] == str(lane.DEMO_DISASTER_STOP_PCT)
    assert resting["order_id"] == "STOP-TICK"


def test_reconcile_is_idempotent_against_quantized_submitted_qty() -> None:
    lane_base = Decimal("0.01341033")
    resting = {
        "state": "ACTIVE",
        "order_id": "STOP-QTY",
        "trigger_price": "1583.02",
        "risk_boundary_price": "1583.0145",
        "base_qty": "0.01341",
        "position_base_qty": str(lane_base),
    }
    assert (
        lane.stop_reconcile_action(
            lane_base,
            Decimal("1862.37"),
            resting,
            Decimal("0.01"),
            Decimal("0.00001"),
        )
        == "noop"
    )


def test_apply_place_fails_closed_when_stop_qty_is_below_step() -> None:
    venue = FakeStopVenue()
    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.000009"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting is None
    assert venue.creates == [] and venue.cancels == []


def test_ambiguous_set_with_any_filled_stop_latches_entire_set() -> None:
    venue = FakeStopVenue()
    venue.statuses.update({"OLD": "Untriggered", "NEW": "Filled"})
    venue.realtime_overrides.update({"triggerPrice": "1583.02", "qty": "0.0134"})
    ambiguous = {
        "state": "AMBIGUOUS",
        "order_ids": ["OLD", "NEW"],
        "order_records": {
            "OLD": {"order_id": "OLD", "trigger_price": "1583.02", "base_qty": "0.0134"},
            "NEW": {"order_id": "NEW", "trigger_price": "1583.02", "base_qty": "0.0134"},
        },
        "ambiguity_reason": "test fixture",
    }
    resting = lane.apply_stop_decision(
        "reconcile",
        ambiguous,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting is not None
    assert resting["state"] == "FILLED_PENDING_RECONCILIATION"
    assert resting["order_ids"] == ["OLD", "NEW"]
    assert resting["filled_order_id"] == "NEW"
    assert resting["filled_order_status"] == "Filled"
    assert venue.events == []


def test_apply_replace_places_new_then_cancels_old() -> None:
    venue = FakeStopVenue(order_id="STOP-2")
    entry, qty = Decimal("1862.37"), Decimal("0.0134")
    old = {"order_id": "OLD", "trigger_price": "1500", "base_qty": "0.01"}
    resting = lane.apply_stop_decision(
        "replace",
        old,
        qty,
        entry,
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert venue.cancels[0]["orderId"] == "OLD"
    assert venue.events == [("create", "STOP-2"), ("cancel", "OLD")]
    assert (
        resting is not None and resting["order_id"] == "STOP-2" and resting["base_qty"] == "0.0134"
    )


def test_apply_cancel_clears_resting_stop() -> None:
    venue = FakeStopVenue()
    old = {"order_id": "OLD", "trigger_price": "1583", "base_qty": "0.0134"}
    resting = lane.apply_stop_decision(
        "cancel",
        old,
        Decimal("0"),
        None,
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
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


def test_legacy_metadata_backfill_refuses_retained_only_and_ambiguous_evidence() -> None:
    legacy = {
        "state": "ACTIVE",
        "order_id": "OLD",
        "trigger_price": "1583.02",
        "base_qty": "0.0134",
    }
    confirmed = {
        "orderId": "OLD",
        "orderStatus": "Untriggered",
        "triggerPrice": "1583.02",
        "qty": "0.0134",
        "symbol": "ETHUSDT",
        "side": "Sell",
        "orderType": "Market",
        "orderFilter": "StopOrder",
        "triggerDirection": 2,
    }
    args = (
        Decimal("0.0134"),
        Decimal("1862.37"),
        Decimal("0.01"),
        Decimal("0.00001"),
    )

    assert lane._backfill_confirmed_stop_metadata(legacy, None, *args) is legacy
    ambiguous = {**legacy, "state": "AMBIGUOUS"}
    assert lane._backfill_confirmed_stop_metadata(ambiguous, confirmed, *args) is ambiguous
    assert "risk_fraction" not in legacy and "risk_fraction" not in ambiguous


def _valid_legacy_confirmation() -> dict:
    return {
        "orderId": "OLD",
        "orderStatus": "Untriggered",
        "triggerPrice": "1583.02",
        "qty": "0.0134",
        "symbol": "ETHUSDT",
        "side": "Sell",
        "orderType": "Market",
        "orderFilter": "StopOrder",
        "triggerDirection": 2,
    }


def _legacy_record() -> dict:
    return {
        "state": "ACTIVE",
        "order_id": "OLD",
        "trigger_price": "1583.02",
        "base_qty": "0.0134",
    }


def _try_legacy_backfill(confirmation: dict) -> dict:
    resting = _legacy_record()
    migrated = lane._backfill_confirmed_stop_metadata(
        resting,
        confirmation,
        Decimal("0.0134"),
        Decimal("1862.37"),
        Decimal("0.01"),
        Decimal("0.00001"),
    )
    assert migrated is not None
    return migrated


def test_legacy_metadata_backfill_accepts_exact_protective_semantics() -> None:
    migrated = _try_legacy_backfill(_valid_legacy_confirmation())

    assert migrated["risk_fraction"] == "0.15"
    assert migrated["price_tick"] == "0.01"
    assert migrated["order_id"] == "OLD"


def test_legacy_metadata_backfill_accepts_absent_optional_market_unit() -> None:
    confirmation = _valid_legacy_confirmation()
    confirmation.pop("marketUnit", None)

    assert _try_legacy_backfill(confirmation)["risk_fraction"] == "0.15"


def test_legacy_metadata_backfill_rejects_wrong_optional_market_unit() -> None:
    confirmation = {**_valid_legacy_confirmation(), "marketUnit": "quoteCoin"}

    assert _try_legacy_backfill(confirmation) == _legacy_record()


@pytest.mark.parametrize(
    "field",
    ["symbol", "side", "orderType", "orderFilter", "triggerDirection"],
)
def test_legacy_metadata_backfill_rejects_missing_protective_semantics(field: str) -> None:
    confirmation = _valid_legacy_confirmation()
    confirmation.pop(field)

    assert _try_legacy_backfill(confirmation) == _legacy_record()


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("symbol", "BTCUSDT"),
        ("side", "Buy"),
        ("orderType", "Limit"),
        ("orderFilter", "Order"),
        ("triggerDirection", 1),
        ("triggerDirection", True),
        ("triggerDirection", "2"),
    ],
)
def test_legacy_metadata_backfill_rejects_wrong_protective_semantics(
    field: str, wrong: object
) -> None:
    confirmation = {**_valid_legacy_confirmation(), field: wrong}

    assert _try_legacy_backfill(confirmation) == _legacy_record()


_REQUIRED_ACTIVE_ROW_FIELDS = (
    "orderId",
    "symbol",
    "side",
    "orderType",
    "orderFilter",
    "triggerDirection",
    "triggerPrice",
    "qty",
)
_WRONG_ACTIVE_ROW_VALUES = (
    ("orderId", "OTHER"),
    ("symbol", "BTCUSDT"),
    ("side", "Buy"),
    ("orderType", "Limit"),
    ("orderFilter", "Order"),
    ("triggerDirection", True),
    ("triggerPrice", "0"),
    ("qty", "0"),
    ("marketUnit", "quoteCoin"),
)


def _enriched_tracked_stop() -> dict:
    return {
        **_legacy_record(),
        "risk_boundary_price": "1583.0145",
        "position_base_qty": "0.0134",
        "risk_fraction": "0.15",
        "price_tick": "0.01",
    }


def _tracked_venue() -> FakeStopVenue:
    venue = FakeStopVenue()
    venue.statuses["OLD"] = "Untriggered"
    venue.realtime_overrides.update({"triggerPrice": "1583.02", "qty": "0.0134"})
    return venue


def test_enriched_tracked_stop_valid_row_is_confirmed_safe() -> None:
    venue = _tracked_venue()

    resting, safe, confirmation = lane.preflight_tracked_stop(
        _enriched_tracked_stop(), "k", "s", venue.get
    )

    assert resting == _enriched_tracked_stop()
    assert safe is True
    assert confirmation is not None and confirmation["orderId"] == "OLD"


def test_none_is_the_only_fresh_no_stop_state_and_remains_safe() -> None:
    venue = _tracked_venue()

    resting, safe, confirmation = lane.preflight_tracked_stop(None, "k", "s", venue.get)

    assert resting is None and safe is True and confirmation is None
    assert venue.realtime_reads == 0


@pytest.mark.parametrize(
    "unsupported",
    [
        {},
        {"state": "UNKNOWN", "order_id": "OLD", "trigger_price": "1", "base_qty": "1"},
        {"state": "ACTIVE", "trigger_price": "1", "base_qty": "1"},
        {"state": None, "order_id": "", "trigger_price": "1", "base_qty": "1"},
    ],
)
def test_preflight_rejects_empty_unknown_or_incomplete_states(unsupported: dict) -> None:
    venue = _tracked_venue()

    resting, safe, confirmation = lane.preflight_tracked_stop(unsupported, "k", "s", venue.get)

    assert resting == unsupported
    assert safe is False and confirmation is None
    assert venue.realtime_reads == 0


@pytest.mark.parametrize(
    "order_ids",
    [[], (), ["OLD", "OLD"], [""], [" OLD"], [1], "OLD"],
)
def test_preflight_rejects_malformed_ambiguous_ids(order_ids: object) -> None:
    venue = _tracked_venue()
    resting = {
        "state": "AMBIGUOUS",
        "order_ids": order_ids,
        "order_records": {"OLD": {"trigger_price": "1583.02", "base_qty": "0.0134"}},
    }

    retained, safe, confirmation = lane.preflight_tracked_stop(resting, "k", "s", venue.get)

    assert retained == resting
    assert safe is False and confirmation is None
    assert venue.realtime_reads == 0


def test_mismatched_cancelled_first_row_cannot_clear_exact_active_tracked_stop() -> None:
    venue = _tracked_venue()
    venue.realtime_prefix_rows = [{"orderId": "OTHER", "orderStatus": "Cancelled"}]

    resting, safe, confirmation = lane.preflight_tracked_stop(
        _enriched_tracked_stop(), "k", "s", venue.get
    )

    assert resting == _enriched_tracked_stop()
    assert safe is True
    assert confirmation is not None and confirmation["orderId"] == "OLD"
    assert venue.creates == [] and venue.cancels == []


def test_only_mismatched_cancelled_row_is_unknown_not_cleared() -> None:
    venue = _tracked_venue()
    venue.realtime_prefix_rows = [{"orderId": "OTHER", "orderStatus": "Cancelled"}]
    venue.realtime_omit.add("orderId")

    resting, safe, confirmation = lane.preflight_tracked_stop(
        _enriched_tracked_stop(), "k", "s", venue.get
    )

    assert resting == _enriched_tracked_stop()
    assert safe is False and confirmation is None


def test_ambiguous_wrong_bound_trigger_stays_ambiguous_and_unsafe() -> None:
    venue = _tracked_venue()
    resting = {
        "state": "AMBIGUOUS",
        "order_ids": ["OLD"],
        "order_records": {
            "OLD": {"order_id": "OLD", "trigger_price": "1500", "base_qty": "0.0134"}
        },
        "ambiguity_reason": "fixture",
    }

    retained, safe, confirmation = lane.preflight_tracked_stop(resting, "k", "s", venue.get)

    assert retained == resting
    assert safe is False and confirmation is None
    reconciled = lane.apply_stop_decision(
        "reconcile",
        resting,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
    )
    assert reconciled is not None and reconciled["state"] == "AMBIGUOUS"
    assert venue.creates == [] and venue.cancels == []


def test_exact_single_ambiguous_record_resolves_active_safely() -> None:
    venue = _tracked_venue()
    resting = {
        "state": "AMBIGUOUS",
        "order_ids": ["OLD"],
        "order_records": {
            "OLD": {"order_id": "OLD", "trigger_price": "1583.02", "base_qty": "0.0134"}
        },
        "ambiguity_reason": "fixture",
    }

    resolved, safe, confirmation = lane.preflight_tracked_stop(resting, "k", "s", venue.get)

    assert resolved is not None and resolved["state"] == "ACTIVE"
    assert resolved["order_id"] == "OLD"
    assert safe is True and confirmation is None


@pytest.mark.parametrize("missing", ["trigger_price", "base_qty"])
def test_preflight_rejects_missing_retained_bounds_before_venue_query(missing: str) -> None:
    venue = _tracked_venue()
    resting = _enriched_tracked_stop()
    resting.pop(missing)

    retained, safe, confirmation = lane.preflight_tracked_stop(resting, "k", "s", venue.get)

    assert retained == resting
    assert safe is False and confirmation is None
    assert venue.realtime_reads == 0


@pytest.mark.parametrize("field", ["trigger_price", "base_qty"])
@pytest.mark.parametrize("bad", [True, "NaN", "Infinity", "-Infinity"])
def test_preflight_rejects_malformed_retained_bounds_before_venue_query(
    field: str, bad: object
) -> None:
    venue = _tracked_venue()
    resting = {**_enriched_tracked_stop(), field: bad}

    retained, safe, confirmation = lane.preflight_tracked_stop(resting, "k", "s", venue.get)

    assert retained == resting
    assert safe is False and confirmation is None
    assert venue.realtime_reads == 0


@pytest.mark.parametrize("current", [[], "ACTIVE", 42, True])
def test_preflight_rejects_non_dict_current_record_without_exception(current: object) -> None:
    venue = _tracked_venue()

    retained, safe, confirmation = lane.preflight_tracked_stop(  # type: ignore[arg-type]
        current, "k", "s", venue.get
    )

    assert retained is None
    assert safe is False and confirmation is None
    assert venue.realtime_reads == 0


@pytest.mark.parametrize("records", [None, [], "bad", {"OLD": []}, {"OLD": "bad"}])
def test_preflight_rejects_malformed_ambiguous_order_records(records: object) -> None:
    venue = _tracked_venue()
    resting = {
        "state": "AMBIGUOUS",
        "order_ids": ["OLD"],
        "order_records": records,
    }

    retained, safe, confirmation = lane.preflight_tracked_stop(resting, "k", "s", venue.get)

    assert retained == resting
    assert safe is False and confirmation is None
    assert venue.realtime_reads == 0


@pytest.mark.parametrize("missing", _REQUIRED_ACTIVE_ROW_FIELDS)
def test_enriched_tracked_stop_missing_identity_is_unknown_and_unsafe(missing: str) -> None:
    venue = _tracked_venue()
    venue.realtime_omit.add(missing)

    resting, safe, confirmation = lane.preflight_tracked_stop(
        _enriched_tracked_stop(), "k", "s", venue.get
    )

    assert resting == _enriched_tracked_stop()
    assert safe is False
    assert confirmation is None


@pytest.mark.parametrize(("field", "wrong"), _WRONG_ACTIVE_ROW_VALUES)
def test_enriched_tracked_stop_wrong_identity_is_unknown_and_unsafe(
    field: str, wrong: object
) -> None:
    venue = _tracked_venue()
    venue.realtime_overrides[field] = wrong

    resting, safe, confirmation = lane.preflight_tracked_stop(
        _enriched_tracked_stop(), "k", "s", venue.get
    )

    assert resting == _enriched_tracked_stop()
    assert safe is False
    assert confirmation is None


def _place_with_corrupt_active_row(*, missing: str | None = None, field: str = "", wrong=None):
    venue = FakeStopVenue(order_id="NEW")
    if missing is not None:
        venue.realtime_omit.add(missing)
    if field:
        venue.realtime_overrides[field] = wrong
    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    return venue, resting


@pytest.mark.parametrize("missing", _REQUIRED_ACTIVE_ROW_FIELDS)
def test_newly_created_stop_missing_identity_never_publishes_active(missing: str) -> None:
    venue, resting = _place_with_corrupt_active_row(missing=missing)

    assert resting is not None and resting["state"] == "AMBIGUOUS"
    assert len(venue.creates) == 1 and venue.cancels == []


@pytest.mark.parametrize(("field", "wrong"), _WRONG_ACTIVE_ROW_VALUES)
def test_newly_created_stop_wrong_identity_never_publishes_active(
    field: str, wrong: object
) -> None:
    venue, resting = _place_with_corrupt_active_row(field=field, wrong=wrong)

    assert resting is not None and resting["state"] == "AMBIGUOUS"
    assert len(venue.creates) == 1 and venue.cancels == []


def test_apply_place_rejected_by_venue_returns_none() -> None:
    venue = FakeStopVenue(ret_code=10001)  # non-zero retCode = rejected
    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting is None  # nothing recorded; next cycle retries. Local stop remains primary.


def test_apply_place_fails_closed_when_price_tick_is_invalid() -> None:
    venue = FakeStopVenue(tick_size="0")
    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting is None
    assert venue.creates == [] and venue.cancels == []


def test_apply_place_fails_closed_when_metadata_lookup_is_unavailable() -> None:
    venue = FakeStopVenue()

    def unavailable(_url: str, _headers: dict[str, str]) -> bytes:
        raise OSError("metadata unavailable")

    resting = lane.apply_stop_decision(
        "place",
        None,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=unavailable,
        post_transport=venue.post,
    )
    assert resting is None
    assert venue.creates == [] and venue.cancels == []


def test_apply_replace_preserves_existing_stop_when_price_tick_is_invalid() -> None:
    venue = FakeStopVenue(tick_size=None)
    existing = {"order_id": "OLD", "trigger_price": "1500", "base_qty": "0.0134"}
    resting = lane.apply_stop_decision(
        "replace",
        existing,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting == existing
    assert venue.creates == [] and venue.cancels == []


def test_apply_replace_rejection_preserves_existing_stop() -> None:
    venue = FakeStopVenue(ret_code=10001, order_id="STOP-2")
    existing = {"order_id": "OLD", "trigger_price": "1500", "base_qty": "0.0134"}
    resting = lane.apply_stop_decision(
        "replace",
        existing,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting == existing
    assert venue.events == [("create", "STOP-2")]


def test_apply_replace_cancel_failure_rolls_back_new_and_marks_old_ambiguous() -> None:
    venue = FakeStopVenue(order_id="STOP-2", cancel_ret_code=[10001, 0])
    existing = {"order_id": "OLD", "trigger_price": "1500", "base_qty": "0.0134"}
    resting = lane.apply_stop_decision(
        "replace",
        existing,
        Decimal("0.0134"),
        Decimal("1862.37"),
        "k",
        "s",
        get_transport=venue.get,
        post_transport=venue.post,
    )
    assert resting is not None
    assert resting["state"] == "AMBIGUOUS"
    assert resting["order_ids"] == ["OLD"]
    assert resting["order_records"]["OLD"] == existing
    assert venue.events == [
        ("create", "STOP-2"),
        ("cancel", "OLD"),
        ("cancel", "STOP-2"),
    ]
