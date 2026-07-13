from __future__ import annotations

import json
import os
import sqlite3
import stat
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import tios.services.paper.store as paper_store_module
from tios.services.paper import (
    PUBLIC_DATA_HOST,
    BinanceBookTicker,
    BinanceDataError,
    BinancePublicClient,
    PaperEventType,
    PaperGateError,
    PaperRiskPolicy,
    PaperRunner,
    PaperRuntimeConfig,
    PaperRuntimeError,
    PaperStore,
    PaperStoreError,
    inactive_snapshot,
)
from tios.services.paper.market import MAX_RESPONSE_BYTES, _transport
from tios.services.paper.store import PaperEventWrite, PortfolioPointWrite
from tios.strategy.spec import CanonicalStrategySpec, Comparison, RuleTree
from tios.trading_domain import (
    ApprovalId,
    CreatorType,
    DomainRef,
    InstrumentId,
    Provenance,
    RunId,
    Side,
    SignalEvent,
    SignalId,
    Stage,
    StageGateId,
    StageGateReadinessRecord,
    StageGateRequirement,
    StageGateRequirementKind,
    StageGateStatus,
    StrategyVersionId,
    Timeframe,
)

NOW = datetime(2026, 7, 12, 12, tzinfo=UTC)
EVIDENCE = (DomainRef("EV-paper-runtime-test"),)
VERSION = StrategyVersionId("SV-STRAT-test-v1")


def _gate(
    status: StageGateStatus = StageGateStatus.APPROVED,
    version: StrategyVersionId = VERSION,
) -> StageGateReadinessRecord:
    codes = (
        "S2_EXIT_PASS",
        "HG_3_APPROVED",
        "COMPLETE_APPROVABLE_STRATEGY_CONTEXT",
        "PAPER_LANE_ARCHITECTURE_DECISION",
        "SECURITY_REVIEW_PASS",
        "SPECIFIC_INTEGRATION_OPERATOR_APPROVAL",
    )
    requirements = tuple(
        StageGateRequirement(
            code,
            StageGateRequirementKind.HUMAN_DECISION
            if code == "HG_3_APPROVED"
            else StageGateRequirementKind.EVIDENCE,
            status is StageGateStatus.APPROVED,
            (DomainRef("APR-paper-human"),)
            if code == "HG_3_APPROVED" and status is StageGateStatus.APPROVED
            else EVIDENCE
            if status is StageGateStatus.APPROVED
            else (),
            None if status is StageGateStatus.APPROVED else "not approved",
        )
        for code in codes
    )
    return StageGateReadinessRecord(
        StageGateId("GATE-paper-test"),
        Stage.S3_PAPER_DEMO,
        DomainRef(str(version)),
        requirements,
        status,
        NOW,
        CreatorType.HUMAN,
        Provenance(EVIDENCE),
    )


def _config(
    gate: StageGateReadinessRecord | None = None,
    *,
    version: StrategyVersionId = VERSION,
    symbol: str = "BTCUSDT",
    triggered: bool = False,
    spec_variant: str = "default",
) -> PaperRuntimeConfig:
    spec = CanonicalStrategySpec(
        strategy_id="STRAT-test",
        family="buy_and_hold",
        inputs=("open", "high", "low", "close", "volume"),
        indicators=(),
        entry_long=(RuleTree("all", (Comparison("close", ">", "99.5"),)) if triggered else None),
        exit_long=None,
        position_sizing={"type": "fixed_amount"},
        risk={"variant": spec_variant},
        always_in_market=not triggered,
    )
    return PaperRuntimeConfig(
        version,
        spec,
        symbol,
        Timeframe.M1,
        gate,
        "APPROVED",
        ApprovalId("APR-paper-validation"),
        EVIDENCE,
    )


def _row(opened: datetime, closed: datetime) -> list[object]:
    return [
        int(opened.timestamp() * 1000),
        "99",
        "101",
        "98",
        "100",
        "10",
        int(closed.timestamp() * 1000),
        "0",
        1,
        "0",
        "0",
        "0",
    ]


def _priced_row(opened: datetime, closed: datetime, close: str) -> list[object]:
    row = _row(opened, closed)
    row[4] = close
    return row


class _InjectedClient:
    def __init__(
        self,
        rows: tuple[list[object], ...],
        *,
        fail_symbol: str | None = None,
    ) -> None:
        self.rows = rows
        self.fail_symbol = fail_symbol

    def fetch_book_ticker(self, symbol: str) -> BinanceBookTicker:
        return BinanceBookTicker(
            symbol,
            Decimal("99.99"),
            Decimal("2"),
            Decimal("100.01"),
            Decimal("2"),
            NOW,
        )

    def fetch_klines(self, symbol: str, interval: Timeframe, *, limit: int):
        if symbol == self.fail_symbol:
            raise BinanceDataError(f"{symbol} injected feed failure")
        payload = json.dumps(list(self.rows)).encode()
        return BinancePublicClient(transport=lambda _r, _t: payload).fetch_klines(
            symbol, interval, limit=limit
        )


