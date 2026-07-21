"""Checks for the independent live ETH-volume-breakout-rule poller.

Loads the REAL canonical spec from the project root (read-only, matches
tests/test_eth_volume_breakout_flow.py's convention) so the rule under test can't
drift from the canonical definition, but never touches real network or the real
signals inbox — `_get_json`/`_load_spec` are monkeypatched per test.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from tios.services.dashboard_api import canonical_signal_poller as csp

ROOT = Path(__file__).resolve().parents[1]


def _kline_row(close_time_ms: int, *, high="100", low="100", close="100", volume="100") -> list:
    return [close_time_ms - 3_600_000, "100", high, low, close, volume, close_time_ms]


def test_load_spec_reads_the_real_canonical_eth_strategy() -> None:
    spec = csp._load_spec(ROOT)
    assert spec.strategy_id == "STRAT-ETH-volume-breakout-prospective-v1"
    assert spec.risk == {"stop_loss": None, "take_profit": None, "execution_authority": "NONE"}


def test_fetch_bars_excludes_the_still_forming_candle(monkeypatch) -> None:
    now_ms = time.time() * 1000
    closed = _kline_row(int(now_ms) - 10_000)  # closed 10s ago
    forming = _kline_row(int(now_ms) + 3_600_000)  # closes an hour from now

    monkeypatch.setattr(csp, "_get_json", lambda url, **kw: [closed, forming])
    bars = csp._fetch_bars("BTCUSDT")
    assert len(bars) == 1
    assert bars[0].close == 100


def test_fetch_bars_maps_ohlcv_fields_correctly(monkeypatch) -> None:
    row = _kline_row(
        int(time.time() * 1000) - 10_000, high="105", low="95", close="102", volume="50"
    )
    monkeypatch.setattr(csp, "_get_json", lambda url, **kw: [row])
    bars = csp._fetch_bars("ETHUSDT")
    assert len(bars) == 1
    bar = bars[0]
    assert (bar.high, bar.low, bar.close, bar.volume) == (105, 95, 102, 50)


def test_fetch_bars_captures_the_real_bar_close_time(monkeypatch) -> None:
    close_time_ms = 1784459999999
    row = _kline_row(close_time_ms)
    monkeypatch.setattr(csp, "_get_json", lambda url, **kw: [row])
    bars = csp._fetch_bars("BTCUSDT")
    assert bars[0].close_time.isoformat() == "2026-07-19T11:19:59.999000+00:00"


def test_poll_canonical_eth_rule_reports_the_bars_own_close_time_not_poll_time(
    tmp_path: Path, monkeypatch
) -> None:
    real_spec = csp._load_spec(ROOT)
    monkeypatch.setattr(csp, "_load_spec", lambda root: real_spec)
    close_time = datetime(2026, 7, 19, 15, 59, 59, tzinfo=UTC)
    bars = _warmup_bars(40) + [
        csp._LiveBar(open=100, high=160, low=100, close=155, volume=200, close_time=close_time)
    ]
    monkeypatch.setattr(csp, "_fetch_bars", lambda symbol: tuple(bars))
    records, _ = csp.poll_canonical_eth_rule(tmp_path)
    assert records[0]["observed_at"] == close_time.isoformat()
    # received_at (when we stored it) is stamped later, in append_polled_signal —
    # this raw record only carries what the poller itself knows: the real bar time.
    assert "received_at" not in records[0]


def _warmup_bars(count: int = 40) -> list[csp._LiveBar]:
    return [csp._LiveBar(open=100, high=100, low=100, close=100, volume=100) for _ in range(count)]


def _evaluate_latest(bars: list[csp._LiveBar]) -> tuple[bool, bool]:
    from tios.strategy.evaluator import _indicator_contexts, evaluate_rule_tree

    spec = csp._load_spec(ROOT)
    contexts = _indicator_contexts(spec, tuple(bars))
    context = contexts[-1]
    assert context is not None, "not enough warm-up bars for the indicators"
    entry = evaluate_rule_tree(spec.entry_long, context)
    exit_ = evaluate_rule_tree(spec.exit_long, context)
    return entry, exit_


def test_rule_fires_buy_on_a_high_volume_breakout_above_the_channel() -> None:
    bars = _warmup_bars(40) + [csp._LiveBar(open=100, high=160, low=100, close=155, volume=200)]
    entry, exit_ = _evaluate_latest(bars)
    assert entry is True
    assert exit_ is False  # close is above the prior lower band too


def test_rule_fires_sell_when_close_drops_below_the_prior_lower_band() -> None:
    bars = _warmup_bars(40) + [csp._LiveBar(open=100, high=100, low=40, close=40, volume=50)]
    entry, exit_ = _evaluate_latest(bars)
    assert entry is False
    assert exit_ is True


def test_rule_holds_when_inside_the_channel_with_normal_volume() -> None:
    bars = _warmup_bars(40) + [csp._LiveBar(open=100, high=105, low=95, close=100, volume=100)]
    entry, exit_ = _evaluate_latest(bars)
    assert entry is False
    assert exit_ is False


def test_breakout_strength_scales_zero_at_band_to_capped_100() -> None:
    context = {"donchian_upper": 100.0, "donchian_lower": 90.0}
    assert csp._breakout_strength("BUY", 100.0, context) == 0.0  # exactly at the band
    assert csp._breakout_strength("BUY", 103.0, context) == 100.0  # 3%+ overshoot: capped
    assert 0 < csp._breakout_strength("BUY", 101.5, context) < 100
    assert csp._breakout_strength("SELL", 90.0, context) == 0.0
    assert csp._breakout_strength("HOLD", 95.0, context) is None


def test_poll_canonical_eth_rule_labels_every_signal_as_independent_and_unreviewed(
    tmp_path: Path, monkeypatch
) -> None:
    real_spec = csp._load_spec(ROOT)
    monkeypatch.setattr(csp, "_load_spec", lambda root: real_spec)
    breakout_bars = _warmup_bars(40) + [
        csp._LiveBar(open=100, high=160, low=100, close=155, volume=200)
    ]
    monkeypatch.setattr(csp, "_fetch_bars", lambda symbol: tuple(breakout_bars))

    records, error = csp.poll_canonical_eth_rule(tmp_path)
    assert error is None
    assert len(records) == len(csp._WATCHLIST)
    for record in records:
        assert record["action"] == "BUY"
        assert record["source"] == csp._SOURCE
        assert "not the project's frozen/reviewed reproduction" in record["rationale"]
        assert "not a preregistered prospective observation" in record["rationale"]
        # Real spec's risk block is null; the fields are omitted, not fabricated.
        assert "stop_loss" not in record
        assert "take_profit" not in record
        assert record["entry_price"] == 155.0


def test_poll_canonical_eth_rule_respects_cooldown(tmp_path: Path, monkeypatch) -> None:
    from tios.services.dashboard_api.signals_inbox import append_polled_signal

    append_polled_signal(tmp_path, source=csp._SOURCE, symbol="BTC", action="HOLD", rationale="r")
    fetch_calls = []
    monkeypatch.setattr(csp, "_fetch_bars", lambda symbol: fetch_calls.append(symbol) or ())

    records, error = csp.poll_canonical_eth_rule(tmp_path)
    assert records == []
    assert error is None
    assert fetch_calls == []  # cooldown skipped fetching entirely


def test_poll_canonical_eth_rule_collects_per_symbol_errors_without_aborting(
    tmp_path: Path, monkeypatch
) -> None:
    real_spec = csp._load_spec(ROOT)
    monkeypatch.setattr(csp, "_load_spec", lambda root: real_spec)

    def flaky_fetch(symbol: str):
        if symbol == "BTCUSDT":
            raise ValueError("network blip")
        return tuple(
            _warmup_bars(40) + [csp._LiveBar(open=100, high=100, low=100, close=100, volume=100)]
        )

    monkeypatch.setattr(csp, "_fetch_bars", flaky_fetch)
    records, error = csp.poll_canonical_eth_rule(tmp_path)
    assert error is not None and "BTC" in error
    assert len(records) == len(csp._WATCHLIST) - 1  # every other symbol still succeeded
