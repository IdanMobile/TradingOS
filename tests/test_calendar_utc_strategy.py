from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from tios.strategy.evaluator import StrategyEvaluationError, evaluate_strategy_signals
from tios.strategy.spec import parse_spec
from tios.strategy.validator import validate
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
SPEC_PATH = ROOT / "strategies/research/calendar-utc-weekday/canonical_strategy_spec.yaml"
CREATED_AT = datetime(2026, 7, 13, tzinfo=UTC)
PROVENANCE = Provenance((DomainRef("EV-calendar-utc-unit"),))


def _spec():  # type: ignore[no-untyped-def]
    return parse_spec(yaml.safe_load(SPEC_PATH.read_text()))


def _bars(timeframe: Timeframe = Timeframe.H1) -> tuple[MarketBar, ...]:
    market = Market(
        MarketName("CRYPTO_SPOT"),
        VenueFamily("BINANCE_SPOT"),
        InstrumentId("BTC-USDT.BINANCE_SPOT"),
        timeframe,
        DatasetId("DS-calendar-utc-unit"),
    )
    start = datetime(2026, 7, 12, 22, tzinfo=UTC)
    return tuple(
        MarketBar(
            market=market,
            open_time=opened,
            close_time=opened + timedelta(hours=1) - timedelta(microseconds=1),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=Decimal("1"),
            created_at=CREATED_AT,
            creator_type=CreatorType.SYSTEM,
            provenance=PROVENANCE,
        )
        for opened in (start + timedelta(hours=index) for index in range(51))
    )


def _signals(spec=None, bars=None):  # type: ignore[no-untyped-def]
    return evaluate_strategy_signals(
        spec=spec or _spec(),
        bars=bars or _bars(),
        strategy_version_ref=StrategyVersionId("SV-calendar-utc-unit"),
        run_ref=RunId("RUN-calendar-utc-unit"),
        created_at=CREATED_AT,
        creator_type=CreatorType.SYSTEM,
        provenance=PROVENANCE,
    )


def test_calendar_strategy_is_valid_and_emits_only_monday_boundaries() -> None:
    payload = yaml.safe_load(SPEC_PATH.read_text())
    assert validate(payload).verdict == "VALID"

    signals = _signals()
    assert [(signal.side, signal.observed_at) for signal in signals] == [
        (Side.BUY, datetime(2026, 7, 12, 23, 59, 59, 999999, tzinfo=UTC)),
        (Side.SELL, datetime(2026, 7, 13, 23, 59, 59, 999999, tzinfo=UTC)),
    ]


def test_calendar_strategy_is_price_independent() -> None:
    original = _bars()
    mutated = tuple(
        MarketBar(
            market=bar.market,
            open_time=bar.open_time,
            close_time=bar.close_time,
            open=Decimal("200"),
            high=Decimal("210"),
            low=Decimal("190"),
            close=Decimal("205"),
            volume=Decimal("2"),
            created_at=bar.created_at,
            creator_type=bar.creator_type,
            provenance=bar.provenance,
        )
        for bar in original
    )
    assert [(item.side, item.observed_at) for item in _signals(bars=original)] == [
        (item.side, item.observed_at) for item in _signals(bars=mutated)
    ]


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"selected_weekday": 7, "timezone": "UTC"}, "selected_weekday"),
        ({"selected_weekday": True, "timezone": "UTC"}, "selected_weekday"),
        ({"selected_weekday": 0, "timezone": "Asia/Jerusalem"}, "timezone must be UTC"),
    ],
)
def test_calendar_strategy_fails_closed_on_invalid_parameters(parameters, message) -> None:  # type: ignore[no-untyped-def]
    payload = yaml.safe_load(SPEC_PATH.read_text())
    payload["indicators"][0]["parameters"] = parameters
    with pytest.raises(StrategyEvaluationError, match=message):
        _signals(spec=parse_spec(payload))


def test_calendar_strategy_rejects_non_hourly_bars() -> None:
    with pytest.raises(StrategyEvaluationError, match="requires 1h bars"):
        _signals(bars=_bars(Timeframe.M5))
