"""Checks for real historical hit-rate tracking (not a fabricated confidence number).

`_fetch_price_at` is monkeypatched throughout — no real network calls. Signals with a
controlled `received_at` are written directly to the inbox file (bypassing
`append_polled_signal`, which always stamps "now") so resolution-eligibility (>=24h
old) can be tested deterministically.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tios.services.dashboard_api import signal_reliability as sr
from tios.services.dashboard_api.signals_inbox import SIGNALS_INBOX_PATH, append_polled_signal


def _write_signal_at(tmp_path: Path, *, hours_ago: float, **fields) -> None:
    received_at = (datetime.now(tz=UTC) - timedelta(hours=hours_ago)).isoformat()
    record = {
        "schema_version": 2,
        "received_at": received_at,
        "source": "Test",
        "symbol": "BTC",
        "action": "BUY",
        "rationale": "r",
        "network": None,
        "strategy": None,
        "timeframe": None,
        "entry_price": 100.0,
        "stop_loss": None,
        "take_profit": None,
        "signal_strength": None,
        **fields,
    }
    path = tmp_path / SIGNALS_INBOX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(record) + "\n")


def test_signal_younger_than_horizon_is_not_resolved(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=23)
    monkeypatch.setattr(
        sr,
        "_fetch_price_at",
        lambda symbol, at: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )
    resolved = sr.resolve_pending_outcomes(tmp_path)
    assert resolved == 0


def test_signal_older_than_horizon_resolves_correct_buy(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25, entry_price=100.0, action="BUY")
    monkeypatch.setattr(sr, "_fetch_price_at", lambda symbol, at: 110.0)  # price went up
    resolved = sr.resolve_pending_outcomes(tmp_path)
    assert resolved == 1

    reliability = sr.build_reliability(tmp_path)
    stats = reliability["by_source"]["Test"]
    assert stats == {"resolved": 1, "correct": 1, "hit_rate_pct": 100.0, "pending": 0}


def test_signal_older_than_horizon_resolves_incorrect_sell(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25, entry_price=100.0, action="SELL")
    monkeypatch.setattr(
        sr, "_fetch_price_at", lambda symbol, at: 110.0
    )  # price went up: wrong for SELL
    sr.resolve_pending_outcomes(tmp_path)
    stats = sr.build_reliability(tmp_path)["by_source"]["Test"]
    assert stats["correct"] == 0
    assert stats["hit_rate_pct"] == 0.0


def test_resolution_is_idempotent_across_polls(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25)
    calls = []
    monkeypatch.setattr(sr, "_fetch_price_at", lambda symbol, at: calls.append(1) or 110.0)
    assert sr.resolve_pending_outcomes(tmp_path) == 1
    assert sr.resolve_pending_outcomes(tmp_path) == 0  # already resolved, no re-fetch
    assert len(calls) == 1


def test_fetch_failure_leaves_signal_pending_for_retry(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25)
    monkeypatch.setattr(sr, "_fetch_price_at", lambda symbol, at: None)
    assert sr.resolve_pending_outcomes(tmp_path) == 0
    # still resolvable later — not marked as permanently failed
    monkeypatch.setattr(sr, "_fetch_price_at", lambda symbol, at: 110.0)
    assert sr.resolve_pending_outcomes(tmp_path) == 1


def test_hold_and_informative_actions_are_never_tracked(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25, action="HOLD")
    _write_signal_at(tmp_path, hours_ago=25, action="INFORMATIVE")
    monkeypatch.setattr(
        sr,
        "_fetch_price_at",
        lambda symbol, at: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )
    assert sr.resolve_pending_outcomes(tmp_path) == 0
    assert sr.build_reliability(tmp_path)["by_source"] == {}


def test_signal_without_entry_price_is_never_tracked(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25, entry_price=None)
    monkeypatch.setattr(
        sr,
        "_fetch_price_at",
        lambda symbol, at: (_ for _ in ()).throw(AssertionError("should not fetch")),
    )
    assert sr.resolve_pending_outcomes(tmp_path) == 0


def test_reliability_reports_pending_for_recent_unresolvable_signals(tmp_path: Path) -> None:
    _write_signal_at(tmp_path, hours_ago=1)
    reliability = sr.build_reliability(tmp_path)
    assert reliability["by_source"]["Test"] == {
        "resolved": 0,
        "correct": 0,
        "hit_rate_pct": None,
        "pending": 1,
    }


def test_reliability_aggregates_per_source_independently(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25, source="A", entry_price=100.0, action="BUY")
    _write_signal_at(tmp_path, hours_ago=25, source="B", entry_price=100.0, action="BUY")
    monkeypatch.setattr(sr, "_fetch_price_at", lambda symbol, at: 90.0)  # both wrong
    sr.resolve_pending_outcomes(tmp_path)
    by_source = sr.build_reliability(tmp_path)["by_source"]
    assert by_source["A"]["hit_rate_pct"] == 0.0
    assert by_source["B"]["hit_rate_pct"] == 0.0
    assert set(by_source) == {"A", "B"}


def test_return_pct_is_recorded_on_the_outcome_record(tmp_path: Path, monkeypatch) -> None:
    _write_signal_at(tmp_path, hours_ago=25, entry_price=100.0, action="BUY")
    monkeypatch.setattr(sr, "_fetch_price_at", lambda symbol, at: 105.0)
    sr.resolve_pending_outcomes(tmp_path)
    outcomes_path = tmp_path / sr.OUTCOMES_PATH
    outcome = json.loads(outcomes_path.read_text().splitlines()[0])
    assert outcome["return_pct"] == 5.0
    assert outcome["correct"] is True


def test_build_reliability_never_touches_the_network(tmp_path: Path, monkeypatch) -> None:
    append_polled_signal(
        tmp_path, source="A", symbol="BTC", action="BUY", rationale="r", entry_price=100
    )

    def boom(*a, **kw):
        raise AssertionError("build_reliability must not fetch")

    monkeypatch.setattr(sr, "_fetch_price_at", boom)
    sr.build_reliability(tmp_path)  # must not raise
