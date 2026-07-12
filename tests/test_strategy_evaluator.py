import csv
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from tios.strategy.evaluator import evaluate_strategy_signals
from tios.strategy.spec import CanonicalStrategySpec, parse_spec
from tios.trading_domain import (
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
    StrategyVersionId,
    Timeframe,
    VenueFamily,
)

ROOT = Path(__file__).resolve().parents[1]
SEEDS = ROOT / "strategies/seed"
FIXTURES = ROOT / "fixtures/micro"
CREATED_AT = datetime(2026, 7, 12, tzinfo=UTC)
MARKET = Market(
    MarketName("CRYPTO_SPOT"),
    VenueFamily("BINANCE_SPOT"),
    InstrumentId("BTC-USDT.BINANCE_SPOT"),
    Timeframe.M5,
    DatasetId("DS-strategy-evaluator"),
)
PROVENANCE = Provenance((DomainRef("EV-strategy-evaluator"),))


def spec(seed: str) -> CanonicalStrategySpec:
    payload = yaml.safe_load((SEEDS / seed / "canonical_strategy_spec.yaml").read_text())
    return parse_spec(payload)


def bars(fixture: str) -> tuple[MarketBar, ...]:
    result = []
    with (FIXTURES / fixture).open(newline="") as handle:
        for row in csv.DictReader(handle):
            opened = datetime.fromisoformat(row["timestamp_open_utc"].replace("Z", "+00:00"))
            result.append(
                MarketBar(
                    market=MARKET,
                    open_time=opened,
                    close_time=opened + timedelta(minutes=5),
                    open=Decimal(row["open"]),
                    high=Decimal(row["high"]),
                    low=Decimal(row["low"]),
                    close=Decimal(row["close"]),
                    volume=Decimal(row["volume_base"]),
                    created_at=CREATED_AT,
                    creator_type=CreatorType.SYSTEM,
                    provenance=PROVENANCE,
                )
            )
    return tuple(result)


def signals(seed: str, fixture: str):  # type: ignore[no-untyped-def]
    return evaluate_strategy_signals(
        spec=spec(seed),
        bars=bars(fixture),
        strategy_version_ref=StrategyVersionId("SV-strategy-evaluator"),
        run_ref=RunId("RUN-strategy-evaluator"),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def signal_bars(seed: str, fixture: str) -> list[tuple[int, Side]]:
    fixture_bars = bars(fixture)
    by_time = {bar.close_time: index for index, bar in enumerate(fixture_bars, start=1)}
    return [(by_time[item.observed_at], item.side) for item in signals(seed, fixture)]


def test_canonical_signal_evaluator_reproduces_unambiguous_seed_transitions() -> None:
    assert signal_bars("01-qc-dual-ma-cross", "bars.csv") == [
        (6, Side.BUY),
        (13, Side.SELL),
    ]
    assert signal_bars("02-qc-donchian-breakout", "bars.csv") == [
        (6, Side.BUY),
        (13, Side.SELL),
    ]
    assert signal_bars("07-pine-bb-strategy", "bars_long.csv") == [
        (21, Side.BUY),
        (27, Side.SELL),
    ]
    assert signal_bars("03-ft-sample-strategy", "bars_long.csv") == [
        (23, Side.BUY),
        (25, Side.SELL),
    ]
    assert signal_bars("04-ft-ema-cross", "bars_long.csv") == [
        (10, Side.BUY),
        (11, Side.SELL),
        (12, Side.BUY),
        (13, Side.SELL),
        (14, Side.BUY),
        (15, Side.SELL),
        (16, Side.BUY),
        (17, Side.SELL),
        (18, Side.BUY),
        (19, Side.SELL),
        (20, Side.BUY),
        (21, Side.SELL),
        (26, Side.BUY),
    ]


def test_canonical_signal_evaluator_supports_source_specific_supertrend_semantics() -> None:
    # The fixture never gets within Hummingbot's one-percent proximity threshold.
    assert signal_bars("05-hb-supertrend-directional", "bars_long.csv") == []
    # TradingView uses -1 for a bullish direction, unlike pandas-ta/Hummingbot.
    assert signal_bars("08-pine-supertrend-strategy", "bars_long.csv") == [
        (25, Side.BUY),
    ]


def test_canonical_signal_ids_are_deterministic_and_transition_only() -> None:
    first = signals("07-pine-bb-strategy", "bars_long.csv")
    second = signals("07-pine-bb-strategy", "bars_long.csv")
    assert first == second
    assert [item.rationale_code for item in first] == ["ENTRY_LONG", "EXIT_LONG"]
    assert all(item.instrument == MARKET.instrument for item in first)
