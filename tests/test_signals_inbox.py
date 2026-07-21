"""Checks for the local signals webhook inbox (validation, storage, projection)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tios.services.dashboard_api.signals_inbox import (
    SignalIngestError,
    append_polled_signal,
    build_signals,
    ingest_signal,
)


def test_ingest_disabled_without_secret_env_var(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TIOS_SIGNALS_WEBHOOK_SECRET", raising=False)
    with pytest.raises(SignalIngestError) as excinfo:
        ingest_signal(tmp_path, {"secret": "x", "source": "Test", "symbol": "BTC", "action": "BUY"})
    assert excinfo.value.status_code == 503


def test_ingest_rejects_wrong_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    with pytest.raises(SignalIngestError) as excinfo:
        ingest_signal(
            tmp_path, {"secret": "wrong", "source": "Test", "symbol": "BTC", "action": "BUY"}
        )
    assert excinfo.value.status_code == 401


@pytest.mark.parametrize("action", ["BUY", "SELL", "HOLD", "INFORMATIVE"])
def test_ingest_accepts_every_valid_action(tmp_path: Path, monkeypatch, action: str) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    record = ingest_signal(
        tmp_path, {"secret": "correct", "source": "Test", "symbol": "btc", "action": action}
    )
    assert record["action"] == action
    assert record["symbol"] == "BTC"  # normalized to uppercase


def test_ingest_rejects_invalid_action(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    with pytest.raises(SignalIngestError) as excinfo:
        ingest_signal(
            tmp_path, {"secret": "correct", "source": "Test", "symbol": "BTC", "action": "MOON"}
        )
    assert excinfo.value.status_code == 400


@pytest.mark.parametrize(
    "source",
    [
        "Fear & Greed Index (free)",
        "CoinGecko 24h momentum (free)",
        "Canonical ETH volume-breakout rule (live/unreviewed)",
        "TradingView Webhook",
        "a",
    ],
)
def test_ingest_accepts_real_source_names_used_by_the_pollers(
    tmp_path: Path, monkeypatch, source: str
) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    record = ingest_signal(
        tmp_path, {"secret": "correct", "source": source, "symbol": "BTC", "action": "HOLD"}
    )
    assert record["source"] == source


def test_ingest_rejects_source_with_disallowed_characters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    with pytest.raises(SignalIngestError) as excinfo:
        ingest_signal(
            tmp_path,
            {"secret": "correct", "source": "bad<script>", "symbol": "BTC", "action": "HOLD"},
        )
    assert excinfo.value.status_code == 400


def test_ingest_optional_fields_round_trip(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    record = ingest_signal(
        tmp_path,
        {
            "secret": "correct",
            "source": "Test",
            "symbol": "BTC",
            "action": "BUY",
            "network": "Bitcoin (native)",
            "strategy": "test rule",
            "timeframe": "1h",
            "entry_price": 64600,
            "stop_loss": 61370,
            "take_profit": [67830, 71060],
        },
    )
    assert record["network"] == "Bitcoin (native)"
    assert record["entry_price"] == 64600
    assert record["stop_loss"] == 61370
    assert record["take_profit"] == [67830, 71060]


def test_ingest_optional_fields_default_to_none_when_omitted(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    record = ingest_signal(
        tmp_path, {"secret": "correct", "source": "Test", "symbol": "BTC", "action": "HOLD"}
    )
    for field in ("network", "strategy", "timeframe", "entry_price", "stop_loss", "take_profit"):
        assert record[field] is None


def test_ingest_rejects_non_positive_entry_price(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    with pytest.raises(SignalIngestError) as excinfo:
        ingest_signal(
            tmp_path,
            {
                "secret": "correct",
                "source": "Test",
                "symbol": "BTC",
                "action": "BUY",
                "entry_price": -5,
            },
        )
    assert excinfo.value.status_code == 400


@pytest.mark.parametrize("strength", [0, 50, 100, 0.0, 99.9])
def test_ingest_accepts_signal_strength_in_bounds(
    tmp_path: Path, monkeypatch, strength: float
) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    record = ingest_signal(
        tmp_path,
        {
            "secret": "correct",
            "source": "Test",
            "symbol": "BTC",
            "action": "BUY",
            "signal_strength": strength,
        },
    )
    assert record["signal_strength"] == strength


@pytest.mark.parametrize("strength", [-1, 100.1, 1000])
def test_ingest_rejects_signal_strength_out_of_bounds(
    tmp_path: Path, monkeypatch, strength: float
) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    with pytest.raises(SignalIngestError) as excinfo:
        ingest_signal(
            tmp_path,
            {
                "secret": "correct",
                "source": "Test",
                "symbol": "BTC",
                "action": "BUY",
                "signal_strength": strength,
            },
        )
    assert excinfo.value.status_code == 400


def test_ingest_rejects_oversized_rationale(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "correct")
    with pytest.raises(SignalIngestError):
        ingest_signal(
            tmp_path,
            {
                "secret": "correct",
                "source": "Test",
                "symbol": "BTC",
                "action": "HOLD",
                "rationale": "x" * 501,
            },
        )


def test_append_polled_signal_bypasses_secret_but_shares_validation(tmp_path: Path) -> None:
    record = append_polled_signal(
        tmp_path, source="Fear & Greed Index (free)", symbol="btc", action="hold", rationale="ok"
    )
    assert record["symbol"] == "BTC"
    assert record["action"] == "HOLD"
    with pytest.raises(SignalIngestError):
        append_polled_signal(tmp_path, source="Test", symbol="BTC", action="NOT_AN_ACTION")


def test_build_signals_projects_newest_first_and_dedups_sources(tmp_path: Path) -> None:
    append_polled_signal(tmp_path, source="A", symbol="BTC", action="BUY", rationale="first")
    append_polled_signal(tmp_path, source="B", symbol="ETH", action="SELL", rationale="second")
    append_polled_signal(tmp_path, source="A", symbol="SOL", action="HOLD", rationale="third")

    data = build_signals(tmp_path)
    assert data["signal_count"] == 3
    assert [s["rationale"] for s in data["signals"]] == ["third", "second", "first"]
    assert {s["name"] for s in data["sources"]} == {"A", "B"}


def test_build_signals_empty_inbox_is_a_clean_zero_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TIOS_SIGNALS_WEBHOOK_SECRET", raising=False)
    data = build_signals(tmp_path)
    assert data == {
        "schema_version": 1,
        "signal_count": 0,
        "signals": [],
        "sources": [],
        "ingest_enabled": False,
    }


def test_build_signals_ingest_enabled_reflects_env_var(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TIOS_SIGNALS_WEBHOOK_SECRET", "x")
    assert build_signals(tmp_path)["ingest_enabled"] is True
    monkeypatch.delenv("TIOS_SIGNALS_WEBHOOK_SECRET")
    assert build_signals(tmp_path)["ingest_enabled"] is False
