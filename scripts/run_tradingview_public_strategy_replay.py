#!/usr/bin/env python3
"""Replay selected TradingView public-strategy hypotheses on frozen local candles.

This runner uses only public page summaries captured as source evidence. It does not
copy Pine source, access protected scripts, connect a TradingView account, subscribe
to alerts, or expose any execution path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "artifacts" / "external_replay" / "tradingview_public_strategies"
SELECTED = (
    ROOT / "artifacts/source_intake/tradingview_public_strategies/"
    "selected_candidates_2026_07_11.json"
)
FROZEN_MANIFEST = ROOT / "artifacts" / "datasets" / "DS-CRYPTO-SPOT-BAKEOFF-V1.manifest.json"
QUALITY_REPORT = ROOT / "artifacts" / "datasets" / "QUALITY_REPORT.json"
DATASETS = {
    f"{instrument}_{timeframe}": ROOT / "data" / "normalized" / f"{instrument}_{timeframe}.parquet"
    for instrument in ("BTCUSDT", "ETHUSDT")
    for timeframe in ("5m", "15m", "1h")
}
INITIAL_CASH = Decimal("10000")


@dataclass(frozen=True)
class StrategyConfig:
    candidate_id: str
    strategy_family: Literal["rsi_mean_reversion", "bb_atr_ema"]
    source_url: str
    rule_capture_status: str
    source_code_status: str
    strategy_tester_status: str
    notes: tuple[str, ...]
    parameters: dict[str, str]
    source_evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class ReplayEvent:
    event_type: str
    signal_index: int
    execution_index: int
    reason: str
    signal_close: str
    execution_price: str
    gross_notional: str
    fee_paid: str
    cash_after: str
    quantity_after: str
    equity_after: str


@dataclass(frozen=True)
class ReplayTrial:
    candidate_id: str
    dataset: str
    bars: int
    status: str
    total_return: str
    final_equity: str
    event_count: int
    entries: int
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


def rolling_std(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    for index in range(window - 1, len(values)):
        sample = values[index - window + 1 : index + 1]
        mean = sum(sample, Decimal("0")) / Decimal(window)
        variance = sum((value - mean) ** 2 for value in sample) / Decimal(window)
        result[index] = Decimal(str(float(variance) ** 0.5))
    return result


def ema(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < window:
        return result
    current = sum(values[:window], Decimal("0")) / Decimal(window)
    result[window - 1] = current
    alpha = Decimal("2") / Decimal(window + 1)
    for index in range(window, len(values)):
        current = values[index] * alpha + current * (Decimal("1") - alpha)
        result[index] = current
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


def atr(candles: dict[str, list[Decimal]], window: int) -> list[Decimal | None]:
    highs = candles["high"]
    lows = candles["low"]
    closes = candles["close"]
    true_ranges: list[Decimal] = []
    for index, high in enumerate(highs):
        if index == 0:
            true_ranges.append(high - lows[index])
        else:
            previous = closes[index - 1]
            true_ranges.append(
                max(high - lows[index], abs(high - previous), abs(lows[index] - previous))
            )
    result: list[Decimal | None] = [None] * len(true_ranges)
    if len(true_ranges) < window:
        return result
    current = sum(true_ranges[:window], Decimal("0")) / Decimal(window)
    result[window - 1] = current
    for index in range(window, len(true_ranges)):
        current = (current * Decimal(window - 1) + true_ranges[index]) / Decimal(window)
        result[index] = current
    return result


def _equity(cash: Decimal, quantity: Decimal, mark: Decimal) -> Decimal:
    return cash + quantity * mark


def _buy(
    cash: Decimal,
    quantity: Decimal,
    notional: Decimal,
    execution_price: Decimal,
    fee_rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    gross = min(cash, notional)
    fee = gross * fee_rate
    acquired = (gross - fee) / execution_price
    return cash - gross, quantity + acquired, fee, gross


def _sell(
    cash: Decimal,
    quantity: Decimal,
    execution_price: Decimal,
    fee_rate: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    gross = quantity * execution_price
    fee = gross * fee_rate
    return cash + gross - fee, Decimal("0"), fee, gross


def _execution_price(open_price: Decimal, tick_size: Decimal, ticks: Decimal, side: str) -> Decimal:
    slippage = tick_size * ticks
    return (
        open_price + slippage
        if side == "buy"
        else max(Decimal("0.00000001"), open_price - slippage)
    )


def simulate_rsi(
    candles: dict[str, list[Decimal]], config: StrategyConfig, events_path: Path | None = None
) -> tuple[ReplayTrial, list[ReplayEvent]]:
    opens = candles["open"]
    closes = candles["close"]
    lows = candles["low"]
    params = config.parameters
    rsi = wilder_rsi(closes, int(params["rsi_window"]))
    enter_lte = Decimal(params["entry_rsi_lte"])
    exit_gte = Decimal(params["exit_rsi_gte"])
    fee_rate = Decimal(params["commission_rate"])
    tick_size = Decimal(params["tick_size"])
    slippage_ticks = Decimal(params["slippage_ticks"])
    stop_loss = Decimal(params["stop_loss_pct"])
    cash = INITIAL_CASH
    quantity = Decimal("0")
    entry_price: Decimal | None = None
    events: list[ReplayEvent] = []
    for signal_index in range(len(opens) - 1):
        current_rsi = rsi[signal_index]
        execution_index = signal_index + 1
        if current_rsi is None:
            continue
        if quantity == 0 and current_rsi <= enter_lte:
            price = _execution_price(opens[execution_index], tick_size, slippage_ticks, "buy")
            cash, quantity, fee, gross = _buy(cash, quantity, cash, price, fee_rate)
            entry_price = price
            events.append(
                _event(
                    "ENTRY",
                    signal_index,
                    execution_index,
                    "rsi_entry",
                    closes[signal_index],
                    price,
                    gross,
                    fee,
                    cash,
                    quantity,
                )
            )
            continue
        if quantity > 0 and entry_price is not None:
            stop_hit = lows[signal_index] <= entry_price * (Decimal("1") - stop_loss)
            exit_signal = current_rsi >= exit_gte
            if stop_hit or exit_signal:
                price = _execution_price(opens[execution_index], tick_size, slippage_ticks, "sell")
                reason = "stop_loss" if stop_hit else "rsi_exit"
                cash, quantity, fee, gross = _sell(cash, quantity, price, fee_rate)
                events.append(
                    _event(
                        "EXIT",
                        signal_index,
                        execution_index,
                        reason,
                        closes[signal_index],
                        price,
                        gross,
                        fee,
                        cash,
                        quantity,
                    )
                )
                entry_price = None
    return _trial(
        config.candidate_id, "", opens, closes[-1], cash, quantity, events, events_path
    ), events


def simulate_bb(
    candles: dict[str, list[Decimal]], config: StrategyConfig, events_path: Path | None = None
) -> tuple[ReplayTrial, list[ReplayEvent]]:
    opens = candles["open"]
    lows = candles["low"]
    closes = candles["close"]
    params = config.parameters
    mean = rolling_mean(closes, int(params["bb_window"]))
    std = rolling_std(closes, int(params["bb_window"]))
    trend = ema(closes, int(params["ema_window"]))
    volatility = atr(candles, int(params["atr_window"]))
    mult = Decimal(params["bb_stddev_mult"])
    fee_rate = Decimal(params["commission_rate"])
    tick_size = Decimal(params["tick_size"])
    slippage_ticks = Decimal(params["slippage_ticks"])
    stop_atr = Decimal(params["stop_loss_atr_mult"])
    trail_atr = Decimal(params["trail_activation_atr_mult"])
    position_fraction = Decimal(params["position_fraction"])
    cash = INITIAL_CASH
    quantity = Decimal("0")
    entry_price: Decimal | None = None
    trail_active = False
    events: list[ReplayEvent] = []
    for signal_index in range(len(opens) - 1):
        if any(
            value is None
            for value in (
                mean[signal_index],
                std[signal_index],
                trend[signal_index],
                volatility[signal_index],
            )
        ):
            continue
        assert mean[signal_index] is not None
        assert std[signal_index] is not None
        assert trend[signal_index] is not None
        assert volatility[signal_index] is not None
        lower_band = mean[signal_index] - mult * std[signal_index]
        execution_index = signal_index + 1
        if (
            quantity == 0
            and closes[signal_index] > trend[signal_index]
            and lows[signal_index] < lower_band
        ):
            price = _execution_price(opens[execution_index], tick_size, slippage_ticks, "buy")
            cash, quantity, fee, gross = _buy(
                cash, quantity, INITIAL_CASH * position_fraction, price, fee_rate
            )
            entry_price = price
            trail_active = False
            events.append(
                _event(
                    "ENTRY",
                    signal_index,
                    execution_index,
                    "bb_dip_above_ema",
                    closes[signal_index],
                    price,
                    gross,
                    fee,
                    cash,
                    quantity,
                )
            )
            continue
        if quantity > 0 and entry_price is not None:
            trail_active = (
                trail_active
                or closes[signal_index] >= entry_price + trail_atr * volatility[signal_index]
            )
            stop_hit = closes[signal_index] <= entry_price - stop_atr * volatility[signal_index]
            trail_exit = trail_active and closes[signal_index] < mean[signal_index]
            if stop_hit or trail_exit:
                price = _execution_price(opens[execution_index], tick_size, slippage_ticks, "sell")
                reason = "atr_stop" if stop_hit else "middle_band_trail"
                cash, quantity, fee, gross = _sell(cash, quantity, price, fee_rate)
                events.append(
                    _event(
                        "EXIT",
                        signal_index,
                        execution_index,
                        reason,
                        closes[signal_index],
                        price,
                        gross,
                        fee,
                        cash,
                        quantity,
                    )
                )
                entry_price = None
                trail_active = False
    return _trial(
        config.candidate_id, "", opens, closes[-1], cash, quantity, events, events_path
    ), events


def _event(
    event_type: str,
    signal_index: int,
    execution_index: int,
    reason: str,
    signal_close: Decimal,
    execution_price: Decimal,
    gross: Decimal,
    fee: Decimal,
    cash: Decimal,
    quantity: Decimal,
) -> ReplayEvent:
    return ReplayEvent(
        event_type=event_type,
        signal_index=signal_index,
        execution_index=execution_index,
        reason=reason,
        signal_close=str(signal_close),
        execution_price=str(execution_price),
        gross_notional=str(gross),
        fee_paid=str(fee),
        cash_after=str(cash),
        quantity_after=str(quantity),
        equity_after=str(_equity(cash, quantity, execution_price)),
    )


def _trial(
    candidate_id: str,
    dataset: str,
    opens: list[Decimal],
    final_mark: Decimal,
    cash: Decimal,
    quantity: Decimal,
    events: list[ReplayEvent],
    events_path: Path | None,
) -> ReplayTrial:
    if events_path is not None:
        events_path.write_text(
            "".join(json.dumps(asdict(event), sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
    final_equity = _equity(cash, quantity, final_mark)
    return ReplayTrial(
        candidate_id=candidate_id,
        dataset=dataset,
        bars=len(opens),
        status="COMPLETED",
        total_return=str(final_equity / INITIAL_CASH - Decimal("1")),
        final_equity=str(final_equity),
        event_count=len(events),
        entries=sum(1 for event in events if event.event_type == "ENTRY"),
        exits=sum(1 for event in events if event.event_type == "EXIT"),
        open_position_at_end=quantity > 0,
        events_path=str(events_path.relative_to(ROOT)) if events_path else "",
    )


def configs() -> tuple[StrategyConfig, ...]:
    return (
        StrategyConfig(
            candidate_id="TVPINE-RAGINGPORRA-RSI-MEAN-REVERSION",
            strategy_family="rsi_mean_reversion",
            source_url="https://www.tradingview.com/script/Hb8KwPmd-RSI-Mean-Reversion-Strategy/",
            rule_capture_status="PUBLIC_PAGE_RULES_SUFFICIENT_FOR_PROSE_REPLAY",
            source_code_status="OPEN_SOURCE_PAGE_OBSERVED_SOURCE_BODY_NOT_CAPTURED",
            strategy_tester_status="SUMMARY_FIELDS_PARTIAL_NOT_PLATFORM_EXPORT",
            notes=(
                "Page summary states RSI<=30 long entry, RSI>=70 exit, 100% equity, "
                "0.1% commission, 1 tick slippage, optional 2% stop.",
                "Local replay uses close signal and next-open execution; this is a "
                "prose-derived hypothesis, not exact Pine parity.",
            ),
            parameters={
                "rsi_window": "14",
                "entry_rsi_lte": "30",
                "exit_rsi_gte": "70",
                "position_fraction": "1.0",
                "commission_rate": "0.001",
                "slippage_ticks": "1",
                "tick_size": "0.01",
                "stop_loss_pct": "0.02",
            },
            source_evidence_refs=("tradingview:Hb8KwPmd:lines14-36",),
        ),
        StrategyConfig(
            candidate_id="TVPINE-SKYREXIO-BB-ENHANCED",
            strategy_family="bb_atr_ema",
            source_url="https://www.tradingview.com/script/V4B5nKIx-Bollinger-Bands-Enhanced-Strategy/",
            rule_capture_status="PUBLIC_PAGE_RULES_SUFFICIENT_FOR_PROSE_REPLAY_WITH_AMBIGUITIES",
            source_code_status="OPEN_SOURCE_PAGE_OBSERVED_SOURCE_BODY_NOT_CAPTURED",
            strategy_tester_status="PAGE_BACKTEST_SUMMARY_CAPTURED_NOT_PLATFORM_EXPORT",
            notes=(
                "Page summary gives BB(20,2), EMA trend filter, ATR stop/trailing "
                "activation, 0.1% commission, 5 ticks slippage, 10000 USDT "
                "capital, 30% position.",
                "Page text mentions both 200 EMA and 100 EMA; local replay chooses "
                "200 EMA from the methodology section and records this ambiguity.",
                "TradingView-reported 4h BTC/USDT result is external comparison evidence only.",
            ),
            parameters={
                "bb_window": "20",
                "bb_stddev_mult": "2",
                "ema_window": "200",
                "atr_window": "14",
                "stop_loss_atr_mult": "1.75",
                "trail_activation_atr_mult": "2.25",
                "position_fraction": "0.30",
                "commission_rate": "0.001",
                "slippage_ticks": "5",
                "tick_size": "0.01",
            },
            source_evidence_refs=("tradingview:V4B5nKIx:lines33-68",),
        ),
    )


def build_hashes(config_list: tuple[StrategyConfig, ...]) -> dict[str, str]:
    return {
        **{f"dataset_{name}": sha256(path) for name, path in DATASETS.items()},
        "frozen_manifest": sha256(FROZEN_MANIFEST),
        "quality_report": sha256(QUALITY_REPORT),
        "selected_candidates": sha256(SELECTED),
        "runner": sha256(Path(__file__)),
        "configs": canonical_hash([asdict(config) for config in config_list]),
    }


def run_replay() -> dict[str, Any]:
    config_list = configs()
    hashes = build_hashes(config_list)
    replay_id = "TVPINE-" + canonical_hash(hashes)[:32]
    out = OUTPUT_ROOT / replay_id
    result_path = out / "replay_run.json"
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["reused"] = True
        return result
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(tz=UTC).isoformat()
    trials: list[ReplayTrial] = []
    for config in config_list:
        simulator = simulate_rsi if config.strategy_family == "rsi_mean_reversion" else simulate_bb
        for dataset_name, dataset_path in DATASETS.items():
            candles = load_candles(dataset_path)
            events_path = out / f"{config.candidate_id}_{dataset_name}_events.jsonl"
            trial, _ = simulator(candles, config, events_path=events_path)
            trials.append(
                ReplayTrial(
                    **{
                        **asdict(trial),
                        "dataset": dataset_name,
                        "events_path": str(events_path.relative_to(ROOT)),
                    }
                )
            )
    scorecard = {
        "schema": "tios-tradingview-public-strategy-replay-scorecard-v1",
        "status": "EVIDENCE_RETAINED_NOT_VALIDATED",
        "validation_state": "UNVALIDATED",
        "approval_status": "NOT_ELIGIBLE",
        "promotion_eligible": False,
        "execution_authority": "NONE",
        "venue_connection": "NONE",
        "paper_demo_live": "DISABLED",
        "winner_selected": False,
        "selected_candidates_artifact": str(SELECTED.relative_to(ROOT)),
        "candidate_configs": [asdict(config) for config in config_list],
        "trials": [asdict(trial) for trial in trials],
        "best_total_return": str(max(Decimal(trial.total_return) for trial in trials)),
        "blockers": [
            "prose-derived replay; exact Pine source body not captured",
            "TradingView Strategy Tester platform export not captured for every candidate",
            "no cross-engine reproduction exists for these TradingView candidates",
            "no temporal/G10 validation package exists for these TradingView candidates",
            "candidate remains unvalidated and not promotion eligible",
        ],
        "prohibited": [
            "credential_request",
            "account_connection",
            "protected_or_invite_only_code_copying",
            "alert_subscription",
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
        "schema": "tios-tradingview-public-strategy-replay-manifest-v1",
        "replay_id": replay_id,
        "status": "COMPLETED",
        "mode": "OFFLINE_RESEARCH_ONLY",
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
        "schema": "tios-tradingview-public-strategy-replay-run-v1",
        "reused": False,
        "counts": {
            "candidates": len(config_list),
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
