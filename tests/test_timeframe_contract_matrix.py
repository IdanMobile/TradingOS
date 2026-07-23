from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pytest
import yaml

from tios.dataset.quality import check_spacing, missing_intervals
from tios.services.paper import (
    BinanceBookTicker,
    BinanceKline,
    PaperEventType,
    PaperRunner,
    PaperRuntimeConfig,
    PaperStore,
)
from tios.strategy.evaluator import StrategyEvaluationError, evaluate_strategy_signals
from tios.strategy.spec import CanonicalStrategySpec, Comparison, Indicator, RuleTree, parse_spec
from tios.trading_domain import (
    ApprovalId,
    CreatorType,
    DatasetId,
    DomainRef,
    InstrumentId,
    Market,
    MarketBar,
    MarketName,
    Provenance,
    RunId,
    Side,
    Stage,
    StageGateId,
    StageGateReadinessRecord,
    StageGateRequirement,
    StageGateRequirementKind,
    StageGateStatus,
    StrategyVersionId,
    Timeframe,
    VenueFamily,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "micro"
SEEDS = ROOT / "strategies" / "seed"
NOW = datetime(2026, 7, 12, 12, tzinfo=UTC)
PROVENANCE = Provenance((DomainRef("EV-timeframe-contract-matrix"),))
VERSION = StrategyVersionId("SV-timeframe-contract-matrix")


def _fixture_bars(
    fixture: str,
    timeframe: Timeframe,
    *,
    start: datetime = datetime(2025, 1, 1, tzinfo=UTC),
) -> tuple[MarketBar, ...]:
    market = Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BINANCE_SPOT"),
        InstrumentId("BTC-USDT.BINANCE_SPOT"),
        timeframe,
        DatasetId(f"DS-timeframe-contract-{timeframe.value}"),
    )
    result = []
    with (FIXTURES / fixture).open(newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            opened = start + timedelta(seconds=index * timeframe.seconds)
            result.append(
                MarketBar(
                    market=market,
                    open_time=opened,
                    close_time=opened + timedelta(seconds=timeframe.seconds),
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=Decimal(row["volume_base"]),
                    created_at=NOW,
                    creator_type=CreatorType.SYSTEM,
                    provenance=PROVENANCE,
                )
            )
    return tuple(result)


def _seed_spec(seed: str) -> CanonicalStrategySpec:
    payload = yaml.safe_load((SEEDS / seed / "canonical_strategy_spec.yaml").read_text())
    return parse_spec(payload)


def _signal_ordinals(
    strategy_spec: CanonicalStrategySpec,
    bars: tuple[MarketBar, ...],
) -> tuple[tuple[int, Side], ...]:
    signals = evaluate_strategy_signals(
        spec=strategy_spec,
        bars=bars,
        strategy_version_ref=VERSION,
        run_ref=RunId("RUN-timeframe-contract-matrix"),
        created_at=NOW,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )
    ordinal_by_close = {bar.close_time: index for index, bar in enumerate(bars, start=1)}
    assert all(signal.timeframe is bars[0].market.timeframe for signal in signals)
    assert all(signal.observed_at in ordinal_by_close for signal in signals)
    assert all(
        bars[ordinal_by_close[signal.observed_at] - 1].open_time < signal.observed_at
        for signal in signals
    )
    return tuple((ordinal_by_close[signal.observed_at], signal.side) for signal in signals)


@pytest.mark.parametrize(
    ("seed", "fixture", "expected"),
    [
        ("01-qc-dual-ma-cross", "bars.csv", ((6, Side.BUY), (13, Side.SELL))),
        ("07-pine-bb-strategy", "bars_long.csv", ((21, Side.BUY), (27, Side.SELL))),
    ],
)
def test_fixture_signal_transitions_are_timeframe_agnostic(
    seed: str,
    fixture: str,
    expected: tuple[tuple[int, Side], ...],
) -> None:
    strategy_spec = _seed_spec(seed)
    observed = {
        timeframe: _signal_ordinals(strategy_spec, _fixture_bars(fixture, timeframe))
        for timeframe in Timeframe
    }
    assert set(observed) == set(Timeframe)
    assert all(transitions == expected for transitions in observed.values())


def _calendar_spec() -> CanonicalStrategySpec:
    return CanonicalStrategySpec(
        strategy_id="STRAT-timeframe-calendar-contract",
        family="calendar",
        inputs=("open",),
        indicators=(
            Indicator(
                "utc_weekday_window",
                {"selected_weekday": 0, "timezone": "UTC"},
                ("calendar_entry", "calendar_exit"),
            ),
        ),
        entry_long=RuleTree("all", (Comparison("calendar_entry", "==", "1"),)),
        exit_long=RuleTree("all", (Comparison("calendar_exit", "==", "1"),)),
        position_sizing={"type": "all_in"},
        risk={"execution_authority": "NONE"},
    )


def test_utc_weekday_window_is_valid_only_for_one_hour_bars() -> None:
    hourly = _fixture_bars(
        "bars.csv",
        Timeframe.H1,
        start=datetime(2026, 7, 12, 22, tzinfo=UTC),
    )
    assert _signal_ordinals(_calendar_spec(), hourly) == ((2, Side.BUY),)
    for timeframe in set(Timeframe) - {Timeframe.H1}:
        with pytest.raises(StrategyEvaluationError, match="requires 1h bars"):
            _signal_ordinals(_calendar_spec(), _fixture_bars("bars.csv", timeframe))


@pytest.mark.parametrize("timeframe", list(Timeframe))
def test_quality_spacing_and_missing_intervals_cover_every_timeframe(
    timeframe: Timeframe,
) -> None:
    step = timedelta(seconds=timeframe.seconds)
    start = datetime(2025, 1, 1, tzinfo=UTC)
    gapped = pa.table({"timestamp_open_utc": pa.array((start, start + step, start + 3 * step))})
    malformed = pa.table(
        {"timestamp_open_utc": pa.array((start, start + step + timedelta(seconds=1)))}
    )

    assert check_spacing(gapped, timeframe.value)["status"] == "PASS"
    report = missing_intervals(gapped, timeframe.value)
    assert report["details"]["gap_count"] == 1
    assert report["details"]["missing_bars_total"] == 1
    assert check_spacing(malformed, timeframe.value)["status"] == "FAIL"


def _gate() -> StageGateReadinessRecord:
    requirements = tuple(
        StageGateRequirement(
            code,
            StageGateRequirementKind.HUMAN_DECISION
            if code == "HG_3_APPROVED"
            else StageGateRequirementKind.EVIDENCE,
            True,
            (DomainRef("APR-timeframe-contract"),) if code == "HG_3_APPROVED" else PROVENANCE.refs,
            None,
        )
        for code in (
            "S2_EXIT_PASS",
            "HG_3_APPROVED",
            "COMPLETE_APPROVABLE_STRATEGY_CONTEXT",
            "PAPER_LANE_ARCHITECTURE_DECISION",
            "SECURITY_REVIEW_PASS",
            "SPECIFIC_INTEGRATION_OPERATOR_APPROVAL",
        )
    )
    return StageGateReadinessRecord(
        StageGateId("GATE-timeframe-contract"),
        Stage.S3_PAPER_DEMO,
        DomainRef(str(VERSION)),
        requirements,
        StageGateStatus.APPROVED,
        NOW,
        CreatorType.HUMAN,
        PROVENANCE,
    )


def _paper_config(timeframe: Timeframe) -> PaperRuntimeConfig:
    spec = CanonicalStrategySpec(
        strategy_id="STRAT-timeframe-paper-contract",
        family="buy_and_hold",
        inputs=("open", "high", "low", "close", "volume"),
        indicators=(),
        entry_long=None,
        exit_long=None,
        position_sizing={"type": "fixed_amount"},
        risk={"execution_authority": "NONE"},
        always_in_market=True,
    )
    return PaperRuntimeConfig(
        VERSION,
        spec,
        "BTCUSDT",
        timeframe,
        _gate(),
        "APPROVED",
        ApprovalId("APR-timeframe-contract"),
        PROVENANCE.refs,
    )


class _PaperClient:
    def __init__(self, timeframe: Timeframe, *, gapped: bool) -> None:
        self.timeframe = timeframe
        self.gapped = gapped

    def fetch_book_ticker(self, symbol: str) -> BinanceBookTicker:
        return BinanceBookTicker(
            symbol,
            Decimal("99.99"),
            Decimal("2"),
            Decimal("100.01"),
            Decimal("2"),
            NOW,
        )

    def fetch_klines(
        self,
        symbol: str,
        interval: Timeframe,
        *,
        limit: int,
    ) -> tuple[BinanceKline, ...]:
        assert interval is self.timeframe and limit >= 2
        step = timedelta(seconds=interval.seconds)
        offsets = (3, 1) if self.gapped else (2, 1)
        return tuple(
            BinanceKline(
                symbol,
                interval,
                NOW - offset * step,
                NOW - (offset - 1) * step,
                Decimal("100"),
                Decimal("101"),
                Decimal("99"),
                Decimal("100"),
                Decimal("10"),
            )
            for offset in offsets
        )


@pytest.mark.parametrize("timeframe", list(Timeframe))
def test_paper_closed_bar_and_gap_behavior_cover_every_timeframe(
    tmp_path: Path,
    timeframe: Timeframe,
) -> None:
    healthy_root = tmp_path / "healthy"
    healthy_root.mkdir()
    config = _paper_config(timeframe)
    healthy_store = PaperStore(root=healthy_root)
    healthy = PaperRunner(
        healthy_store,
        _PaperClient(timeframe, gapped=False),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    healthy.activate((config,))
    snapshot = healthy.run_once()
    healthy_events = healthy_store.current_projection().events
    assert snapshot.bots[0].last_evaluated_bar_at == NOW
    assert any(event.event_type is PaperEventType.FILL for event in healthy_events)

    gap_root = tmp_path / "gap"
    gap_root.mkdir()
    gap_store = PaperStore(root=gap_root)
    gapped = PaperRunner(
        gap_store,
        _PaperClient(timeframe, gapped=True),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    gapped.activate((config,))
    gap_snapshot = gapped.run_once()
    gap_events = gap_store.current_projection().events
    assert gap_snapshot.attention
    assert not any(
        event.event_type is PaperEventType.FILL
        or event.event_type is PaperEventType.BOT
        and event.payload.get("kind") == "EVALUATED"
        for event in gap_events
    )