def test_store_is_confined_append_only_idempotent_and_replayable(tmp_path: Path) -> None:
    with pytest.raises(PaperStoreError, match="artifacts/paper"):
        PaperStore(tmp_path / "outside.sqlite3", root=tmp_path)
    store = PaperStore(root=tmp_path)
    first = store.append_event(
        PaperEventType.HEARTBEAT,
        "paper-runner",
        {"ok": True},
        idempotency_key="heartbeat-1",
        occurred_at=NOW,
    )
    assert (
        store.append_event(
            PaperEventType.HEARTBEAT,
            "paper-runner",
            {"ok": True},
            idempotency_key="heartbeat-1",
            occurred_at=NOW,
        )
        == first
    )
    with pytest.raises(PaperStoreError, match="conflicts"):
        store.append_event(
            PaperEventType.HEARTBEAT,
            "paper-runner",
            {"ok": False},
            idempotency_key="heartbeat-1",
            occurred_at=NOW,
        )
    store.set_entries_paused(True, actor="operator", idempotency_key="pause-1", occurred_at=NOW)
    store.append_portfolio_point(
        idempotency_key="point-1",
        observed_at=NOW,
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        exposure=Decimal(0),
        realized_pnl=Decimal(0),
        unrealized_pnl=Decimal(0),
        fees=Decimal(0),
    )
    replay = PaperStore(root=tmp_path).current_projection()
    assert replay.entries_paused is True
    assert replay.latest_heartbeat_at == NOW
    assert replay.portfolio_points[0].equity == Decimal("10000")
    assert store.integrity_check() is True

    connection = sqlite3.connect(store.path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("DELETE FROM paper_events")
    connection.close()


def test_public_client_parses_only_allowlisted_data_and_retries_429() -> None:
    requests = []
    delays: list[float] = []
    calls = 0

    def transport(request, timeout):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        requests.append((request, timeout))
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "slow down", {"Retry-After": "2"}, None
            )
        if "/klines?" in request.full_url:
            return json.dumps([_row(NOW - timedelta(minutes=1), NOW)]).encode()
        return json.dumps(
            {
                "symbol": "BTCUSDT",
                "bidPrice": "99.99",
                "bidQty": "1",
                "askPrice": "100.01",
                "askQty": "2",
            }
        ).encode()

    client = BinancePublicClient(transport=transport, sleep=delays.append, clock=lambda: NOW)
    bars = client.fetch_klines("BTCUSDT", Timeframe.M1, limit=2)
    quote = client.fetch_book_ticker("BTCUSDT")
    assert bars[0].close == Decimal("100") and bars[0].is_closed(NOW)
    assert quote.midpoint == Decimal("100.00")
    assert delays == [2.0]
    assert all(request.full_url.startswith(PUBLIC_DATA_HOST) for request, _ in requests)
    assert all(request.get_method() == "GET" for request, _ in requests)
    assert all(
        not any(
            name.lower() in {"authorization", "x-mbx-apikey"} for name, _ in request.header_items()
        )
        for request, _ in requests
    )
    assert all(
        "/order" not in request.full_url and "/account" not in request.full_url
        for request, _ in requests
    )
    with pytest.raises(BinanceDataError, match="limited"):
        client.fetch_book_ticker("SOLUSDT")


def test_runner_refuses_absent_or_unapproved_gate_without_network(tmp_path: Path) -> None:
    class NoNetwork:
        def fetch_book_ticker(self, symbol: str):
            raise AssertionError(symbol)

        def fetch_klines(self, symbol: str, interval: Timeframe, *, limit: int):
            raise AssertionError((symbol, interval, limit))

    runner = PaperRunner(PaperStore(root=tmp_path), NoNetwork())  # type: ignore[arg-type]
    with pytest.raises(PaperGateError, match="no strategy"):
        runner.activate(())
    with pytest.raises(PaperGateError, match="stage gate"):
        runner.activate((_config(None),))
    with pytest.raises(PaperGateError, match="APPROVED"):
        runner.activate((_config(_gate(StageGateStatus.BLOCKED)),))
    snapshot = inactive_snapshot(NOW, "No strategy is approved for paper simulation.")
    assert snapshot.available is False
    assert snapshot.portfolio.equity is None
    assert snapshot.execution_authority == "NONE" and snapshot.real_money is False


def test_runner_uses_closed_bars_and_supports_deterministic_gated_fill(tmp_path: Path) -> None:
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _row(NOW, NOW + timedelta(minutes=1)),
    )

    class InjectedClient:
        def fetch_book_ticker(self, symbol: str) -> BinanceBookTicker:
            return BinanceBookTicker(
                symbol,
                Decimal("99.99"),
                Decimal("2"),
                Decimal("100.01"),
                Decimal("2"),
                NOW,
            )

        def fetch_klines(self, symbol: str, interval: Timeframe, *, limit: int):
            payload = json.dumps(list(rows)).encode()
            return BinancePublicClient(transport=lambda _r, _t: payload).fetch_klines(
                symbol, interval, limit=limit
            )

    config = _config(_gate(), triggered=True)
    runner = PaperRunner(
        PaperStore(root=tmp_path),
        InjectedClient(),
        clock=lambda: NOW,  # type: ignore[arg-type]
    )
    runner.activate((config,))
    snapshot = runner.run_once()
    assert snapshot.available and snapshot.mode.value == "SYNTHETIC_LOCAL_SIMULATOR"
    assert snapshot.bots[0].last_evaluated_bar_at == NOW - timedelta(minutes=1)
    assert snapshot.portfolio.equity == Decimal("10000")

    signal = SignalEvent(
        SignalId("SIG-paper-fill"),
        VERSION,
        RunId("RUN-paper-fill"),
        InstrumentId("BTC-USDT.BINANCE_SPOT"),
        Timeframe.M1,
        NOW,
        Side.BUY,
        "ENTRY_LONG",
        NOW,
        CreatorType.SYSTEM,
        Provenance(EVIDENCE),
    )
    fill = runner.calculate_gated_fill(
        config,
        signal,
        InjectedClient().fetch_book_ticker("BTCUSDT"),
        quantity=Decimal(1),
    )
    assert fill.price == Decimal("100.020000")
    assert fill.fee is not None and fill.fee.amount == Decimal("0.100020000")

    runner.store.set_entries_paused(
        True, actor="operator", idempotency_key="pause-fill-test", occurred_at=NOW
    )
    with pytest.raises(PaperRuntimeError, match="entries are paused"):
        runner.calculate_gated_fill(
            config,
            signal,
            InjectedClient().fetch_book_ticker("BTCUSDT"),
            quantity=Decimal(1),
        )

    stale_quote = BinanceBookTicker(
        "BTCUSDT",
        Decimal("99"),
        Decimal(1),
        Decimal("101"),
        Decimal(1),
        NOW - timedelta(seconds=16),
    )
    with pytest.raises(PaperRuntimeError, match="stale"):
        runner.calculate_gated_fill(config, signal, stale_quote, quantity=Decimal(1), as_of=NOW)


def test_conservative_defaults_are_locked() -> None:
    policy = PaperRiskPolicy()
    assert (
        policy.starting_capital,
        policy.max_position_notional,
        policy.max_total_exposure,
        policy.max_daily_loss,
        policy.max_drawdown_fraction,
        policy.max_open_positions,
        policy.fee_bps,
        policy.slippage_bps,
        policy.quote_max_age_seconds,
        policy.max_fill_latency_seconds,
        policy.heartbeat_interval_seconds,
        policy.stale_after_seconds,
    ) == (
        Decimal("10000"),
        Decimal("1000"),
        Decimal("2000"),
        Decimal("100"),
        Decimal("0.05"),
        2,
        Decimal("10"),
        Decimal("2"),
        15,
        5,
        10,
        30,
    )


