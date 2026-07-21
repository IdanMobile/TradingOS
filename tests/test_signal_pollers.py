"""Checks for the free-tier outbound signal pollers (thresholds, cooldowns, risk math).

No real network calls: `_get_json` is monkeypatched to canned responses per test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tios.services.dashboard_api import signal_pollers as sp
from tios.services.dashboard_api.signals_inbox import append_polled_signal


def test_momentum_strength_scales_from_zero_at_threshold_to_capped_100() -> None:
    assert sp._momentum_strength(5.0, 5.0) == 0.0  # exactly at threshold: no strength yet
    assert sp._momentum_strength(-5.0, 5.0) == 0.0  # sign-agnostic
    assert 0 < sp._momentum_strength(12.0, 5.0) < 100
    assert sp._momentum_strength(999.0, 5.0) == 100.0  # capped, never exceeds 100


def test_fear_greed_strength_zero_at_threshold_max_at_extreme() -> None:
    assert sp._fear_greed_strength(25, "BUY") == 0.0
    assert sp._fear_greed_strength(0, "BUY") == 100.0
    assert sp._fear_greed_strength(75, "SELL") == 0.0
    assert sp._fear_greed_strength(100, "SELL") == 100.0
    assert sp._fear_greed_strength(50, "HOLD") is None


def test_risk_levels_buy_sell_hold() -> None:
    stop_loss, take_profit = sp._risk_levels(64600, "BUY")
    assert stop_loss == pytest.approx(64600 * 0.95)
    assert take_profit == pytest.approx([64600 * 1.05, 64600 * 1.10])

    stop_loss, take_profit = sp._risk_levels(64600, "SELL")
    assert stop_loss == pytest.approx(64600 * 1.05)
    assert take_profit == pytest.approx([64600 * 0.95, 64600 * 0.90])

    assert sp._risk_levels(64600, "HOLD") == (None, None)
    assert sp._risk_levels(None, "BUY") == (None, None)


def test_fear_greed_uses_the_index_own_timestamp_not_poll_time(tmp_path: Path, monkeypatch) -> None:
    # A real capture: alternative.me's own reading is from midnight, long before poll time.
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: {
            "data": [{"value": "10", "value_classification": "Fear", "timestamp": "1784419200"}]
        },
    )
    records, _ = sp.poll_fear_greed(tmp_path)
    assert records[0]["observed_at"] == "2026-07-19T00:00:00+00:00"


def test_fear_greed_omits_observed_at_when_source_timestamp_is_unparseable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: {"data": [{"value": "10", "value_classification": "Fear"}]},
    )
    records, _ = sp.poll_fear_greed(tmp_path)
    assert records[0]["observed_at"] is None


def test_coingecko_passes_through_coingeckos_own_last_updated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: [
            {
                "id": "bitcoin",
                "price_change_percentage_24h": 10,
                "current_price": 100,
                "last_updated": "2026-07-19T16:33:01.215Z",
            }
        ],
    )
    records, _ = sp.poll_coingecko_momentum(tmp_path)
    assert records[0]["observed_at"] == "2026-07-19T16:33:01.215Z"


def test_binance_converts_close_time_ms_to_iso(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: [
            {
                "symbol": "BTCUSDT",
                "priceChangePercent": "10",
                "lastPrice": "100",
                "closeTime": 1784478548004,
            }
        ],
    )
    records, _ = sp.poll_binance_momentum(tmp_path)
    assert records[0]["observed_at"] == "2026-07-19T16:29:08.004000+00:00"


@pytest.mark.parametrize(
    ("value", "expected_action"),
    [(10, "BUY"), (25, "BUY"), (26, "HOLD"), (74, "HOLD"), (75, "SELL"), (90, "SELL")],
)
def test_fear_greed_thresholds(
    tmp_path: Path, monkeypatch, value: int, expected_action: str
) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: {"data": [{"value": str(value), "value_classification": "x"}]},
    )
    records, error = sp.poll_fear_greed(tmp_path)
    assert error is None
    assert len(records) == 1
    assert records[0]["action"] == expected_action
    assert records[0]["symbol"] == "BTC"
    # No price basis for a market-wide index — the field is omitted, not fabricated.
    assert "entry_price" not in records[0]


def test_fear_greed_respects_cooldown(tmp_path: Path, monkeypatch) -> None:
    append_polled_signal(
        tmp_path, source=sp._FEAR_GREED_SOURCE, symbol="BTC", action="HOLD", rationale="r"
    )
    called = []
    monkeypatch.setattr(sp, "_get_json", lambda url, **kw: called.append(url) or {"data": []})
    records, error = sp.poll_fear_greed(tmp_path)
    assert records == []
    assert error is None
    assert called == []  # cooldown skipped the network call entirely


def test_fear_greed_reports_error_without_crashing(tmp_path: Path, monkeypatch) -> None:
    def boom(url, **kw):
        raise ValueError("bad json")

    monkeypatch.setattr(sp, "_get_json", boom)
    records, error = sp.poll_fear_greed(tmp_path)
    assert records == []
    assert error is not None and "Fear & Greed" in error


@pytest.mark.parametrize(
    ("change_pct", "expected_action"),
    [(-10.0, "SELL"), (-5.0, "SELL"), (-4.9, "HOLD"), (4.9, "HOLD"), (5.0, "BUY"), (12.0, "BUY")],
)
def test_coingecko_momentum_thresholds(
    tmp_path: Path, monkeypatch, change_pct: float, expected_action: str
) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: [
            {
                "id": "bitcoin",
                "price_change_percentage_24h": change_pct,
                "current_price": 64600,
            }
        ],
    )
    records, error = sp.poll_coingecko_momentum(tmp_path)
    assert error is None
    assert len(records) == 1
    record = records[0]
    assert record["symbol"] == "BTC"
    assert record["action"] == expected_action
    assert record["network"] == "Bitcoin (native)"
    if expected_action == "HOLD":
        assert record["stop_loss"] is None and record["take_profit"] is None
    else:
        assert record["stop_loss"] is not None and record["take_profit"] is not None


def test_coingecko_skips_unknown_coin_ids(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: [
            {"id": "some-unlisted-coin", "price_change_percentage_24h": 10, "current_price": 1}
        ],
    )
    records, error = sp.poll_coingecko_momentum(tmp_path)
    assert records == []
    assert error is None


def test_binance_momentum_matches_coingecko_semantics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: [
            {"symbol": "BTCUSDT", "priceChangePercent": "6.5", "lastPrice": "64600"}
        ],
    )
    records, error = sp.poll_binance_momentum(tmp_path)
    assert error is None
    assert len(records) == 1
    record = records[0]
    assert record["symbol"] == "BTC"
    assert record["action"] == "BUY"
    assert record["entry_price"] == 64600.0
    assert record["stop_loss"] == pytest.approx(64600 * 0.95)


def test_binance_momentum_skips_malformed_rows(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        sp,
        "_get_json",
        lambda url, **kw: [
            {"symbol": "BTCUSDT", "priceChangePercent": "not-a-number", "lastPrice": "64600"}
        ],
    )
    records, error = sp.poll_binance_momentum(tmp_path)
    assert records == []
    assert error is None


def test_poll_all_sources_aggregates_added_configured_and_errors(
    tmp_path: Path, monkeypatch
) -> None:
    def fake_get_json(url, **kw):
        if "alternative.me" in url:
            return {"data": [{"value": "50", "value_classification": "Neutral"}]}
        if "coingecko" in url:
            return [{"id": "bitcoin", "price_change_percentage_24h": 0, "current_price": 1}]
        if "binance.com" in url and "ticker" in url:
            return [{"symbol": "BTCUSDT", "priceChangePercent": "0", "lastPrice": "1"}]
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(sp, "_get_json", fake_get_json)
    # Neutralize the canonical-rule poller (hits Binance klines + real spec file);
    # it has its own dedicated test module. _POLLERS captures function references at
    # import time, so patching sp._poll_canonical_eth_rule directly wouldn't affect
    # the tuple entry already built from it — replace the tuple itself instead.
    monkeypatch.setattr(
        sp,
        "_POLLERS",
        tuple(p for p in sp._POLLERS if p[0] != sp._CANONICAL_ETH_RULE_SOURCE),
    )

    result = sp.poll_all_sources(tmp_path)
    assert result["schema_version"] == 1
    assert result["added"][sp._FEAR_GREED_SOURCE] == 1
    assert result["added"][sp._COINGECKO_SOURCE] == 1
    assert result["added"][sp._BINANCE_SOURCE] == 1
    assert result["configured"][sp._FEAR_GREED_SOURCE] is True
    assert result["errors"] == []
    assert result["total_added"] == sum(result["added"].values())


def test_whale_alert_and_lunarcrush_are_not_in_the_active_registry() -> None:
    active_sources = {source for source, _poller, _env in sp._POLLERS}
    assert sp._WHALE_ALERT_SOURCE not in active_sources
    assert sp._LUNARCRUSH_SOURCE not in active_sources


def test_whale_alert_poller_is_a_noop_without_an_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("WHALE_ALERT_API_KEY", raising=False)
    records, error = sp.poll_whale_alert(tmp_path)
    assert records == []
    assert error is None


def test_lunarcrush_poller_is_a_noop_without_an_api_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("LUNARCRUSH_API_KEY", raising=False)
    records, error = sp.poll_lunarcrush(tmp_path)
    assert records == []
    assert error is None
