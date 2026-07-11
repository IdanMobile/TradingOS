#!/usr/bin/env python3
"""Replay the external 3Commas-style DCA hypothesis on frozen local candles.

This runner is deliberately evidence-only. It models the OS-local DCA hypothesis
from strategies/external/3commas-dca-config/canonical_strategy_spec.yaml without
creating a platform bot, account connection, paper wallet, venue order, or live
trading path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "strategies" / "external" / "3commas-dca-config" / "canonical_strategy_spec.yaml"
OUTPUT_ROOT = ROOT / "artifacts" / "external_replay" / "3commas_dca"
FROZEN_MANIFEST = ROOT / "artifacts" / "datasets" / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
QUALITY_REPORT = ROOT / "artifacts" / "datasets" / "QUALITY_REPORT.json"
DATASETS = {
    f"{instrument}_{timeframe}": ROOT / "data" / "normalized" / f"{instrument}_{timeframe}.parquet"
    for instrument in ("BTCUSDT", "ETHUSDT")
    for timeframe in ("5m", "15m", "1h")
}
INITIAL_CASH = Decimal("1000")
FEE_RATE = Decimal("0.001")


@dataclass(frozen=True)
class DcaConfig:
    strategy_id: str
    rsi_window: int
    rsi_threshold: Decimal
    sma_window: int
    start_fraction: Decimal
    add_fraction: Decimal
    max_position_fraction: Decimal
    add_steps: tuple[Decimal, ...]
    stop_loss: Decimal


@dataclass(frozen=True)
class DcaEvent:
    event_type: str
    signal_index: int
    execution_index: int
    signal_close: str
    execution_open: str
    reason: str
    gross_notional: str
    fee_paid: str
    cash_after: str
    quantity_after: str
    equity_after: str


@dataclass(frozen=True)
class DcaTrial:
    dataset: str
    bars: int
    status: str
    total_return: str
    final_equity: str
    event_count: int
    entries: int
    adds: int
    exits: int
    open_position_at_end: bool
    events_path: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _decimal(value: object, field: str) -> Decimal:
    if value is None:
        raise ValueError(f"{field} is required")
    return Decimal(str(value))


def _int_param(raw: dict[str, object], key: str) -> int:
    value = raw.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def load_config(path: Path = SPEC) -> DcaConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("strategy spec must be a mapping")
    indicators = raw.get("indicators")
    if not isinstance(indicators, list):
        raise ValueError("indicators must be a list")
    rsi_window = 0
    sma_window = 0
    for item in indicators:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        params = item.get("parameters")
        if not isinstance(params, dict):
            continue
        if name == "rsi":
            rsi_window = _int_param(params, "window")
        if name == "sma_recovery":
            sma_window = _int_param(params, "window")
    sizing = raw.get("position_sizing")
    risk = raw.get("risk")
    if not isinstance(sizing, dict) or not isinstance(risk, dict):
        raise ValueError("position_sizing and risk must be mappings")
    entry = raw.get("entry_long")
    threshold = Decimal("35")
    if isinstance(entry, dict) and isinstance(entry.get("all"), list):
        for clause in entry["all"]:
            if isinstance(clause, str) and clause.startswith("rsi < "):
                threshold = Decimal(clause.removeprefix("rsi < ").strip())
    return DcaConfig(
        strategy_id=str(raw["strategy_id"]),
        rsi_window=rsi_window,
        rsi_threshold=threshold,
        sma_window=sma_window,
        start_fraction=_decimal(sizing.get("fraction"), "fraction"),
        add_fraction=_decimal(sizing.get("dca_add_fraction"), "dca_add_fraction"),
        max_position_fraction=_decimal(
            sizing.get("max_position_fraction"), "max_position_fraction"
        ),
        add_steps=tuple(
            _decimal(value, "add_on_drawdown_steps") for value in sizing["add_on_drawdown_steps"]
        ),
        stop_loss=_decimal(risk.get("stop_loss"), "stop_loss"),
    )


def load_candles(path: Path) -> dict[str, list[Decimal]]:
    table = pq.read_table(path, columns=["open", "high", "low", "close"])
    return {
        name: [Decimal(str(value.as_py())) for value in table.column(name)]
        for name in ("open", "high", "low", "close")
    }


def rolling_mean(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    total = Decimal("0")
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        if index + 1 >= window:
            result[index] = total / Decimal(window)
    return result


def wilder_rsi(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    average_gain = Decimal("0")
    average_loss = Decimal("0")
    hundred = Decimal("100")
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gain = delta if delta > 0 else Decimal("0")
        loss = -delta if delta < 0 else Decimal("0")
        if index <= window:
            average_gain += gain / Decimal(window)
            average_loss += loss / Decimal(window)
            if index < window:
                continue
        else:
            average_gain = (average_gain * Decimal(window - 1) + gain) / Decimal(window)
            average_loss = (average_loss * Decimal(window - 1) + loss) / Decimal(window)
        result[index] = (
            hundred
            if average_loss == 0
            else hundred - hundred / (Decimal("1") + average_gain / average_loss)
        )
    return result


def _equity(cash: Decimal, quantity: Decimal, mark_price: Decimal) -> Decimal:
    return cash + quantity * mark_price


def _buy(
    *,
    cash: Decimal,
    quantity: Decimal,
    gross_notional: Decimal,
    execution_open: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    notional = min(cash, gross_notional)
    fee = notional * FEE_RATE
    acquired = (notional - fee) / execution_open
    return cash - notional, quantity + acquired, fee


def simulate_dca(
    candles: dict[str, list[Decimal]], config: DcaConfig, *, events_path: Path | None = None
) -> tuple[DcaTrial, list[DcaEvent]]:
    opens = candles["open"]
    closes = candles["close"]
    rsi = wilder_rsi(closes, config.rsi_window)
    sma = rolling_mean(closes, config.sma_window)
    cash = INITIAL_CASH
    quantity = Decimal("0")
    initial_entry_price: Decimal | None = None
    next_add_step = 0
    events: list[DcaEvent] = []

    for signal_index in range(len(opens) - 1):
        close = closes[signal_index]
        execution_open = opens[signal_index + 1]
        mark_for_equity = execution_open
        current_rsi = rsi[signal_index]
        current_sma = sma[signal_index]
        if quantity == 0:
            if current_rsi is None or current_sma is None or current_rsi >= config.rsi_threshold:
                continue
            cash, quantity, fee = _buy(
                cash=cash,
                quantity=quantity,
                gross_notional=INITIAL_CASH * config.start_fraction,
                execution_open=execution_open,
            )
            initial_entry_price = execution_open
            next_add_step = 0
            events.append(
                DcaEvent(
                    event_type="ENTRY",
                    signal_index=signal_index,
                    execution_index=signal_index + 1,
                    signal_close=str(close),
                    execution_open=str(execution_open),
                    reason=f"rsi<{config.rsi_threshold}",
                    gross_notional=str(INITIAL_CASH * config.start_fraction),
                    fee_paid=str(fee),
                    cash_after=str(cash),
                    quantity_after=str(quantity),
                    equity_after=str(_equity(cash, quantity, mark_for_equity)),
                )
            )
            continue

        if initial_entry_price is None:
            raise RuntimeError("position has quantity but no initial entry price")
        drawdown = close / initial_entry_price - Decimal("1")
        exit_reason: str | None = None
        if drawdown <= -config.stop_loss:
            exit_reason = "stop_loss"
        elif current_sma is not None and close > current_sma:
            exit_reason = "sma_recovery"
        if exit_reason is not None:
            gross = quantity * execution_open
            fee = gross * FEE_RATE
            cash += gross - fee
            quantity = Decimal("0")
            initial_entry_price = None
            next_add_step = 0
            events.append(
                DcaEvent(
                    event_type="EXIT",
                    signal_index=signal_index,
                    execution_index=signal_index + 1,
                    signal_close=str(close),
                    execution_open=str(execution_open),
                    reason=exit_reason,
                    gross_notional=str(gross),
                    fee_paid=str(fee),
                    cash_after=str(cash),
                    quantity_after=str(quantity),
                    equity_after=str(cash),
                )
            )
            continue

        max_steps = int(
            (config.max_position_fraction - config.start_fraction) / config.add_fraction
        )
        max_steps = min(max_steps, len(config.add_steps))
        while next_add_step < max_steps and drawdown <= config.add_steps[next_add_step]:
            gross = INITIAL_CASH * config.add_fraction
            cash, quantity, fee = _buy(
                cash=cash,
                quantity=quantity,
                gross_notional=gross,
                execution_open=execution_open,
            )
            events.append(
                DcaEvent(
                    event_type="ADD",
                    signal_index=signal_index,
                    execution_index=signal_index + 1,
                    signal_close=str(close),
                    execution_open=str(execution_open),
                    reason=f"drawdown<={config.add_steps[next_add_step]}",
                    gross_notional=str(gross),
                    fee_paid=str(fee),
                    cash_after=str(cash),
                    quantity_after=str(quantity),
                    equity_after=str(_equity(cash, quantity, mark_for_equity)),
                )
            )
            next_add_step += 1

    final_equity = _equity(cash, quantity, closes[-1])
    if events_path is not None:
        events_path.write_text(
            "".join(json.dumps(asdict(event), sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
    relative_events_path = str(events_path.relative_to(ROOT)) if events_path else ""
    trial = DcaTrial(
        dataset="",
        bars=len(opens),
        status="COMPLETED",
        total_return=str(final_equity / INITIAL_CASH - Decimal("1")),
        final_equity=str(final_equity),
        event_count=len(events),
        entries=sum(1 for event in events if event.event_type == "ENTRY"),
        adds=sum(1 for event in events if event.event_type == "ADD"),
        exits=sum(1 for event in events if event.event_type == "EXIT"),
        open_position_at_end=quantity > 0,
        events_path=relative_events_path,
    )
    return trial, events


def build_hashes(config: DcaConfig) -> dict[str, str]:
    return {
        **{f"dataset_{name}": sha256(path) for name, path in DATASETS.items()},
        "frozen_manifest": sha256(FROZEN_MANIFEST),
        "quality_report": sha256(QUALITY_REPORT),
        "runner": sha256(Path(__file__)),
        "spec": sha256(SPEC),
        "config": canonical_hash(asdict(config)),
    }


def run_replay() -> dict[str, Any]:
    config = load_config()
    hashes = build_hashes(config)
    replay_id = "EXTDCA-" + canonical_hash(hashes)[:32]
    out = OUTPUT_ROOT / replay_id
    result_path = out / "replay_run.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["reused"] = True
        return result
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(tz=UTC).isoformat()
    trials: list[DcaTrial] = []
    for dataset_name, dataset_path in DATASETS.items():
        candles = load_candles(dataset_path)
        events_path = out / f"{dataset_name}_events.jsonl"
        trial, _ = simulate_dca(candles, config, events_path=events_path)
        trials.append(
            DcaTrial(
                **{
                    **asdict(trial),
                    "dataset": dataset_name,
                    "events_path": str(events_path.relative_to(ROOT)),
                }
            )
        )
    scorecard = {
        "schema": "tios-external-dca-replay-scorecard-v1",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "strategy_id": config.strategy_id,
        "validation_state": "UNVALIDATED",
        "approval_status": "NOT_ELIGIBLE",
        "promotion_eligible": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_demo_live": "DISABLED",
        "winner_selected": False,
        "fee_rate": str(FEE_RATE),
        "initial_cash": str(INITIAL_CASH),
        "trials": [asdict(trial) for trial in trials],
        "best_total_return": max(trial.total_return for trial in trials),
        "blockers": [
            "local external-source replay only; no platform reproduction",
            "no cross-engine reproduction exists for this DCA add-on model",
            "no temporal/G10 validation package exists for this external candidate",
            "candidate remains unvalidated and not promotion eligible",
        ],
        "prohibited": [
            "credential_request",
            "account_connection",
            "platform_bot_execution",
            "order_routing",
            "paper_demo_or_live_activation",
            "profit_claim_inheritance",
        ],
    }
    scorecard_path = out / "scorecard.json"
    scorecard_path.write_text(
        json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    finished = datetime.now(tz=UTC).isoformat()
    artifacts = {
        path.name: sha256(path)
        for path in sorted(out.iterdir())
        if path.name not in {"manifest.json", "replay_run.json"}
    }
    manifest = {
        "schema": "tios-external-dca-replay-manifest-v1",
        "replay_id": replay_id,
        "status": "COMPLETED",
        "mode": "OFFLINE_RESEARCH_ONLY",
        "strategy_id": config.strategy_id,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_orders": "DISABLED",
        "live_orders": "DISABLED",
        "hashes": hashes,
        "artifacts": artifacts,
        "started_at_utc": started,
        "finished_at_utc": finished,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result = {
        **manifest,
        "schema": "tios-external-dca-replay-run-v1",
        "reused": False,
        "counts": {
            "datasets": len(DATASETS),
            "trials": len(trials),
            "events": sum(trial.event_count for trial in trials),
        },
        "scorecard_path": str(scorecard_path.relative_to(ROOT)),
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "artifact_manifest_sha256": sha256(manifest_path),
        "content_sha256": canonical_hash({"manifest": manifest, "scorecard": scorecard}),
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    result = run_replay()
    print(
        json.dumps(
            {
                "replay_id": result["replay_id"],
                "reused": result["reused"],
                "scorecard_path": result["scorecard_path"],
                "counts": result["counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
