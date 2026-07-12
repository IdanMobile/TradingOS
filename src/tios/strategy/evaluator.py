"""Deterministic canonical rule and signal evaluation over retained market bars."""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal

from tios.trading_domain import (
    CreatorType,
    MarketBar,
    Provenance,
    RunId,
    Side,
    SignalEvent,
    SignalId,
    StrategyVersionId,
)

from .spec import CanonicalStrategySpec, Comparison, Indicator, RuleTree


class StrategyEvaluationError(ValueError):
    """Canonical strategy semantics are missing or internally inconsistent."""


def evaluate_comparison(comparison: Comparison, context: dict[str, Decimal]) -> bool:
    def resolve(token: str) -> Decimal:
        try:
            return Decimal(token)
        except Exception as error:
            if token not in context:
                raise StrategyEvaluationError(f"missing rule operand {token!r}") from error
            return context[token]

    left, right = resolve(comparison.left), resolve(comparison.right)
    return {
        "<": left < right,
        "<=": left <= right,
        ">": left > right,
        ">=": left >= right,
        "==": left == right,
        "!=": left != right,
    }[comparison.op]


def evaluate_rule_tree(tree: RuleTree | None, context: dict[str, Decimal]) -> bool:
    if tree is None:
        return False
    values = [evaluate_comparison(item, context) for item in tree.comparisons]
    values.extend(evaluate_rule_tree(item, context) for item in tree.subtrees)
    return all(values) if tree.kind == "all" else any(values)


def evaluate_strategy_signals(
    *,
    spec: CanonicalStrategySpec,
    bars: tuple[MarketBar, ...],
    strategy_version_ref: StrategyVersionId,
    run_ref: RunId,
    created_at: datetime,
    creator_type: CreatorType,
    provenance: Provenance,
) -> tuple[SignalEvent, ...]:
    """Emit deduplicated long-only state transitions; signals never become orders."""
    if not bars:
        return ()
    market = bars[0].market
    if any(bar.market != market for bar in bars):
        raise StrategyEvaluationError("strategy bars must share one market context")
    if any(
        previous.close_time >= current.close_time
        for previous, current in zip(bars, bars[1:], strict=False)
    ):
        raise StrategyEvaluationError("strategy bars must be strictly time ordered")
    contexts = _indicator_contexts(spec, bars)
    signals: list[SignalEvent] = []
    is_long = False
    for bar, context in zip(bars, contexts, strict=True):
        if context is None:
            continue
        side: Side | None = None
        rationale = ""
        if spec.always_in_market and not is_long:
            side, rationale, is_long = Side.BUY, "ALWAYS_IN_MARKET", True
        elif is_long and evaluate_rule_tree(spec.exit_long, context):
            side, rationale, is_long = Side.SELL, "EXIT_LONG", False
        elif not is_long and evaluate_rule_tree(spec.entry_long, context):
            side, rationale, is_long = Side.BUY, "ENTRY_LONG", True
        if side is None:
            continue
        digest = hashlib.sha256(
            f"{strategy_version_ref}|{run_ref}|{bar.close_time.isoformat()}|{side}".encode()
        ).hexdigest()[:24]
        signals.append(
            SignalEvent(
                signal_id=SignalId(f"SIG-{digest}"),
                strategy_version_ref=strategy_version_ref,
                run_ref=run_ref,
                instrument=market.instrument,
                timeframe=market.timeframe,
                observed_at=bar.close_time,
                side=side,
                rationale_code=rationale,
                created_at=created_at,
                creator_type=creator_type,
                provenance=provenance,
            )
        )
    return tuple(signals)