def test_same_closed_candle_is_idempotent_and_cannot_fill_twice(tmp_path: Path) -> None:
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(
        store,
        _InjectedClient(rows),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    runner.activate((_config(_gate(), triggered=True),))

    runner.run_once()
    runner.run_once()

    projection = store.current_projection()
    assert sum(event.event_type is PaperEventType.SIGNAL for event in projection.events) == 1
    assert sum(event.event_type is PaperEventType.RISK for event in projection.events) == 1
    assert sum(event.event_type is PaperEventType.FILL for event in projection.events) == 1
    assert (
        sum(
            event.event_type is PaperEventType.BOT and event.payload.get("kind") == "EVALUATED"
            for event in projection.events
        )
        == 1
    )


def test_activation_binds_spec_digest_and_refuses_substitution_or_mutation(
    tmp_path: Path,
) -> None:
    config = _config(_gate(), triggered=True)
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(
        store,
        _InjectedClient(()),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    runner.activate((config,))
    started = next(
        event
        for event in store.current_projection().events
        if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
    )
    assert started.payload["spec_sha256"] == config.spec_sha256
    assert started.payload["config_digest"] == config.config_digest

    substitute = _config(_gate(), triggered=True, spec_variant="substitute")
    with pytest.raises(PaperGateError, match="substitution"):
        runner.activate((substitute,))

    config.spec.risk["variant"] = "mutated"
    with pytest.raises(PaperRuntimeError, match="changed"):
        runner.run_once()


def test_signal_risk_fill_and_accounting_commit_as_one_cycle(tmp_path: Path) -> None:
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(
        store,
        _InjectedClient(rows),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    config = _config(_gate(), triggered=True)
    runner.activate((config,))
    snapshot = runner.run_once()
    projection = store.current_projection()

    cycle = tuple(
        event
        for event in projection.events
        if event.event_type in {PaperEventType.SIGNAL, PaperEventType.RISK, PaperEventType.FILL}
    )
    assert tuple(event.event_type for event in cycle) == (
        PaperEventType.SIGNAL,
        PaperEventType.RISK,
        PaperEventType.FILL,
    )
    assert cycle[1].payload["decision"] == "PASS"
    fill = cycle[2].payload
    point = next(
        point
        for point in projection.portfolio_points
        if point.idempotency_key.startswith("portfolio-fill:")
    )
    assert point.cash == Decimal(str(fill["cash_after"]))
    assert point.fees == Decimal(str(fill["fees_after"])) == Decimal(str(fill["fee"]))
    assert point.equity == point.cash + point.exposure
    assert point.unrealized_pnl == point.exposure - Decimal(str(fill["position_cost_after"]))
    assert snapshot.positions[0].quantity == Decimal(str(fill["position_quantity_after"]))

    before = len(projection.events)
    with pytest.raises(PaperStoreError):
        store.commit_cycle(
            (
                PaperEventWrite(
                    PaperEventType.SIGNAL,
                    config.bot_id,
                    {
                        "signal_id": "SIG-atomic-rollback",
                        "symbol": "BTCUSDT",
                        "timeframe": "1m",
                        "side": "BUY",
                        "rationale": "ROLLBACK_TEST",
                    },
                    "signal:atomic-rollback",
                    NOW,
                ),
            ),
            (
                PortfolioPointWrite(
                    "portfolio-atomic-rollback",
                    NOW,
                    Decimal("-1"),
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                    Decimal(0),
                ),
            ),
            recorded_at=NOW,
        )
    assert len(store.current_projection().events) == before


def test_independent_risk_blocks_a_second_bot_exposure_breach(tmp_path: Path) -> None:
    second_version = StrategyVersionId("SV-STRAT-test-v2")
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(
        store,
        _InjectedClient(rows),  # type: ignore[arg-type]
        policy=PaperRiskPolicy(max_total_exposure=Decimal("1500")),
        clock=lambda: NOW,
    )
    runner.activate(
        (
            _config(_gate(), triggered=True),
            _config(
                _gate(version=second_version),
                version=second_version,
                symbol="ETHUSDT",
                triggered=True,
            ),
        )
    )

    runner.run_once()
    projection = store.current_projection()
    risks = tuple(event for event in projection.events if event.event_type is PaperEventType.RISK)
    fills = tuple(event for event in projection.events if event.event_type is PaperEventType.FILL)
    assert tuple(event.payload["decision"] for event in risks) == ("PASS", "BLOCK")
    assert "CAPITAL_AT_RISK" in str(risks[1].payload["reason"])
    assert len(fills) == 1


def test_database_symlink_swap_is_refused(tmp_path: Path) -> None:
    store = PaperStore(root=tmp_path)
    store.initialize()
    retained = store.path.with_name("retained.sqlite3")
    store.path.rename(retained)
    store.path.symlink_to(retained)

    with pytest.raises(PaperStoreError, match="symlink"):
        store.current_projection()


def test_partial_bot_failure_is_isolated_and_acknowledgement_is_projected(
    tmp_path: Path,
) -> None:
    second_version = StrategyVersionId("SV-STRAT-test-v2")
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(
        store,
        _InjectedClient(rows, fail_symbol="ETHUSDT"),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    configs = (
        _config(_gate(), triggered=True),
        _config(
            _gate(version=second_version),
            version=second_version,
            symbol="ETHUSDT",
            triggered=True,
        ),
    )
    runner.activate(configs)
    snapshot = runner.run_once()

    status = {source.source: source.status.value for source in snapshot.sources}
    assert status[f"BINANCE_PUBLIC_DATA:{configs[0].bot_id}"] == "LIVE"
    assert status[f"BINANCE_PUBLIC_DATA:{configs[1].bot_id}"] == "UNAVAILABLE"
    assert {bot.bot_id: bot.phase.value for bot in snapshot.bots}[configs[1].bot_id] == "STALE"
    assert len(snapshot.attention) == 1 and "ETHUSDT" in snapshot.attention[0].title

    item_id = snapshot.attention[0].item_id
    store.acknowledge_attention(
        item_id,
        actor="operator",
        idempotency_key="ack-feed-failure",
        occurred_at=NOW,
    )
    projected = runner.snapshot(now=NOW)
    assert item_id in store.current_projection().acknowledged_item_ids
    assert projected.attention[0].acknowledged is True


def test_portfolio_ranges_use_prior_baselines_and_jerusalem_day_start(
    tmp_path: Path,
) -> None:
    store = PaperStore(root=tmp_path)
    jerusalem_start = datetime(2026, 7, 12, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem")).astimezone(UTC)
    retained = (
        (NOW - timedelta(days=40), Decimal("9000")),
        (NOW - timedelta(days=31), Decimal("9100")),
        (NOW - timedelta(days=8), Decimal("9200")),
        (NOW - timedelta(days=7), Decimal("9300")),
        (NOW - timedelta(days=3), Decimal("9400")),
        (NOW - timedelta(hours=24), Decimal("9500")),
        (jerusalem_start, Decimal("9600")),
        (NOW, Decimal("10000")),
    )
    runner = PaperRunner(
        store,
        _InjectedClient(()),  # type: ignore[arg-type]
        policy=PaperRiskPolicy(starting_capital=Decimal("9000")),
        clock=lambda: retained[0][0],
    )
    runner.activate((_config(_gate()),))
    for index, (observed_at, equity) in enumerate(retained[1:], start=1):
        store.append_portfolio_point(
            idempotency_key=f"range-point-{index}",
            observed_at=observed_at,
            equity=equity,
            cash=equity,
            exposure=Decimal(0),
            realized_pnl=Decimal(0),
            unrealized_pnl=Decimal(0),
            fees=Decimal(0),
        )
    expected = {
        "24h": (Decimal("9500"), Decimal("500")),
        "1d": (Decimal("9600"), Decimal("400")),
        "3d": (Decimal("9400"), Decimal("600")),
        "7d": (Decimal("9300"), Decimal("700")),
        "1m": (Decimal("9100"), Decimal("900")),
        "30d": (Decimal("9100"), Decimal("900")),
        "all": (Decimal("9000"), Decimal("1000")),
    }
    for range_name, (baseline, pnl) in expected.items():
        portfolio = runner.snapshot(now=NOW, range_name=range_name).portfolio
        assert portfolio.points[0].equity == baseline
        assert portfolio.pnl == pnl
    with pytest.raises(PaperRuntimeError, match="range must be"):
        runner.snapshot(now=NOW, range_name="year")


def test_payload_boundaries_reject_malformed_oversized_and_float_values(
    tmp_path: Path,
) -> None:
    store = PaperStore(root=tmp_path)
    with pytest.raises(PaperStoreError, match="schema"):
        store.append_event(
            PaperEventType.INCIDENT,
            "paper-runner",
            {"summary": "missing source"},
            idempotency_key="malformed-payload",
            occurred_at=NOW,
        )
    with pytest.raises(PaperStoreError, match="too large"):
        store.append_event(
            PaperEventType.INCIDENT,
            "paper-runner",
            {"summary": "x" * 5000, "source": "test"},
            idempotency_key="oversized-payload",
            occurred_at=NOW,
        )
    with pytest.raises(PaperStoreError, match="floating-point"):
        store.append_event(
            PaperEventType.INCIDENT,
            "paper-runner",
            {"summary": "float", "source": "test", "code": 1.5},
            idempotency_key="float-payload",
            occurred_at=NOW,
        )

    payload = json.dumps(
        {
            "symbol": "BTCUSDT",
            "bidPrice": 99.99,
            "bidQty": "1",
            "askPrice": "100.01",
            "askQty": "1",
        }
    ).encode()
    with pytest.raises(BinanceDataError, match="exact decimal"):
        BinancePublicClient(transport=lambda _r, _t: payload).fetch_book_ticker("BTCUSDT")


def test_replay_returns_every_retained_event_without_truncation(tmp_path: Path) -> None:
    store = PaperStore(root=tmp_path)
    count = 1105
    store.commit_cycle(
        tuple(
            PaperEventWrite(
                PaperEventType.HEARTBEAT,
                "paper-runner",
                {"ok": True},
                f"replay-heartbeat-{index}",
                NOW + timedelta(seconds=index),
            )
            for index in range(count)
        ),
        recorded_at=NOW,
    )

    replay = PaperStore(root=tmp_path).current_projection()
    assert len(replay.events) == count
    assert replay.events[0].idempotency_key == "replay-heartbeat-0"
    assert replay.events[-1].idempotency_key == f"replay-heartbeat-{count - 1}"


class _MutableClient(_InjectedClient):
    def __init__(self, rows: tuple[list[object], ...], clock: list[datetime]) -> None:
        super().__init__(rows)
        self.clock = clock
        self.bid = Decimal("99.99")
        self.ask = Decimal("100.01")
        self.fail_quotes = False
        self.fail_klines = False

    def fetch_book_ticker(self, symbol: str) -> BinanceBookTicker:
        if self.fail_quotes:
            raise BinanceDataError("injected quote failure")
        return BinanceBookTicker(
            symbol, self.bid, Decimal("2"), self.ask, Decimal("2"), self.clock[0]
        )

    def fetch_klines(self, symbol: str, interval: Timeframe, *, limit: int):
        if self.fail_klines:
            raise BinanceDataError("injected kline failure")
        return super().fetch_klines(symbol, interval, limit=limit)


def test_cycle_uses_post_fetch_time_and_does_not_consume_transient_fill(
    tmp_path: Path,
) -> None:
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    quote_clock = [NOW + timedelta(seconds=1)]
    runner = PaperRunner(
        PaperStore(root=tmp_path),
        _MutableClient(rows, quote_clock),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    runner.activate((_config(_gate(), triggered=True),))
    runner.run_once()
    assert any(
        event.event_type is PaperEventType.FILL
        for event in runner.store.current_projection().events
    )

    stale_root = tmp_path / "stale"
    stale_root.mkdir()
    stale_clock = [NOW - timedelta(seconds=16)]
    stale = PaperRunner(
        PaperStore(root=stale_root),
        _MutableClient(rows, stale_clock),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    stale.activate((_config(_gate(), triggered=True),))
    stale.run_once()
    assert not any(
        event.event_type is PaperEventType.BOT and event.payload.get("kind") == "EVALUATED"
        for event in stale.store.current_projection().events
    )


def test_open_positions_are_marked_each_cycle_and_risk_sees_the_mark(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    client = _MutableClient(rows, clock)
    runner = PaperRunner(PaperStore(root=tmp_path), client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((_config(_gate(), triggered=True),))
    first = runner.run_once()
    quantity = first.positions[0].quantity
    client.bid, client.ask = Decimal("110"), Decimal("110.02")
    marked = runner.run_once()
    assert marked.positions[0].mark_price == Decimal("110")
    assert marked.portfolio.exposure == quantity * Decimal("110")
    assert marked.portfolio.unrealized_pnl == marked.portfolio.exposure - Decimal(
        str(
            next(
                event.payload["position_cost_after"]
                for event in runner.store.current_projection().events
                if event.event_type is PaperEventType.FILL
            )
        )
    )
    assert marked.portfolio.equity == marked.portfolio.cash + marked.portfolio.exposure
    clock[0] += timedelta(seconds=5)
    client.bid, client.ask = Decimal("95"), Decimal("95.02")
    assert runner.run_once().leaderboard[0].max_drawdown_fraction > 0


def test_quote_and_kline_health_are_independent_and_stale_bars_stay_unhealthy(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    stale_rows = (_row(NOW - timedelta(minutes=3), NOW - timedelta(minutes=2)),)
    client = _MutableClient(stale_rows, clock)
    runner = PaperRunner(PaperStore(root=tmp_path), client, clock=lambda: clock[0])  # type: ignore[arg-type]
    config = _config(_gate(), triggered=True)
    runner.activate((config,))
    first = runner.run_once()
    assert first.sources[0].status.value == "UNAVAILABLE"
    clock[0] += timedelta(seconds=40)
    second = runner.run_once()
    assert second.sources[0].status.value == "UNAVAILABLE"
    assert not any(
        event.event_type is PaperEventType.BOT and event.payload.get("kind") == "EVALUATED"
        for event in runner.store.current_projection().events
    )


def test_evaluator_error_is_isolated_as_a_bot_incident(tmp_path: Path) -> None:
    broken = CanonicalStrategySpec(
        strategy_id="STRAT-broken",
        family="broken",
        inputs=("open", "high", "low", "close", "volume"),
        indicators=(),
        entry_long=RuleTree("all", (Comparison("missing_operand", ">", "0"),)),
        exit_long=None,
        position_sizing={"type": "fixed_amount"},
        risk={},
    )
    config = PaperRuntimeConfig(
        VERSION,
        broken,
        "BTCUSDT",
        Timeframe.M1,
        _gate(),
        "APPROVED",
        ApprovalId("APR-paper-validation"),
        EVIDENCE,
    )
    rows = (_row(NOW - timedelta(minutes=1), NOW),)
    runner = PaperRunner(
        PaperStore(root=tmp_path),
        _InjectedClient(rows),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    runner.activate((config,))
    snapshot = runner.run_once()
    assert snapshot.sources[0].status.value == "UNAVAILABLE"
    assert "missing rule operand" in snapshot.attention[0].summary


def test_full_warmup_state_enters_always_in_market_and_reconciles_latest_exit(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    client = _MutableClient(
        (
            _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "100"),
            _priced_row(NOW - timedelta(minutes=1), NOW - timedelta(seconds=10), "100"),
        ),
        clock,
    )
    runner = PaperRunner(PaperStore(root=tmp_path), client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((_config(_gate()),))
    assert len(runner.run_once().positions) == 1

    transition_spec = CanonicalStrategySpec(
        strategy_id="STRAT-transition",
        family="transition",
        inputs=("open", "high", "low", "close", "volume"),
        indicators=(),
        entry_long=RuleTree("all", (Comparison("close", ">", "99.5"),)),
        exit_long=RuleTree("all", (Comparison("close", "<", "99.5"),)),
        position_sizing={"type": "fixed_amount"},
        risk={},
    )
    exit_root = tmp_path / "exit"
    exit_root.mkdir()
    exit_client = _MutableClient(client.rows, clock)
    exit_config = PaperRuntimeConfig(
        VERSION,
        transition_spec,
        "BTCUSDT",
        Timeframe.M1,
        _gate(),
        "APPROVED",
        ApprovalId("APR-paper-validation"),
        EVIDENCE,
    )
    exit_runner = PaperRunner(
        PaperStore(root=exit_root),
        exit_client,
        clock=lambda: clock[0],  # type: ignore[arg-type]
    )
    exit_runner.activate((exit_config,))
    assert len(exit_runner.run_once().positions) == 1
    clock[0] += timedelta(minutes=1)
    exit_client.rows += (_priced_row(NOW, NOW + timedelta(minutes=1), "99"),)
    closed = exit_runner.run_once()
    assert closed.positions == ()
    assert closed.leaderboard[0].trade_count == 1
    assert closed.leaderboard[0].win_rate_fraction == 0


def test_missed_bar_is_retained_as_an_incident(tmp_path: Path) -> None:
    clock = [NOW - timedelta(minutes=2)]
    client = _MutableClient((_row(NOW - timedelta(minutes=3), NOW - timedelta(minutes=2)),), clock)
    runner = PaperRunner(PaperStore(root=tmp_path), client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((_config(_gate(), triggered=True),))
    runner.run_once()
    clock[0] = NOW
    client.rows = (_row(NOW - timedelta(minutes=1), NOW),)
    runner.run_once()
    assert any(
        event.event_type is PaperEventType.INCIDENT and event.payload.get("code") == "MISSED_BARS"
        for event in runner.store.current_projection().events
    )
    attention = runner.snapshot(now=clock[0]).attention
    assert len(attention) == 1 and "missed" in attention[0].summary.lower()
    runner.store.acknowledge_attention(
        attention[0].item_id,
        actor="operator",
        idempotency_key="ack-missed-bars",
        occurred_at=clock[0],
    )
    assert runner.snapshot(now=clock[0]).attention == ()


def test_attention_ack_is_scoped_to_one_incident_generation(tmp_path: Path) -> None:
    clock = [NOW]
    rows = (_priced_row(NOW - timedelta(minutes=1), NOW, "99"),)
    client = _MutableClient(rows, clock)
    client.fail_klines = True
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(store, client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((_config(_gate(), triggered=True),))
    first = runner.run_once().attention[0]
    store.acknowledge_attention(
        first.item_id, actor="operator", idempotency_key="ack-generation-1", occurred_at=clock[0]
    )
    client.fail_klines = False
    clock[0] += timedelta(seconds=40)
    assert runner.run_once().attention == ()
    client.fail_klines = True
    clock[0] += timedelta(seconds=40)
    second = runner.run_once().attention[0]
    assert second.item_id != first.item_id and second.acknowledged is False


def test_global_and_per_bot_position_limits_are_counted_separately(tmp_path: Path) -> None:
    second = StrategyVersionId("SV-STRAT-test-v2")
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    runner = PaperRunner(
        PaperStore(root=tmp_path),
        _InjectedClient(rows),
        clock=lambda: NOW,  # type: ignore[arg-type]
    )
    runner.activate(
        (
            _config(_gate(), triggered=True),
            _config(_gate(version=second), version=second, symbol="ETHUSDT", triggered=True),
        )
    )
    runner.run_once()
    projection = runner.store.current_projection()
    assert sum(event.event_type is PaperEventType.FILL for event in projection.events) == 2
    assert all(
        event.payload["decision"] == "PASS"
        for event in projection.events
        if event.event_type is PaperEventType.RISK
    )


def test_mark_breach_pauses_entries_closes_at_fresh_bid_and_records_kill(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    rows = (
        _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    client = _MutableClient(rows, clock)
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(store, client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((_config(_gate(), triggered=True),))
    runner.run_once()
    client.bid = client.ask = Decimal("85")
    client.fail_klines = True
    clock[0] += timedelta(seconds=5)
    snapshot = runner.run_once()
    projection = store.current_projection()
    assert snapshot.positions == () and projection.entries_paused is True
    kill = next(
        event
        for event in projection.events
        if event.event_type is PaperEventType.INCIDENT and event.payload.get("code") == "RISK_KILL"
    )
    assert "DAILY_LOSS" in str(kill.payload["summary"])
    sell = tuple(event for event in projection.events if event.event_type is PaperEventType.FILL)[
        -1
    ]
    assert sell.payload["side"] == "SELL" and Decimal(str(sell.payload["price"])) <= client.bid


def test_decimal_identities_and_minute_cash_flow_are_canonical(tmp_path: Path) -> None:
    config = _config(_gate())
    same = PaperRuntimeConfig(
        config.strategy_version_ref,
        config.spec,
        config.symbol,
        config.timeframe,
        config.gate,
        config.validation_status,
        config.validation_approval_ref,
        config.validation_evidence_refs,
        Decimal("1000.00"),
    )
    assert config.config_digest == same.config_digest

    store = PaperStore(root=tmp_path)
    clock = [NOW - timedelta(minutes=1)]
    rows = (_priced_row(NOW - timedelta(minutes=1), NOW, "99"),)
    runner = PaperRunner(
        store,
        _InjectedClient(rows),  # type: ignore[arg-type]
        clock=lambda: clock[0],
    )
    runner.activate((_config(_gate(), triggered=True),))
    store.append_portfolio_point(
        idempotency_key="cash-flow-source",
        observed_at=NOW - timedelta(minutes=1),
        equity=Decimal("10100.0"),
        cash=Decimal("10100.00"),
        exposure=Decimal("0.0"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        fees=Decimal("0"),
        external_cash_flow=Decimal("100.00"),
    )
    assert (
        store.append_portfolio_point(
            idempotency_key="cash-flow-source",
            observed_at=NOW - timedelta(minutes=1),
            equity=Decimal("10100.00"),
            cash=Decimal("10100.0"),
            exposure=Decimal("0"),
            realized_pnl=Decimal("0.0"),
            unrealized_pnl=Decimal("0.00"),
            fees=Decimal("0.0"),
            external_cash_flow=Decimal("100.0"),
        ).idempotency_key
        == "cash-flow-source"
    )
    clock[0] = NOW
    snapshot = runner.run_once()
    assert store.current_projection().portfolio_points[-1].external_cash_flow == 0
    assert snapshot.portfolio.pnl == 0


def test_public_reads_are_bounded_and_bad_counts_or_timestamps_are_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        requested = 0

        def __enter__(self):
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self, count: int) -> bytes:
            self.requested = count
            return b"{}"

    response = Response()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: response)
    _transport(urllib.request.Request(PUBLIC_DATA_HOST), 1)
    assert response.requested == MAX_RESPONSE_BYTES + 1

    too_many = json.dumps(
        [
            _row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1)),
            _row(NOW - timedelta(minutes=1), NOW),
        ]
    ).encode()
    with pytest.raises(BinanceDataError, match="requested limit"):
        BinancePublicClient(transport=lambda _r, _t: too_many).fetch_klines(
            "BTCUSDT", Timeframe.M1, limit=1
        )
    overflow = _row(NOW - timedelta(minutes=1), NOW)
    overflow[0] = 10**100
    with pytest.raises(BinanceDataError, match="epoch milliseconds"):
        BinancePublicClient(transport=lambda _r, _t: json.dumps([overflow]).encode()).fetch_klines(
            "BTCUSDT", Timeframe.M1, limit=1
        )


def test_concurrent_activation_reserves_one_immutable_lane(tmp_path: Path) -> None:
    store = PaperStore(root=tmp_path)
    barrier = threading.Barrier(2)
    configs = (_config(_gate(), spec_variant="a"), _config(_gate(), spec_variant="b"))

    def activate(config: PaperRuntimeConfig) -> Exception | None:
        runner = PaperRunner(store, _InjectedClient(()), clock=lambda: NOW)  # type: ignore[arg-type]
        barrier.wait()
        try:
            runner.activate((config,))
        except Exception as error:  # noqa: BLE001 - the rejected contender is the assertion
            return error
        return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(activate, configs))
    assert sum(result is None for result in results) == 1
    assert sum(result is not None for result in results) == 1
    assert (
        sum(
            event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
            for event in store.current_projection().events
        )
        == 1
    )


def test_recovered_failure_in_same_bucket_gets_a_new_incident_generation(
    tmp_path: Path,
) -> None:
    clock = [NOW]
    client = _MutableClient((_priced_row(NOW - timedelta(minutes=1), NOW, "99"),), clock)
    client.fail_klines = True
    runner = PaperRunner(PaperStore(root=tmp_path), client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((_config(_gate(), triggered=True),))
    first = runner.run_once().attention[0]
    clock[0] += timedelta(seconds=5)
    client.fail_klines = False
    assert runner.run_once().attention == ()
    clock[0] += timedelta(seconds=5)
    client.fail_klines = True
    second = runner.run_once().attention[0]
    assert second.item_id != first.item_id


def test_persisted_position_older_than_warmup_can_exit(tmp_path: Path) -> None:
    spec = CanonicalStrategySpec(
        strategy_id="STRAT-long-held",
        family="transition",
        inputs=("open", "high", "low", "close", "volume"),
        indicators=(),
        entry_long=RuleTree("all", (Comparison("close", ">", "100.5"),)),
        exit_long=RuleTree("all", (Comparison("close", "<", "99.5"),)),
        position_sizing={"type": "fixed_amount"},
        risk={},
    )
    config = PaperRuntimeConfig(
        VERSION,
        spec,
        "BTCUSDT",
        Timeframe.M1,
        _gate(),
        "APPROVED",
        ApprovalId("APR-paper-validation"),
        EVIDENCE,
    )
    clock = [NOW]
    client = _MutableClient(
        (
            _priced_row(NOW - timedelta(minutes=2), NOW - timedelta(minutes=1), "99"),
            _priced_row(NOW - timedelta(minutes=1), NOW, "101"),
        ),
        clock,
    )
    runner = PaperRunner(PaperStore(root=tmp_path), client, clock=lambda: clock[0])  # type: ignore[arg-type]
    runner.activate((config,))
    assert len(runner.run_once().positions) == 1

    clock[0] += timedelta(minutes=200)
    client.rows = tuple(
        _priced_row(
            clock[0] - timedelta(minutes=200 - index),
            clock[0] - timedelta(minutes=199 - index),
            "99" if index == 199 else "100",
        )
        for index in range(200)
    )
    assert runner.run_once().positions == ()


def test_decimal_identity_is_context_independent_and_policy_is_activation_bound(
    tmp_path: Path,
) -> None:
    base = _config(_gate())

    def allocated(value: str) -> PaperRuntimeConfig:
        return PaperRuntimeConfig(
            base.strategy_version_ref,
            base.spec,
            base.symbol,
            base.timeframe,
            base.gate,
            base.validation_status,
            base.validation_approval_ref,
            base.validation_evidence_refs,
            Decimal(value),
        )

    with localcontext() as context:
        context.prec = 3
        assert allocated("1000").config_digest == allocated("1000.00").config_digest
        assert allocated("999").config_digest != allocated("999.000000000000000001").config_digest

    store = PaperStore(root=tmp_path)
    PaperRunner(store, _InjectedClient(()), clock=lambda: NOW).activate((base,))  # type: ignore[arg-type]
    started = next(
        event
        for event in store.current_projection().events
        if event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
    )
    assert set(started.payload["risk_policy"]) == set(PaperRiskPolicy.__dataclass_fields__)
    assert isinstance(started.payload["policy_sha256"], str)
    changed = PaperRunner(
        store,
        _InjectedClient(()),  # type: ignore[arg-type]
        policy=PaperRiskPolicy(fee_bps=Decimal("11")),
        clock=lambda: NOW,
    )
    with pytest.raises(PaperGateError, match="substitution"):
        changed.activate((base,))


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("price", "-1"),
        ("quantity", "0"),
        ("fee", "-1"),
        ("cash_after", "-1"),
        ("position_quantity_after", "-1"),
        ("position_cost_after", "-1"),
        ("fees_after", "-1"),
        ("notional", "1e1000"),
    ),
)
def test_fill_decimal_sign_and_magnitude_are_validated(
    tmp_path: Path, field: str, value: str
) -> None:
    payload = {
        "signal_id": "SIG-invalid-fill",
        "fill_id": "FILL-invalid-fill",
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "side": "BUY",
        "price": "100",
        "quantity": "1",
        "notional": "100",
        "fee": "0.1",
        "cash_after": "9899.9",
        "position_quantity_after": "1",
        "position_cost_after": "100.1",
        "realized_pnl_after": "0",
        "fees_after": "0.1",
    }
    payload[field] = value
    with pytest.raises(PaperStoreError):
        PaperStore(root=tmp_path).append_event(
            PaperEventType.FILL,
            "PAPERBOT-invalid",
            payload,
            idempotency_key=f"invalid-fill-{field}",
            occurred_at=NOW,
        )


def test_database_and_lock_hardlinks_are_rejected(tmp_path: Path) -> None:
    database_root = tmp_path / "database"
    database_root.mkdir()
    database = PaperStore(root=database_root)
    database.initialize()
    os.link(database.path, database.path.with_name("database-alias.sqlite3"))
    with pytest.raises(PaperStoreError, match="hardlink"):
        database.current_projection()

    lock_root = tmp_path / "lock"
    lock_root.mkdir()
    lock = PaperStore(root=lock_root)
    lock.initialize()
    os.link(lock.lock_path, lock.lock_path.with_name("lock-alias"))
    with pytest.raises(PaperStoreError, match="hardlink"):
        lock.current_projection()


@pytest.mark.parametrize("lock_kind", ["database", "runner"])
def test_fifo_lock_validation_never_unlocks_an_unacquired_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lock_kind: str,
) -> None:
    store = PaperStore(root=tmp_path)
    store.initialize()
    path = store.lock_path if lock_kind == "database" else store.runner_lock_path
    if path.exists():
        path.unlink()
    os.mkfifo(path)
    real_flock = paper_store_module.fcntl.flock

    def guarded_flock(descriptor: int, operation: int) -> object:
        if operation == paper_store_module.fcntl.LOCK_UN:
            raise AssertionError("unlock attempted before a lease was acquired")
        return real_flock(descriptor, operation)

    monkeypatch.setattr(paper_store_module.fcntl, "flock", guarded_flock)
    started = time.monotonic()

    with pytest.raises(PaperStoreError, match="lock identity changed"):
        if lock_kind == "database":
            store.current_projection()
        else:
            with store.runner_lease():
                pass

    assert time.monotonic() - started < 1
    assert stat.S_ISFIFO(os.lstat(path).st_mode)


def test_runner_loads_full_projection_once_per_bot_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = PaperStore(root=tmp_path)
    runner = PaperRunner(
        store,
        _InjectedClient((_priced_row(NOW - timedelta(minutes=1), NOW, "99"),)),
        clock=lambda: NOW,  # type: ignore[arg-type]
    )
    runner.activate((_config(_gate(), triggered=True),))
    calls = 0
    current_projection = store.current_projection

    def counted():  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return current_projection()

    monkeypatch.setattr(store, "current_projection", counted)
    runner.run_once()
    assert calls == 2  # one cycle load plus the returned snapshot


def test_buy_commit_rechecks_pause_and_portfolio_time_is_monotonic(tmp_path: Path) -> None:
    store = PaperStore(root=tmp_path)
    store.set_entries_paused(
        True, actor="operator", idempotency_key="pause-before-buy", occurred_at=NOW
    )
    committed = store.commit_cycle(
        (
            PaperEventWrite(
                PaperEventType.SIGNAL,
                "PAPERBOT-paused",
                {
                    "signal_id": "SIG-paused-buy",
                    "symbol": "BTCUSDT",
                    "timeframe": "1m",
                    "side": "BUY",
                    "rationale": "ENTRY_LONG",
                },
                "signal:paused-buy",
                NOW,
            ),
        ),
        recorded_at=NOW,
        require_entries_unpaused=True,
    )
    assert committed is False
    assert not any(
        event.event_type is PaperEventType.SIGNAL for event in store.current_projection().events
    )

    store.append_portfolio_point(
        idempotency_key="monotonic-newer",
        observed_at=NOW,
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        exposure=Decimal(0),
        realized_pnl=Decimal(0),
        unrealized_pnl=Decimal(0),
        fees=Decimal(0),
    )
    with pytest.raises(PaperStoreError, match="monotonic"):
        store.append_portfolio_point(
            idempotency_key="monotonic-older",
            observed_at=NOW - timedelta(seconds=1),
            equity=Decimal("10000"),
            cash=Decimal("10000"),
            exposure=Decimal(0),
            realized_pnl=Decimal(0),
            unrealized_pnl=Decimal(0),
            fees=Decimal(0),
        )


@pytest.mark.parametrize(
    "changed_policy",
    (
        PaperRiskPolicy(fee_bps=Decimal("11")),
        PaperRiskPolicy(starting_capital=Decimal("20000")),
    ),
)
def test_new_lane_must_match_store_wide_portfolio_policy(
    tmp_path: Path, changed_policy: PaperRiskPolicy
) -> None:
    store = PaperStore(root=tmp_path)
    PaperRunner(store, _InjectedClient(()), clock=lambda: NOW).activate(  # type: ignore[arg-type]
        (_config(_gate()),)
    )
    second = StrategyVersionId("SV-STRAT-shared-policy-v2")
    drifted = PaperRunner(
        store,
        _InjectedClient(()),  # type: ignore[arg-type]
        policy=changed_policy,
        clock=lambda: NOW,
    )
    with pytest.raises(PaperGateError, match="shared portfolio policy"):
        drifted.activate(
            (
                _config(
                    _gate(version=second),
                    version=second,
                    symbol="ETHUSDT",
                ),
            )
        )
    assert (
        sum(
            event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
            for event in store.current_projection().events
        )
        == 1
    )


def test_bootstrap_kline_gap_is_unhealthy_and_never_evaluated_or_filled(
    tmp_path: Path,
) -> None:
    rows = (
        _priced_row(NOW - timedelta(minutes=3), NOW - timedelta(minutes=2), "99"),
        _priced_row(NOW - timedelta(minutes=1), NOW, "100"),
    )
    store = PaperStore(root=tmp_path)
    config = _config(_gate(), triggered=True)
    runner = PaperRunner(
        store,
        _InjectedClient(rows),
        clock=lambda: NOW,  # type: ignore[arg-type]
    )
    runner.activate((config,))
    snapshot = runner.run_once()
    projection = store.current_projection()
    assert snapshot.sources[0].status.value != "LIVE" and snapshot.attention
    assert not any(
        event.event_type is PaperEventType.HEARTBEAT
        and event.payload.get("source") == "BINANCE_KLINES"
        for event in projection.events
    )
    assert not any(
        event.event_type is PaperEventType.FILL
        or event.event_type is PaperEventType.BOT
        and event.payload.get("kind") == "EVALUATED"
        for event in projection.events
    )


def test_point_only_bootstrap_state_rejects_restart_with_different_policy(
    tmp_path: Path,
) -> None:
    store = PaperStore(root=tmp_path)
    store.append_portfolio_point(
        idempotency_key="paper-portfolio-initial-v1",
        observed_at=NOW,
        equity=Decimal("10000"),
        cash=Decimal("10000"),
        exposure=Decimal(0),
        realized_pnl=Decimal(0),
        unrealized_pnl=Decimal(0),
        fees=Decimal(0),
    )
    restarted = PaperRunner(
        store,
        _InjectedClient(()),  # type: ignore[arg-type]
        policy=PaperRiskPolicy(fee_bps=Decimal("11")),
        clock=lambda: NOW,
    )
    with pytest.raises(PaperGateError, match="without retained activation"):
        restarted.activate((_config(_gate()),))
    assert not store.current_projection().events


def test_first_activation_is_one_atomic_idempotent_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = PaperStore(root=tmp_path)
    commits = 0
    commit_cycle = store.commit_cycle

    def counted(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal commits
        commits += 1
        return commit_cycle(*args, **kwargs)

    monkeypatch.setattr(store, "commit_cycle", counted)
    runner = PaperRunner(store, _InjectedClient(()), clock=lambda: NOW)  # type: ignore[arg-type]
    config = _config(_gate())
    runner.activate((config,))
    runner.activate((config,))
    projection = store.current_projection()
    assert commits == 1
    assert len(projection.portfolio_points) == 1
    assert (
        sum(
            event.event_type is PaperEventType.BOT and event.payload.get("kind") == "STARTED"
            for event in projection.events
        )
        == 1
    )
