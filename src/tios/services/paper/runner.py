"""Gated orchestration boundary for public-data synthetic paper observation."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import time as datetime_time
from decimal import Decimal
from zoneinfo import ZoneInfo

from tios.strategy.evaluator import StrategyEvaluationError, evaluate_strategy_signals
from tios.trading_domain import (
    ApprovalId,
    ContractError,
    CreatorType,
    DatasetId,
    DomainRef,
    InstrumentId,
    KillSwitchMode,
    Market,
    MarketBar,
    MarketName,
    MarketQuote,
    Money,
    OrderIntent,
    OrderType,
    PaperFeeModel,
    PaperFillPriceSource,
    PortfolioId,
    Provenance,
    RiskDecision,
    RiskId,
    RiskOutcome,
    RunId,
    Side,
    SignalEvent,
    SignalId,
    Stage,
    StageGateStatus,
    SyntheticFillCalculation,
    SyntheticMarketConditionPolicy,
    SyntheticPaperFillPolicy,
    SyntheticPortfolioRiskPolicy,
    SyntheticRiskInputs,
    SyntheticRuntimeRiskPolicy,
    SyntheticStrategyBudgetPolicy,
    VenueFamily,
    calculate_synthetic_fill,
    evaluate_synthetic_risk,
)

from .market import BinanceBookTicker, BinanceDataError, BinancePublicClient
from .models import (
    AttentionItem,
    AttentionSeverity,
    CockpitSnapshot,
    EquityPoint,
    FreshnessStatus,
    PaperActivity,
    PaperBotPhase,
    PaperBotSnapshot,
    PaperMode,
    PaperPositionSnapshot,
    PaperRiskPolicy,
    PaperRuntimeConfig,
    PaperRuntimeError,
    PortfolioPerformance,
    SignalWatchSnapshot,
    SignalWatchState,
    SourceFreshness,
    _decimal_identity,
)
from .store import (
    PaperEventType,
    PaperEventWrite,
    PaperStore,
    PaperStoreProjection,
    PortfolioPointWrite,
    StoredPaperEvent,
    StoredPortfolioPoint,
)


class PaperGateError(PaperRuntimeError):
    """A bot attempted to start without complete human and validation approval."""


DEFAULT_POLICY = PaperRiskPolicy()


def _validate_activation(config: PaperRuntimeConfig, policy: PaperRiskPolicy) -> None:
    config.assert_immutable()
    gate = config.gate
    if gate is None:
        raise PaperGateError("paper activation requires an approved S3 stage gate")
    if gate.stage is not Stage.S3_PAPER_DEMO or gate.status is not StageGateStatus.APPROVED:
        raise PaperGateError("paper activation requires an APPROVED S3 stage gate")
    if gate.subject_ref != DomainRef(str(config.strategy_version_ref)):
        raise PaperGateError("paper gate does not match the strategy version context")
    if (
        config.validation_status != "APPROVED"
        or config.validation_approval_ref is None
        or not config.validation_evidence_refs
    ):
        raise PaperGateError("strategy context lacks retained validation approval evidence")
    if config.allocated_capital > policy.max_position_notional:
        raise PaperGateError("bot allocation exceeds the conservative position limit")


class PaperRunner:
    """Runs closed-bar observation; no repository config currently activates it."""

    def __init__(
        self,
        store: PaperStore,
        client: BinancePublicClient,
        *,
        policy: PaperRiskPolicy = DEFAULT_POLICY,
        clock: Callable[[], datetime] = lambda: datetime.now(tz=UTC),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = store
        self.client = client
        self.policy = policy
        self._clock = clock
        self._sleep = sleep
        self._configs: tuple[PaperRuntimeConfig, ...] = ()

    def activate(self, configs: tuple[PaperRuntimeConfig, ...]) -> None:
        if not configs:
            raise PaperGateError("no strategy is approved for paper simulation")
        for config in configs:
            _validate_activation(config, self.policy)
        if len({config.bot_id for config in configs}) != len(configs):
            raise PaperGateError("paper bot identities must be unique")
        if len({config.activation_key for config in configs}) != len(configs):
            raise PaperGateError("one immutable config is allowed per paper lane")
        with self.store.runner_lease():
            now = self._now()
            projection = self.store.current_projection()
            started = tuple(
                event.payload
                for event in projection.events
                if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
            )
            if bool(projection.portfolio_points) != bool(started):
                raise PaperGateError(
                    "paper portfolio state exists without retained activation policy"
                )
            retained_policy = _activation_payload(configs[0], self.policy)
            if any(
                payload.get("policy_sha256") != retained_policy["policy_sha256"]
                or payload.get("risk_policy") != retained_policy["risk_policy"]
                for payload in started
            ):
                raise PaperGateError(
                    "retained paper store refuses shared portfolio policy substitution"
                )
            if started and projection.portfolio_points:
                initial = projection.portfolio_points[0]
                if (
                    initial.equity != self.policy.starting_capital
                    or initial.cash != self.policy.starting_capital
                    or initial.exposure != 0
                ):
                    raise PaperGateError(
                        "retained paper store refuses shared portfolio initial capital drift"
                    )
            pending: list[tuple[PaperRuntimeConfig, dict[str, object]]] = []
            for config in configs:
                retained = _activation_payload(config, self.policy)
                lane_starts = tuple(
                    payload
                    for payload in started
                    if (
                        payload.get("strategy_version_ref"),
                        payload.get("symbol"),
                        payload.get("timeframe"),
                    )
                    == config.activation_key
                )
                if any(payload != retained for payload in lane_starts):
                    raise PaperGateError(
                        "retained paper activation refuses config or spec substitution"
                    )
                if not lane_starts:
                    pending.append((config, retained))
            if pending:
                self.store.commit_cycle(
                    tuple(
                        PaperEventWrite(
                            PaperEventType.BOT,
                            config.bot_id,
                            retained,
                            f"bot-start:{config.bot_id}",
                            now,
                        )
                        for config, retained in pending
                    ),
                    (
                        PortfolioPointWrite(
                            "paper-portfolio-initial-v1",
                            now,
                            self.policy.starting_capital,
                            self.policy.starting_capital,
                            Decimal(0),
                            Decimal(0),
                            Decimal(0),
                            Decimal(0),
                        ),
                    )
                    if not projection.portfolio_points
                    else (),
                    recorded_at=now,
                )
        self._configs = configs

    def run_once(self) -> CockpitSnapshot:
        if not self._configs:
            raise PaperGateError("no strategy is approved for paper simulation")
        snapshot_at = self._now()
        with self.store.runner_lease():
            for config in self._configs:
                _validate_activation(config, self.policy)
                projection = self.store.current_projection()
                source = "BINANCE_BOOK_TICKER"
                try:
                    quote = self.client.fetch_book_ticker(config.symbol)
                    cycle_at = max(self._now(), quote.observed_at)
                    snapshot_at = max(snapshot_at, cycle_at)
                    if (
                        cycle_at - quote.observed_at
                    ).total_seconds() > self.policy.quote_max_age_seconds:
                        raise BinanceDataError("book ticker is stale")
                    projection = self._record_health(
                        config, quote, source, cycle_at, projection, mark=True
                    )
                    source = "RISK_ENGINE"
                    projection = self._enforce_risk_kill(config, quote, cycle_at, projection)
                    source = "BINANCE_KLINES"
                    klines = self.client.fetch_klines(
                        config.symbol, config.timeframe, limit=_warmup(config)
                    )
                    cycle_at = max(self._now(), quote.observed_at)
                    snapshot_at = max(snapshot_at, cycle_at)
                    closed = tuple(kline for kline in klines if kline.is_closed(cycle_at))
                    if not closed:
                        raise BinanceDataError("no closed bars are available")
                    if any(
                        current.open_time - previous.open_time
                        != timedelta(seconds=config.timeframe.seconds)
                        for previous, current in zip(closed, closed[1:], strict=False)
                    ):
                        raise BinanceDataError("closed kline history is not contiguous")
                    latest = closed[-1].close_time
                    if (cycle_at - latest).total_seconds() > config.timeframe.seconds:
                        raise BinanceDataError("latest closed bar is stale")
                    projection = self._record_health(
                        config, quote, source, cycle_at, projection, mark=False
                    )
                    evaluated = _last_evaluated(projection, config.bot_id)
                    if evaluated is None or latest > evaluated:
                        source = "STRATEGY_EVALUATOR"
                        projection = self._commit_closed_bar(
                            config,
                            closed,
                            quote,
                            latest,
                            cycle_at,
                            projection,
                            evaluated=evaluated,
                        )
                    projection = self._retain_minute(cycle_at, projection)
                except (
                    BinanceDataError,
                    ContractError,
                    PaperRuntimeError,
                    StrategyEvaluationError,
                ) as error:
                    self._record_incident(
                        config,
                        source,
                        error,
                        max(snapshot_at, self._now()),
                        projection,
                    )
        return self.snapshot(now=snapshot_at)

    def _record_health(
        self,
        config: PaperRuntimeConfig,
        quote: BinanceBookTicker,
        source: str,
        now: datetime,
        projection: PaperStoreProjection,
        *,
        mark: bool,
    ) -> PaperStoreProjection:
        events: list[PaperEventWrite] = []
        interval = 5 if source == "BINANCE_BOOK_TICKER" else self.policy.heartbeat_interval_seconds
        bucket = int(now.timestamp()) // interval
        quote_identity = hashlib.sha256(
            f"{quote.observed_at.isoformat()}|{_decimal_identity(quote.bid_price)}".encode()
        ).hexdigest()[:8]
        suffix = f":{quote_identity}" if source == "BINANCE_BOOK_TICKER" else ""
        key = f"heartbeat:{source.lower()}:{config.bot_id}:{bucket}{suffix}"
        if key not in {event.idempotency_key for event in projection.events}:
            events.append(
                PaperEventWrite(
                    PaperEventType.HEARTBEAT,
                    config.bot_id,
                    {"status": "OK", "source": source, "mark_price": str(quote.bid_price)},
                    key,
                    now,
                )
            )
        points: tuple[PortfolioPointWrite, ...] = ()
        positions = _position_state(projection)
        position = positions.get(config.bot_id)
        if mark and position is not None and position.quantity > 0:
            mark_bucket = int(now.timestamp()) // 5
            point_key = f"portfolio-mark:{config.bot_id}:{mark_bucket}:{quote_identity}"
            if point_key not in {point.idempotency_key for point in projection.portfolio_points}:
                marks = _latest_marks(projection)
                marks[config.bot_id] = quote.bid_price
                ledger = _marked_ledger(projection, marks)
                points = (
                    PortfolioPointWrite(
                        point_key,
                        now,
                        ledger["equity"],
                        ledger["cash"],
                        ledger["exposure"],
                        ledger["realized"],
                        ledger["unrealized"],
                        ledger["fees"],
                    ),
                )
        if events or points:
            self.store.commit_cycle(tuple(events), points, recorded_at=now)
            return self.store.refresh_projection(projection)
        return projection

    def _record_incident(
        self,
        config: PaperRuntimeConfig,
        source: str,
        error: Exception,
        now: datetime,
        projection: PaperStoreProjection,
    ) -> None:
        bucket = int(now.timestamp()) // self.policy.stale_after_seconds
        summary = str(error)
        digest = hashlib.sha256(summary.encode()).hexdigest()[:8]
        success_source = {
            "BINANCE_BOOK_TICKER": "BINANCE_BOOK_TICKER",
            "BINANCE_KLINES": "BINANCE_KLINES",
        }.get(source)
        success = max(
            (
                event.sequence
                for event in projection.events
                if event.subject_id == config.bot_id
                and (
                    event.event_type is PaperEventType.HEARTBEAT
                    and event.payload.get("source") == success_source
                    or event.event_type is PaperEventType.BOT
                    and event.payload.get("kind") == "EVALUATED"
                    and source == "STRATEGY_EVALUATOR"
                )
            ),
            default=0,
        )
        key = f"incident:{source.lower()}:{config.bot_id}:{success}:{bucket}:{digest}"
        self.store.append_event(
            PaperEventType.INCIDENT,
            config.bot_id,
            {"summary": summary, "source": source},
            idempotency_key=key,
            occurred_at=datetime.fromtimestamp(bucket * self.policy.stale_after_seconds, tz=UTC),
        )

    def _commit_closed_bar(
        self,
        config: PaperRuntimeConfig,
        closed: tuple[object, ...],
        quote: BinanceBookTicker,
        latest: datetime,
        now: datetime,
        projection: PaperStoreProjection,
        *,
        evaluated: datetime | None,
    ) -> PaperStoreProjection:
        position = _position_state(projection).get(config.bot_id)
        held = position.quantity if position is not None else Decimal(0)
        history = evaluate_strategy_signals(
            spec=config.spec,
            bars=tuple(_bar(config, kline, now) for kline in closed),
            strategy_version_ref=config.strategy_version_ref,
            run_ref=_run_ref(config),
            created_at=now,
            creator_type=CreatorType.SYSTEM,
            provenance=_provenance(config),
            initial_held=held > 0,
        )
        latest_signals = tuple(signal for signal in history if signal.observed_at == latest)
        events: list[PaperEventWrite] = []
        points: list[PortfolioPointWrite] = []
        buy_fill = False
        if (
            evaluated is not None
            and (latest - evaluated).total_seconds() > config.timeframe.seconds
        ):
            events.append(
                PaperEventWrite(
                    PaperEventType.INCIDENT,
                    config.bot_id,
                    {
                        "summary": "One or more closed strategy bars were missed.",
                        "source": "STRATEGY_EVALUATOR",
                        "code": "MISSED_BARS",
                    },
                    f"missed-bars:{config.bot_id}:{int(evaluated.timestamp())}:{int(latest.timestamp())}",
                    latest,
                )
            )
        signal_writes = {str(signal.signal_id): signal for signal in latest_signals}
        desired = history[-1].side if history else None
        action = (
            Side.BUY
            if desired is Side.BUY and held == 0
            else Side.SELL
            if desired is Side.SELL and held > 0
            else None
        )
        signal = next((item for item in latest_signals if item.side is action), None)
        if action is not None and signal is None:
            signal = _state_signal(config, action, now, now, "STATE_RECONCILIATION")
            signal_writes[str(signal.signal_id)] = signal
        events.extend(_signal_write(config, item) for item in signal_writes.values())
        if signal is not None and not (signal.side is Side.BUY and projection.entries_paused):
            quantity = (
                config.allocated_capital
                / (quote.midpoint * (Decimal(1) + self.policy.slippage_bps / Decimal("10000")))
                if signal.side is Side.BUY
                else held
            )
            risk, risk_payload, fill = self._assess_fill(
                config, signal, quote, projection, quantity=quantity, now=now
            )
            events.append(
                PaperEventWrite(
                    PaperEventType.RISK,
                    config.bot_id,
                    risk_payload,
                    f"risk:{signal.signal_id}",
                    signal.observed_at,
                )
            )
            if risk is None or risk.decision is not RiskOutcome.BLOCK:
                assert fill is not None
                buy_fill = signal.side is Side.BUY
                marks = _latest_marks(projection)
                marks[config.bot_id] = quote.bid_price
                ledger, updated = _after_fill(
                    projection, config.bot_id, signal.side, fill, marks, now
                )
                events.append(_fill_write(config, signal, fill, ledger, updated, now))
                points.append(
                    PortfolioPointWrite(
                        f"portfolio-fill:{signal.signal_id}",
                        now,
                        ledger["equity"],
                        ledger["cash"],
                        ledger["exposure"],
                        ledger["realized"],
                        ledger["unrealized"],
                        ledger["fees"],
                    )
                )
        events.append(
            PaperEventWrite(
                PaperEventType.BOT,
                config.bot_id,
                {
                    "kind": "EVALUATED",
                    "last_evaluated_bar_at": latest,
                    "signal_count": len(signal_writes),
                },
                f"bot-evaluated:{config.bot_id}:{int(latest.timestamp())}",
                latest,
            )
        )
        self.store.commit_cycle(
            tuple(events),
            tuple(points),
            recorded_at=now,
            require_entries_unpaused=buy_fill,
        )
        return self.store.refresh_projection(projection)

    def _enforce_risk_kill(
        self,
        config: PaperRuntimeConfig,
        quote: BinanceBookTicker,
        now: datetime,
        projection: PaperStoreProjection,
    ) -> PaperStoreProjection:
        daily_loss, drawdown = _loss_and_drawdown(projection, now)
        breached = tuple(
            code
            for code, failed in (
                ("DAILY_LOSS", daily_loss > self.policy.max_daily_loss),
                ("DRAWDOWN", drawdown > self.policy.max_drawdown_fraction),
            )
            if failed
        )
        if not breached:
            return projection
        if not projection.entries_paused:
            self.store.set_entries_paused(
                True,
                actor="paper-risk-engine",
                idempotency_key=f"risk-pause:{projection.portfolio_points[-1].sequence}",
                occurred_at=now,
            )
            projection = self.store.refresh_projection(projection)
        prior_kill = next(
            (
                event
                for event in reversed(projection.events)
                if event.event_type is PaperEventType.INCIDENT
                and event.subject_id == config.bot_id
                and event.payload.get("source") == "RISK_ENGINE"
            ),
            None,
        )
        position = _position_state(projection).get(config.bot_id)
        events: list[PaperEventWrite] = []
        points: list[PortfolioPointWrite] = []
        if prior_kill is None:
            events.append(
                PaperEventWrite(
                    PaperEventType.INCIDENT,
                    config.bot_id,
                    {
                        "summary": f"Risk kill triggered: {', '.join(breached)}.",
                        "source": "RISK_ENGINE",
                        "code": "RISK_KILL",
                    },
                    f"risk-kill:{config.bot_id}:{projection.portfolio_points[-1].sequence}",
                    now,
                )
            )
        if position is not None and position.quantity > 0:
            signal = _state_signal(config, Side.SELL, now, now, "RISK_KILL")
            bid_quote = BinanceBookTicker(
                quote.symbol,
                quote.bid_price,
                quote.bid_quantity,
                quote.bid_price,
                quote.bid_quantity,
                quote.observed_at,
            )
            risk, risk_payload, fill = self._assess_fill(
                config,
                signal,
                bid_quote,
                projection,
                quantity=position.quantity,
                now=now,
            )
            assert risk is None and fill is not None
            marks = _latest_marks(projection)
            marks[config.bot_id] = quote.bid_price
            ledger, updated = _after_fill(projection, config.bot_id, Side.SELL, fill, marks, now)
            events.extend(
                (
                    _signal_write(config, signal),
                    PaperEventWrite(
                        PaperEventType.RISK,
                        config.bot_id,
                        risk_payload,
                        f"risk:{signal.signal_id}",
                        now,
                    ),
                    _fill_write(config, signal, fill, ledger, updated, now),
                )
            )
            points.append(
                PortfolioPointWrite(
                    f"portfolio-fill:{signal.signal_id}",
                    now,
                    ledger["equity"],
                    ledger["cash"],
                    ledger["exposure"],
                    ledger["realized"],
                    ledger["unrealized"],
                    ledger["fees"],
                )
            )
        if events or points:
            self.store.commit_cycle(tuple(events), tuple(points), recorded_at=now)
            return self.store.refresh_projection(projection)
        return projection

    def _retain_minute(
        self, now: datetime, projection: PaperStoreProjection
    ) -> PaperStoreProjection:
        minute = int(now.timestamp()) // 60
        key = f"portfolio-minute:{minute}"
        if key in {point.idempotency_key for point in projection.portfolio_points}:
            return projection
        latest = projection.portfolio_points[-1]
        self.store.append_portfolio_point(
            idempotency_key=key,
            observed_at=now,
            equity=latest.equity,
            cash=latest.cash,
            exposure=latest.exposure,
            realized_pnl=latest.realized_pnl,
            unrealized_pnl=latest.unrealized_pnl,
            fees=latest.fees,
            external_cash_flow=Decimal(0),
        )
        return self.store.refresh_projection(projection)

    def run_forever(self, *, stopped: Callable[[], bool]) -> None:
        if not self._configs:
            raise PaperGateError("no strategy is approved for paper simulation")
        while not stopped():
            self.run_once()
            self._sleep(5)

    def calculate_gated_fill(
        self,
        config: PaperRuntimeConfig,
        signal: SignalEvent,
        quote: BinanceBookTicker,
        *,
        quantity: Decimal,
        as_of: datetime | None = None,
    ) -> SyntheticFillCalculation:
        """Deterministic injected-client fill boundary; it never submits an order."""
        now = as_of or self._now()
        risk, _, fill = self._assess_fill(
            config,
            signal,
            quote,
            self.store.current_projection(),
            quantity=quantity,
            now=now,
        )
        if risk is not None and risk.decision is RiskOutcome.BLOCK:
            raise PaperRuntimeError("independent synthetic risk evaluation blocked the fill")
        assert fill is not None
        return fill

    def _assess_fill(
        self,
        config: PaperRuntimeConfig,
        signal: SignalEvent,
        quote: BinanceBookTicker,
        projection: PaperStoreProjection,
        *,
        quantity: Decimal,
        now: datetime,
    ) -> tuple[RiskDecision | None, dict[str, object], SyntheticFillCalculation | None]:
        """Evaluate a fill without persistence so its cycle can commit atomically."""
        _validate_activation(config, self.policy)
        if (
            quote.symbol != config.symbol
            or signal.strategy_version_ref != config.strategy_version_ref
        ):
            raise PaperRuntimeError("fill inputs do not match the approved bot context")
        quote_age = (now - quote.observed_at).total_seconds()
        signal_age = (now - signal.observed_at).total_seconds()
        if not 0 <= quote_age <= self.policy.quote_max_age_seconds:
            raise PaperRuntimeError("quote is stale; synthetic fill rejected")
        if not 0 <= signal_age <= self.policy.max_fill_latency_seconds:
            raise PaperRuntimeError("signal fill latency exceeded; synthetic fill rejected")
        if quantity <= 0 or not quantity.is_finite():
            raise PaperRuntimeError("synthetic fill quantity must be finite and positive")
        if signal.side is Side.BUY and projection.entries_paused:
            raise PaperRuntimeError("new paper entries are paused")
        latest_point = projection.portfolio_points[-1]
        current_exposure = latest_point.exposure
        daily_loss, drawdown_fraction = _loss_and_drawdown(projection, now)
        positions = _position_state(projection)
        bot_position = positions.get(config.bot_id)
        if signal.side is Side.BUY and bot_position is not None and bot_position.quantity > 0:
            raise PaperRuntimeError("one open position is allowed per paper bot")
        open_positions = sum(position.quantity > 0 for position in positions.values())
        market = _market(config)
        market_quote = MarketQuote(
            market,
            quote.observed_at,
            quote.bid_price,
            quote.bid_quantity,
            quote.ask_price,
            quote.ask_quantity,
            now,
            CreatorType.SYSTEM,
            _provenance(config),
        )
        proposed = (
            quote.midpoint
            * (
                Decimal(1)
                + (
                    self.policy.slippage_bps / Decimal("10000")
                    if signal.side is Side.BUY
                    else -self.policy.slippage_bps / Decimal("10000")
                )
            )
            * quantity
        )
        resulting_exposure = (
            current_exposure + proposed
            if signal.side is Side.BUY
            else max(Decimal(0), current_exposure - proposed)
        )
        risk = (
            _risk(
                config,
                self.policy,
                proposed,
                resulting_exposure - proposed,
                daily_loss,
                drawdown_fraction,
                open_positions + 1,
                int(quote_age),
                quote.spread_bps,
                now,
            )
            if signal.side is Side.BUY
            else None
        )
        risk_payload: dict[str, object] = {
            "signal_id": str(signal.signal_id),
            "decision": risk.decision.value if risk is not None else "PASS",
            "reason": _risk_reason(risk),
            "proposed_notional": str(proposed),
            "capital_at_risk": str(resulting_exposure),
            "daily_loss": str(daily_loss),
            "drawdown_fraction": str(drawdown_fraction),
            "open_positions": open_positions + (1 if signal.side is Side.BUY else 0),
        }
        if risk is not None and risk.decision is RiskOutcome.BLOCK:
            return risk, risk_payload, None
        intent = OrderIntent(
            signal.signal_id,
            signal.run_ref,
            signal.instrument,
            signal.side,
            OrderType.MARKET,
            quantity,
            None,
            None,
            None,
            now,
            CreatorType.SYSTEM,
            _provenance(config),
        )
        fill_policy = SyntheticPaperFillPolicy(
            ApprovalId(f"APR-paper-fill-{config.config_digest[:16]}"),
            Stage.S3_PAPER_DEMO,
            PaperFillPriceSource.QUOTE_MIDPOINT,
            PaperFeeModel.FIXED_BPS,
            self.policy.fee_bps,
            self.policy.fee_bps,
            self.policy.slippage_bps,
            self.policy.max_fill_latency_seconds,
            config.validation_evidence_refs,
            now,
            CreatorType.SYSTEM,
            _provenance(config),
        )
        fill = calculate_synthetic_fill(intent=intent, policy=fill_policy, quote=market_quote)
        return risk, risk_payload, fill

    def snapshot(self, *, now: datetime | None = None, range_name: str = "all") -> CockpitSnapshot:
        as_of = now or self._now()
        _range_start(as_of, range_name)
        if not self._configs:
            return inactive_snapshot(
                as_of, "No strategy is approved for paper simulation.", range_name
            )
        projection = self.store.current_projection()
        required_sources = ("BINANCE_BOOK_TICKER", "BINANCE_KLINES")
        health_events = {
            config.bot_id: {
                source: next(
                    (
                        event
                        for event in reversed(projection.events)
                        if event.event_type is PaperEventType.HEARTBEAT
                        and event.subject_id == config.bot_id
                        and event.payload.get("source") == source
                    ),
                    None,
                )
                for source in required_sources
            }
            for config in self._configs
        }
        heartbeat_events = {
            bot_id: max(
                (event for event in components.values() if event is not None),
                key=lambda event: event.sequence,
                default=None,
            )
            for bot_id, components in health_events.items()
        }
        starts = {
            event.subject_id: event.occurred_at
            for event in projection.events
            if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
        }
        evaluated = {
            event.subject_id: datetime.fromisoformat(str(event.payload["last_evaluated_bar_at"]))
            for event in projection.events
            if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "EVALUATED"
        }
        evaluated_events = {
            config.bot_id: next(
                (
                    event
                    for event in reversed(projection.events)
                    if event.event_type is PaperEventType.BOT
                    and event.subject_id == config.bot_id
                    and event.payload.get("kind") == "EVALUATED"
                ),
                None,
            )
            for config in self._configs
        }
        unresolved_incidents = {
            config.bot_id: tuple(
                event
                for event in projection.events
                if event.event_type is PaperEventType.INCIDENT
                and event.subject_id == config.bot_id
                and not (
                    event.payload.get("code") == "MISSED_BARS"
                    and f"paper-incident-{event.sequence}" in projection.acknowledged_item_ids
                )
                and not _incident_recovered(
                    event, health_events[config.bot_id], evaluated_events[config.bot_id]
                )
            )
            for config in self._configs
        }
        points = _range_points(projection.portfolio_points, as_of, range_name)
        latest = points[-1]
        pnl = (
            latest.equity
            - points[0].equity
            - sum((point.external_cash_flow for point in points[1:]), Decimal(0))
        )
        peak = max(point.equity for point in points)
        drawdown = (peak - latest.equity) / peak if peak else Decimal(0)
        positions_state = _position_state(projection)
        marks = _latest_marks(projection)
        bot_pnl = {
            config.bot_id: _position_pnl(
                positions_state.get(config.bot_id), marks.get(config.bot_id)
            )
            for config in self._configs
        }
        bot_stats = {
            config.bot_id: _bot_statistics(projection, config.bot_id, config.allocated_capital)
            for config in self._configs
        }
        bot_stale = {
            config.bot_id: any(
                _heartbeat_stale(health_events[config.bot_id][source], as_of, self.policy)
                for source in required_sources
            )
            or any(
                event.payload.get("source") != "RISK_ENGINE"
                for event in unresolved_incidents[config.bot_id]
            )
            for config in self._configs
        }
        bots = tuple(
            PaperBotSnapshot(
                config.bot_id,
                str(config.strategy_version_ref),
                config.symbol,
                config.timeframe.value,
                config.config_digest,
                PaperBotPhase.STALE
                if bot_stale[config.bot_id]
                else PaperBotPhase.PAUSED
                if projection.entries_paused
                else PaperBotPhase.POSITION_OPEN
                if config.bot_id in positions_state and positions_state[config.bot_id].quantity > 0
                else PaperBotPhase.WATCHING,
                starts.get(config.bot_id),
                _event_at(heartbeat_events[config.bot_id]),
                evaluated.get(config.bot_id),
                evaluated[config.bot_id] + timedelta(seconds=config.timeframe.seconds)
                if config.bot_id in evaluated
                else None,
                (),
                projection.entries_paused,
                config.allocated_capital,
                bot_pnl[config.bot_id],
                bot_pnl[config.bot_id] / config.allocated_capital,
                bot_stats[config.bot_id][0],
                bot_stats[config.bot_id][1],
                bot_stats[config.bot_id][2],
            )
            for config in self._configs
        )
        positions = tuple(
            PaperPositionSnapshot(
                config.bot_id,
                config.symbol,
                state.opened_at,
                as_of,
                state.quantity,
                state.cost / state.quantity,
                marks.get(config.bot_id, state.mark),
                state.quantity * marks.get(config.bot_id, state.mark),
                state.realized,
                state.quantity * marks.get(config.bot_id, state.mark) - state.cost,
            )
            for config in self._configs
            if (state := positions_state.get(config.bot_id)) is not None and state.quantity > 0
        )
        signals = tuple(
            SignalWatchSnapshot(
                str(event.payload["signal_id"]),
                event.subject_id,
                str(event.payload["symbol"]),
                str(event.payload["timeframe"]),
                str(event.payload["side"]),
                SignalWatchState.EXPIRED
                if (as_of - event.occurred_at).total_seconds()
                > self.policy.max_fill_latency_seconds
                else SignalWatchState.TRIGGERED,
                event.occurred_at,
                str(event.payload["rationale"]),
                (),
            )
            for event in projection.events
            if event.event_type is PaperEventType.SIGNAL
        )
        attention_items: list[AttentionItem] = []
        for config in self._configs:
            for incident in unresolved_incidents[config.bot_id]:
                item_id = f"paper-incident-{incident.sequence}"
                attention_items.append(
                    AttentionItem(
                        item_id,
                        AttentionSeverity.CRITICAL
                        if incident.payload.get("source") == "RISK_ENGINE"
                        else AttentionSeverity.WARNING,
                        f"{config.symbol} paper runtime needs attention",
                        str(incident.payload["summary"]),
                        incident.occurred_at,
                        acknowledged=item_id in projection.acknowledged_item_ids,
                    )
                )
            if bot_stale[config.bot_id] and not unresolved_incidents[config.bot_id]:
                heartbeat = heartbeat_events[config.bot_id]
                generation = heartbeat.sequence if heartbeat is not None else 0
                item_id = f"paper-stale-{config.bot_id}-{generation}"
                attention_items.append(
                    AttentionItem(
                        item_id,
                        AttentionSeverity.WARNING,
                        f"{config.symbol} paper feed needs attention",
                        "A required market-data component has no fresh heartbeat.",
                        heartbeat.occurred_at if heartbeat is not None else as_of,
                        acknowledged=item_id in projection.acknowledged_item_ids,
                    )
                )
        attention = tuple(attention_items)
        portfolio = PortfolioPerformance(
            True,
            None,
            range_name,
            as_of,
            "USDT",
            latest.equity,
            latest.cash,
            latest.exposure,
            pnl,
            latest.realized_pnl,
            latest.unrealized_pnl,
            latest.fees,
            drawdown,
            tuple(EquityPoint(point.observed_at, point.equity) for point in points),
        )
        activity = tuple(
            PaperActivity(
                event.sequence,
                event.event_type.value,
                event.subject_id,
                event.occurred_at,
                _event_summary(event.payload),
            )
            for event in projection.events[-20:]
        )
        return CockpitSnapshot(
            True,
            None,
            PaperMode.SYNTHETIC_LOCAL_SIMULATOR,
            f"{len(bots)} paper bot{' is' if len(bots) == 1 else 's are'} watching; "
            f"{len(attention)} item{' needs' if len(attention) == 1 else 's need'} attention.",
            as_of,
            tuple(
                SourceFreshness(
                    f"BINANCE_PUBLIC_DATA:{config.bot_id}",
                    FreshnessStatus.UNAVAILABLE
                    if any(
                        event.payload.get("source") != "RISK_ENGINE"
                        for event in unresolved_incidents[config.bot_id]
                    )
                    else FreshnessStatus.STALE
                    if any(
                        _heartbeat_stale(health_events[config.bot_id][source], as_of, self.policy)
                        for source in required_sources
                    )
                    else FreshnessStatus.LIVE,
                    _event_at(heartbeat_events[config.bot_id]),
                    "Public market data only; no account or order connection.",
                )
                for config in self._configs
            ),
            attention,
            portfolio,
            bots,
            positions,
            signals,
            tuple(sorted(bots, key=lambda bot: bot.return_fraction, reverse=True)),
            (),
            activity,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() != timedelta(0):
            raise PaperRuntimeError("paper runner clock must return UTC")
        return now


def inactive_snapshot(as_of: datetime, reason: str, range_name: str = "all") -> CockpitSnapshot:
    _range_start(as_of, range_name)
    portfolio = PortfolioPerformance(
        False,
        reason,
        range_name,
        as_of,
        "USDT",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    return CockpitSnapshot(
        False,
        reason,
        PaperMode.RESEARCH_ONLY,
        "Research is available, but no strategy is approved for paper simulation.",
        as_of,
        (SourceFreshness("PAPER_RUNTIME", FreshnessStatus.UNAVAILABLE, None, reason),),
        (),
        portfolio,
        (),
        (),
        (),
        (),
        (),
        (),
    )


def _range_start(as_of: datetime, range_name: str) -> datetime | None:
    if range_name == "all":
        return None
    durations = {
        "24h": timedelta(hours=24),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
        "1m": timedelta(days=30),
        "30d": timedelta(days=30),
    }
    if range_name == "1d":
        local = as_of.astimezone(ZoneInfo("Asia/Jerusalem"))
        return datetime.combine(local.date(), datetime_time.min, tzinfo=local.tzinfo).astimezone(
            UTC
        )
    if range_name not in durations:
        raise PaperRuntimeError("range must be one of 24h, 1d, 3d, 7d, 1m, 30d, all")
    return as_of - durations[range_name]


def _range_points(
    points: tuple[StoredPortfolioPoint, ...], as_of: datetime, range_name: str
) -> tuple[StoredPortfolioPoint, ...]:
    retained = tuple(point for point in points if point.observed_at <= as_of)
    if not retained:
        raise PaperRuntimeError("paper portfolio has no retained point at the requested time")
    start = _range_start(as_of, range_name)
    if start is None:
        return retained
    baseline = next(
        (point for point in reversed(retained) if point.observed_at <= start),
        retained[0],
    )
    return (baseline,) + tuple(
        point
        for point in retained
        if point.sequence > baseline.sequence and point.observed_at > start
    )


def _warmup(config: PaperRuntimeConfig) -> int:
    windows = [
        int(indicator.parameters.get("window", 1))
        for indicator in config.spec.indicators
        if str(indicator.parameters.get("window", 1)).isdigit()
    ]
    return min(1000, max(200, max(windows, default=1) + 2))


def _market(config: PaperRuntimeConfig) -> Market:
    base = "BTC" if config.symbol == "BTCUSDT" else "ETH"
    return Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BINANCE_SPOT"),
        InstrumentId(f"{base}-USDT.BINANCE_SPOT"),
        config.timeframe,
        DatasetId(f"DS-paper-{config.symbol}-{config.timeframe.value}"),
    )


def _bar(config: PaperRuntimeConfig, kline: object, created_at: datetime) -> MarketBar:
    # BinanceKline is kept structural here so deterministic test clients can inject it.
    return MarketBar(
        _market(config),
        kline.open_time,  # type: ignore[attr-defined]
        kline.close_time,  # type: ignore[attr-defined]
        kline.open,  # type: ignore[attr-defined]
        kline.high,  # type: ignore[attr-defined]
        kline.low,  # type: ignore[attr-defined]
        kline.close,  # type: ignore[attr-defined]
        kline.volume,  # type: ignore[attr-defined]
        created_at,
        CreatorType.SYSTEM,
        _provenance(config),
    )


def _provenance(config: PaperRuntimeConfig) -> Provenance:
    return Provenance(config.validation_evidence_refs)


def _run_ref(config: PaperRuntimeConfig) -> RunId:
    return RunId(f"RUN-paper-{config.config_digest[:20]}")


def _state_signal(
    config: PaperRuntimeConfig,
    side: Side,
    observed_at: datetime,
    created_at: datetime,
    rationale: str,
) -> SignalEvent:
    digest = hashlib.sha256(
        f"{config.bot_id}|{observed_at.isoformat()}|{side.value}|{rationale}".encode()
    ).hexdigest()[:24]
    return SignalEvent(
        SignalId(f"SIG-{digest}"),
        config.strategy_version_ref,
        _run_ref(config),
        _market(config).instrument,
        config.timeframe,
        observed_at,
        side,
        rationale,
        created_at,
        CreatorType.SYSTEM,
        _provenance(config),
    )


@dataclass(slots=True)
class _PositionState:
    quantity: Decimal
    cost: Decimal
    realized: Decimal
    mark: Decimal
    opened_at: datetime


def _activation_payload(config: PaperRuntimeConfig, policy: PaperRiskPolicy) -> dict[str, object]:
    assert config.gate is not None and config.validation_approval_ref is not None
    risk_policy: dict[str, object] = {
        "starting_capital": _decimal_identity(policy.starting_capital),
        "max_position_notional": _decimal_identity(policy.max_position_notional),
        "max_total_exposure": _decimal_identity(policy.max_total_exposure),
        "max_daily_loss": _decimal_identity(policy.max_daily_loss),
        "max_drawdown_fraction": _decimal_identity(policy.max_drawdown_fraction),
        "max_open_positions": policy.max_open_positions,
        "fee_bps": _decimal_identity(policy.fee_bps),
        "slippage_bps": _decimal_identity(policy.slippage_bps),
        "quote_max_age_seconds": policy.quote_max_age_seconds,
        "max_fill_latency_seconds": policy.max_fill_latency_seconds,
        "heartbeat_interval_seconds": policy.heartbeat_interval_seconds,
        "stale_after_seconds": policy.stale_after_seconds,
    }
    policy_json = json.dumps(risk_policy, sort_keys=True, separators=(",", ":"))
    return {
        "kind": "STARTED",
        "strategy_version_ref": str(config.strategy_version_ref),
        "symbol": config.symbol,
        "timeframe": config.timeframe.value,
        "config_digest": config.config_digest,
        "spec_sha256": config.spec_sha256,
        "gate_id": str(config.gate.gate_id),
        "approval_sha256": config.approval_sha256,
        "risk_policy": risk_policy,
        "policy_sha256": hashlib.sha256(policy_json.encode()).hexdigest(),
        "validation_approval_ref": str(config.validation_approval_ref),
        "validation_evidence_refs": [str(ref) for ref in config.validation_evidence_refs],
    }


def _last_evaluated(projection: PaperStoreProjection, bot_id: str) -> datetime | None:
    return max(
        (
            datetime.fromisoformat(str(event.payload["last_evaluated_bar_at"]))
            for event in projection.events
            if event.event_type is PaperEventType.BOT
            and event.subject_id == bot_id
            and event.payload.get("kind") == "EVALUATED"
        ),
        default=None,
    )


def _signal_write(config: PaperRuntimeConfig, signal: SignalEvent) -> PaperEventWrite:
    return PaperEventWrite(
        PaperEventType.SIGNAL,
        config.bot_id,
        {
            "signal_id": str(signal.signal_id),
            "symbol": config.symbol,
            "timeframe": config.timeframe.value,
            "side": signal.side.value,
            "rationale": signal.rationale_code,
        },
        f"signal:{signal.signal_id}",
        signal.observed_at,
    )


def _risk_reason(risk: RiskDecision | None) -> str:
    if risk is None:
        return "EXIT_ALLOWED"
    blocked = tuple(
        check.rule_code for check in risk.rule_results if check.outcome is RiskOutcome.BLOCK
    )
    return "ENTRY_RISK" if not blocked else f"BLOCKED:{','.join(blocked)}"


def _fill_write(
    config: PaperRuntimeConfig,
    signal: SignalEvent,
    fill: SyntheticFillCalculation,
    ledger: dict[str, Decimal],
    position: _PositionState,
    now: datetime,
) -> PaperEventWrite:
    assert fill.price is not None and fill.notional is not None and fill.fee is not None
    return PaperEventWrite(
        PaperEventType.FILL,
        config.bot_id,
        {
            "signal_id": str(signal.signal_id),
            "fill_id": f"FILL-{str(signal.signal_id)[4:]}",
            "symbol": config.symbol,
            "timeframe": config.timeframe.value,
            "side": signal.side.value,
            "price": str(fill.price),
            "quantity": str(fill.quantity),
            "notional": str(fill.notional.amount),
            "fee": str(fill.fee.amount),
            "cash_after": str(ledger["cash"]),
            "position_quantity_after": str(position.quantity),
            "position_cost_after": str(position.cost),
            "realized_pnl_after": str(position.realized),
            "fees_after": str(ledger["fees"]),
        },
        f"fill:{signal.signal_id}",
        now,
    )


def _position_state(projection: PaperStoreProjection) -> dict[str, _PositionState]:
    positions: dict[str, _PositionState] = {}
    for event in projection.events:
        if event.event_type is not PaperEventType.FILL:
            continue
        previous = positions.get(event.subject_id)
        quantity = Decimal(str(event.payload["position_quantity_after"]))
        positions[event.subject_id] = _PositionState(
            quantity,
            Decimal(str(event.payload["position_cost_after"])),
            Decimal(str(event.payload["realized_pnl_after"])),
            Decimal(str(event.payload["price"])),
            (
                event.occurred_at
                if quantity > 0 and (previous is None or previous.quantity == 0)
                else previous.opened_at
                if previous is not None
                else event.occurred_at
            ),
        )
    return positions


def _latest_marks(projection: PaperStoreProjection) -> dict[str, Decimal]:
    marks: dict[str, Decimal] = {}
    for event in projection.events:
        if (
            event.event_type is PaperEventType.HEARTBEAT
            and event.payload.get("source") in {"BINANCE_BOOK_TICKER", "BINANCE_PUBLIC_DATA"}
            and "mark_price" in event.payload
        ):
            marks[event.subject_id] = Decimal(str(event.payload["mark_price"]))
    return marks


def _marked_ledger(
    projection: PaperStoreProjection, marks: dict[str, Decimal]
) -> dict[str, Decimal]:
    positions = _position_state(projection)
    latest = projection.portfolio_points[-1]
    exposure = sum(
        (
            position.quantity * marks.get(bot_id, position.mark)
            for bot_id, position in positions.items()
            if position.quantity > 0
        ),
        Decimal(0),
    )
    unrealized = exposure - sum(
        (position.cost for position in positions.values() if position.quantity > 0),
        Decimal(0),
    )
    return {
        "cash": latest.cash,
        "exposure": exposure,
        "equity": latest.cash + exposure,
        "realized": sum((position.realized for position in positions.values()), Decimal(0)),
        "unrealized": unrealized,
        "fees": latest.fees,
    }


def _loss_and_drawdown(projection: PaperStoreProjection, now: datetime) -> tuple[Decimal, Decimal]:
    retained = tuple(point for point in projection.portfolio_points if point.observed_at <= now)
    if not retained:
        raise PaperRuntimeError("paper portfolio has no retained point at the requested time")
    latest = retained[-1]
    peak = max(point.equity for point in retained)
    drawdown = (peak - latest.equity) / peak if peak else Decimal(0)
    day = _range_points(retained, now, "1d")
    day_pnl = (
        day[-1].equity
        - day[0].equity
        - sum((point.external_cash_flow for point in day[1:]), Decimal(0))
    )
    return max(Decimal(0), -day_pnl), drawdown


def _after_fill(
    projection: PaperStoreProjection,
    bot_id: str,
    side: Side,
    fill: SyntheticFillCalculation,
    marks: dict[str, Decimal],
    now: datetime,
) -> tuple[dict[str, Decimal], _PositionState]:
    assert fill.price is not None and fill.notional is not None and fill.fee is not None
    positions = _position_state(projection)
    position = positions.setdefault(
        bot_id,
        _PositionState(Decimal(0), Decimal(0), Decimal(0), fill.price, now),
    )
    quantity, cost, realized = position.quantity, position.cost, position.realized
    latest = projection.portfolio_points[-1]
    if side is Side.BUY:
        cash = latest.cash - fill.notional.amount - fill.fee.amount
        if cash < 0:
            raise PaperRuntimeError("synthetic ledger cash would be overdrawn")
        quantity += fill.quantity
        cost += fill.notional.amount + fill.fee.amount
    else:
        if fill.quantity > quantity:
            raise PaperRuntimeError("synthetic spot position cannot sell more than it holds")
        sold_cost = cost * fill.quantity / quantity
        cash = latest.cash + fill.notional.amount - fill.fee.amount
        quantity -= fill.quantity
        cost -= sold_cost
        realized += fill.notional.amount - fill.fee.amount - sold_cost
    position.quantity, position.cost = quantity, cost
    position.realized, position.mark = realized, fill.price
    exposure = sum(
        (
            item.quantity * marks.get(subject, item.mark)
            for subject, item in positions.items()
            if item.quantity > 0
        ),
        Decimal(0),
    )
    unrealized = exposure - sum(
        (item.cost for item in positions.values() if item.quantity > 0), Decimal(0)
    )
    return (
        {
            "cash": cash,
            "exposure": exposure,
            "equity": cash + exposure,
            "realized": sum((item.realized for item in positions.values()), Decimal(0)),
            "unrealized": unrealized,
            "fees": latest.fees + fill.fee.amount,
        },
        position,
    )


def _position_pnl(position: _PositionState | None, mark: Decimal | None) -> Decimal:
    if position is None:
        return Decimal(0)
    return position.realized + position.quantity * (mark or position.mark) - position.cost


def _bot_statistics(
    projection: PaperStoreProjection, bot_id: str, allocated: Decimal
) -> tuple[Decimal, int, Decimal | None]:
    quantity = cost = realized = Decimal(0)
    mark = Decimal(0)
    peak = allocated
    max_drawdown = Decimal(0)
    trades = wins = 0
    for event in projection.events:
        if event.subject_id != bot_id:
            continue
        if event.event_type is PaperEventType.FILL:
            quantity = Decimal(str(event.payload["position_quantity_after"]))
            cost = Decimal(str(event.payload["position_cost_after"]))
            updated_realized = Decimal(str(event.payload["realized_pnl_after"]))
            if event.payload["side"] == "SELL":
                trades += 1
                wins += updated_realized > realized
            realized = updated_realized
            mark = Decimal(str(event.payload["price"]))
        elif (
            event.event_type is PaperEventType.HEARTBEAT
            and event.payload.get("source") == "BINANCE_BOOK_TICKER"
        ):
            mark = Decimal(str(event.payload["mark_price"]))
        else:
            continue
        equity = allocated + realized + quantity * mark - cost
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown, trades, Decimal(wins) / trades if trades else None


def _event_at(event: StoredPaperEvent | None) -> datetime | None:
    return event.occurred_at if event is not None else None


def _heartbeat_stale(
    heartbeat: StoredPaperEvent | None,
    as_of: datetime,
    policy: PaperRiskPolicy,
) -> bool:
    return (
        heartbeat is None
        or (as_of - heartbeat.occurred_at).total_seconds() > policy.stale_after_seconds
    )


def _incident_recovered(
    incident: StoredPaperEvent,
    health: dict[str, StoredPaperEvent | None],
    evaluated: StoredPaperEvent | None,
) -> bool:
    source = incident.payload.get("source")
    if source == "BINANCE_BOOK_TICKER":
        recovery = health["BINANCE_BOOK_TICKER"]
    elif source in {"BINANCE_KLINES", "BINANCE_PUBLIC_DATA"}:
        recovery = health["BINANCE_KLINES"]
    elif source == "STRATEGY_EVALUATOR":
        if incident.payload.get("code") == "MISSED_BARS":
            return False
        recovery = evaluated
    else:
        return False
    return recovery is not None and recovery.sequence > incident.sequence


def _risk(
    config: PaperRuntimeConfig,
    policy: PaperRiskPolicy,
    proposed: Decimal,
    exposure: Decimal,
    daily_loss: Decimal,
    drawdown: Decimal,
    open_positions: int,
    quote_age: int,
    spread_bps: Decimal,
    now: datetime,
) -> RiskDecision:
    context = DomainRef(str(config.strategy_version_ref))
    portfolio = PortfolioId("PF-paper-synthetic")
    evidence = config.validation_evidence_refs
    provenance = _provenance(config)
    runtime = SyntheticRuntimeRiskPolicy(
        RiskId(f"RISK-runtime-{config.config_digest[:12]}"),
        Stage.S3_PAPER_DEMO,
        context,
        portfolio,
        Money(policy.max_total_exposure, "USDT"),
        Money(policy.max_position_notional, "USDT"),
        Money(policy.max_daily_loss, "USDT"),
        policy.max_drawdown_fraction,
        KillSwitchMode.AUTOMATIC_LOCAL_SIMULATION,
        evidence,
        now,
        CreatorType.SYSTEM,
        provenance,
    )
    portfolio_policy = SyntheticPortfolioRiskPolicy(
        RiskId("RISK-paper-portfolio"),
        Stage.S3_PAPER_DEMO,
        portfolio,
        Decimal(1),
        Decimal(1),
        policy.max_position_notional / policy.starting_capital,
        policy.max_open_positions,
        evidence,
        now,
        CreatorType.SYSTEM,
        provenance,
    )
    budget = SyntheticStrategyBudgetPolicy(
        RiskId(f"RISK-budget-{config.config_digest[:12]}"),
        Stage.S3_PAPER_DEMO,
        context,
        portfolio,
        config.allocated_capital / policy.starting_capital,
        Money(config.allocated_capital, "USDT"),
        Money(min(policy.max_daily_loss, config.allocated_capital), "USDT"),
        policy.max_open_positions,
        evidence,
        now,
        CreatorType.SYSTEM,
        provenance,
    )
    market = SyntheticMarketConditionPolicy(
        RiskId(f"RISK-market-{config.config_digest[:12]}"),
        Stage.S3_PAPER_DEMO,
        context,
        policy.quote_max_age_seconds,
        Decimal("100"),
        True,
        True,
        evidence,
        now,
        CreatorType.SYSTEM,
        provenance,
    )
    return evaluate_synthetic_risk(
        risk_id=RiskId(f"RISK-decision-{config.config_digest[:12]}"),
        subject_ref=context,
        as_of=now,
        runtime_policy=runtime,
        portfolio_policy=portfolio_policy,
        strategy_budget=budget,
        market_policy=market,
        inputs=SyntheticRiskInputs(
            Money(proposed, "USDT"),
            Money(exposure + proposed, "USDT"),
            Money(max(Decimal(0), daily_loss), "USDT"),
            drawdown,
            Decimal(1),
            Decimal(1),
            proposed / policy.starting_capital,
            open_positions,
            quote_age,
            spread_bps,
        ),
        evidence_refs=evidence,
        created_at=now,
        creator_type=CreatorType.SYSTEM,
        provenance=provenance,
    )


def _event_summary(payload: dict[str, object]) -> str:
    return str(
        payload.get("summary") or payload.get("kind") or payload.get("rationale") or "Updated"
    )