def _indicator_contexts(
    spec: CanonicalStrategySpec, bars: tuple[MarketBar, ...]
) -> list[dict[str, Decimal] | None]:
    contexts: list[dict[str, Decimal] | None] = [
        {
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]
    for indicator in spec.indicators:
        values = _indicator_values(indicator, bars)
        for index, outputs in enumerate(values):
            if outputs is None:
                contexts[index] = None
            else:
                context = contexts[index]
                if context is not None:
                    context.update(outputs)
    return contexts


def _indicator_values(
    indicator: Indicator, bars: tuple[MarketBar, ...]
) -> list[dict[str, Decimal] | None]:
    name = indicator.name
    window = int(indicator.parameters.get("window", 1))
    if window <= 0:
        raise StrategyEvaluationError(f"indicator {name!r} requires a positive window")
    if name == "donchian_channel":
        return _donchian(indicator, bars, window)
    if name == "supertrend":
        return _supertrend(indicator, bars, window)
    source_name = str(indicator.parameters.get("source", "close"))
    if source_name not in {"open", "high", "low", "close", "volume"}:
        raise StrategyEvaluationError(f"indicator {name!r} has unsupported source {source_name!r}")
    source = [getattr(bar, source_name) for bar in bars]
    if name in {"sma_fast", "sma_slow"}:
        return _single_output(indicator, _sma(source, window))
    if name in {"ema_short", "ema_long"}:
        return _single_output(indicator, _ema(source, window))
    if name == "bollinger_bands":
        deviations = Decimal(str(indicator.parameters["std"]))
        return _bollinger(indicator, source, window, deviations)
    if name == "rsi":
        return _single_output(indicator, _wilder_rsi(source, window))
    if name == "rate_of_change":
        return _single_output(indicator, _rate_of_change(source, window))
    if name == "reference_price":
        return _single_output(indicator, source)
    raise StrategyEvaluationError(f"unsupported canonical indicator {name!r}")


def _single_output(
    indicator: Indicator, values: list[Decimal | None] | list[Decimal]
) -> list[dict[str, Decimal] | None]:
    if len(indicator.outputs) != 1:
        raise StrategyEvaluationError(f"indicator {indicator.name!r} must declare one output")
    output = indicator.outputs[0]
    return [None if value is None else {output: value} for value in values]


def _sma(values: list[Decimal], window: int) -> list[Decimal | None]:
    return [
        None
        if index + 1 < window
        else sum(values[index + 1 - window : index + 1], Decimal(0)) / Decimal(window)
        for index in range(len(values))
    ]


def _ema(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < window:
        return result
    current = sum(values[:window], Decimal(0)) / Decimal(window)
    result[window - 1] = current
    alpha = Decimal(2) / Decimal(window + 1)
    for index in range(window, len(values)):
        current = (values[index] - current) * alpha + current
        result[index] = current
    return result


def _bollinger(
    indicator: Indicator, values: list[Decimal], window: int, deviations: Decimal
) -> list[dict[str, Decimal] | None]:
    if tuple(indicator.outputs) != ("bb_lower", "bb_mid", "bb_upper"):
        raise StrategyEvaluationError("bollinger_bands outputs must be lower, mid, upper")
    result: list[dict[str, Decimal] | None] = [None] * len(values)
    for index in range(window - 1, len(values)):
        sample = values[index + 1 - window : index + 1]
        middle = sum(sample, Decimal(0)) / Decimal(window)
        variance = sum(((value - middle) ** 2 for value in sample), Decimal(0)) / Decimal(window)
        deviation = variance.sqrt()
        result[index] = {
            "bb_lower": middle - deviations * deviation,
            "bb_mid": middle,
            "bb_upper": middle + deviations * deviation,
        }
    return result


def _wilder_rsi(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= window:
        return result
    gains = [max(values[index] - values[index - 1], Decimal(0)) for index in range(1, window + 1)]
    losses = [max(values[index - 1] - values[index], Decimal(0)) for index in range(1, window + 1)]
    average_gain = sum(gains, Decimal(0)) / Decimal(window)
    average_loss = sum(losses, Decimal(0)) / Decimal(window)
    result[window] = _rsi(average_gain, average_loss)
    for index in range(window + 1, len(values)):
        delta = values[index] - values[index - 1]
        average_gain = (average_gain * Decimal(window - 1) + max(delta, Decimal(0))) / Decimal(
            window
        )
        average_loss = (average_loss * Decimal(window - 1) + max(-delta, Decimal(0))) / Decimal(
            window
        )
        result[index] = _rsi(average_gain, average_loss)
    return result


def _rsi(average_gain: Decimal, average_loss: Decimal) -> Decimal:
    if average_loss == 0:
        return Decimal(100)
    return Decimal(100) - Decimal(100) / (Decimal(1) + average_gain / average_loss)


def _rate_of_change(values: list[Decimal], window: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    for index in range(window, len(values)):
        if values[index - window] == 0:
            raise StrategyEvaluationError("rate_of_change source cannot contain a zero base")
        result[index] = values[index] / values[index - window] - 1
    return result


def _donchian(
    indicator: Indicator, bars: tuple[MarketBar, ...], window: int
) -> list[dict[str, Decimal] | None]:
    if tuple(indicator.outputs) != ("donchian_upper", "donchian_lower"):
        raise StrategyEvaluationError("donchian_channel outputs must be upper and lower")
    if indicator.parameters.get("include_current_bar") is not False:
        raise StrategyEvaluationError("donchian_channel requires explicit prior-bar semantics")
    result: list[dict[str, Decimal] | None] = [None] * len(bars)
    for index in range(window, len(bars)):
        prior = bars[index - window : index]
        result[index] = {
            "donchian_upper": max(bar.high for bar in prior),
            "donchian_lower": min(bar.low for bar in prior),
        }
    return result


def _supertrend(
    indicator: Indicator, bars: tuple[MarketBar, ...], window: int
) -> list[dict[str, Decimal] | None]:
    if len(indicator.outputs) != 1:
        raise StrategyEvaluationError("supertrend must declare one output")
    multiplier = Decimal(str(indicator.parameters["multiplier"]))
    mode = str(indicator.parameters.get("signal_mode", "direction_level"))
    convention = str(indicator.parameters.get("direction_convention", "pandas_ta"))
    if (
        multiplier <= 0
        or mode not in {"direction_level", "proximity_level"}
        or convention not in {"pandas_ta", "tradingview"}
    ):
        raise StrategyEvaluationError("supertrend multiplier or signal_mode is invalid")
    threshold = Decimal(str(indicator.parameters.get("percentage_threshold", "0")))
    if mode == "proximity_level" and not 0 < threshold < 1:
        raise StrategyEvaluationError("proximity supertrend requires a fractional threshold")
    true_ranges = []
    for index, bar in enumerate(bars):
        previous_close = bars[index - 1].close if index else bar.close
        true_ranges.append(
            max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        )
    atr: list[Decimal | None] = [None] * len(bars)
    if len(bars) < window:
        return [None] * len(bars)
    current_atr = sum(true_ranges[:window], Decimal(0)) / Decimal(window)
    atr[window - 1] = current_atr
    for index in range(window, len(bars)):
        current_atr = (current_atr * Decimal(window - 1) + true_ranges[index]) / Decimal(window)
        atr[index] = current_atr
    upper: list[Decimal | None] = [None] * len(bars)
    lower: list[Decimal | None] = [None] * len(bars)
    line: list[Decimal | None] = [None] * len(bars)
    direction: list[int | None] = [None] * len(bars)
    for index in range(window - 1, len(bars)):
        current = atr[index]
        assert current is not None
        midpoint = (bars[index].high + bars[index].low) / 2
        basic_upper = midpoint + multiplier * current
        basic_lower = midpoint - multiplier * current
        if index == window - 1:
            upper[index], lower[index] = basic_upper, basic_lower
            direction[index] = -1
            line[index] = basic_upper
        else:
            previous_upper, previous_lower = upper[index - 1], lower[index - 1]
            previous_line = line[index - 1]
            assert previous_upper is not None and previous_lower is not None
            assert previous_line is not None
            upper[index] = (
                basic_upper
                if basic_upper < previous_upper or bars[index - 1].close > previous_upper
                else previous_upper
            )
            lower[index] = (
                basic_lower
                if basic_lower > previous_lower or bars[index - 1].close < previous_lower
                else previous_lower
            )
            current_upper, current_lower = upper[index], lower[index]
            assert current_upper is not None and current_lower is not None
            if previous_line == previous_upper:
                direction[index] = 1 if bars[index].close > current_upper else -1
            else:
                direction[index] = -1 if bars[index].close < current_lower else 1
            line[index] = current_lower if direction[index] == 1 else current_upper
    output = indicator.outputs[0]
    result: list[dict[str, Decimal] | None] = [None] * len(bars)
    for index in range(window - 1, len(bars)):
        current_line, current_direction = line[index], direction[index]
        assert current_line is not None and current_direction is not None
        value = Decimal(-current_direction if convention == "tradingview" else current_direction)
        if mode == "proximity_level":
            distance = abs(bars[index].close - current_line) / bars[index].close
            if distance >= threshold:
                value = Decimal(0)
        result[index] = {output: value}
    return result
