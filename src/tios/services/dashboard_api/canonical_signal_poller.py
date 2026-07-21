"""Independent, honest live computation of a project canonical strategy rule.

This is deliberately NOT the project's frozen/reviewed reproduction pipeline
(`scripts/verify_eth_volume_breakout_flow.py`) and NOT its governed prospective-
observation framework (`src/tios/services/observations/risk_signal.py`, gated by a
D-080-style preregistration decision before observation starts). Both of those exist
and neither accepts live-polled data: `MarketBar.environment` has exactly one legal
value in this codebase (`Environment.HISTORICAL_RESEARCH`) — there is no "live" value
to construct honestly, and extending that is a real architecture decision, not a
dashboard feature.

So this module takes the narrower, honest path: it reuses the REAL rule definition
(read live from `strategies/research/eth-volume-breakout-prospective/canonical_strategy_spec.yaml`,
so it can't drift from the canonical spec) and the REAL indicator/rule-evaluation code
(`tios.strategy.evaluator`), but runs them against freshly-polled Binance klines using a
lightweight bar object instead of the full `MarketBar`/`Market`/`Provenance` domain
objects — because those are structurally tied to `Environment.HISTORICAL_RESEARCH` and
misusing them for live data would be a false provenance claim.

The rule itself (Donchian(40) breakout + 1.5x volume confirmation) has nothing ETH-
specific in it, so this runs it across the same watchlist as the other pollers — but
every signal is labeled as an independent live computation of the published rule, not
the reviewed reproduction and not a preregistered prospective observation. No position
state is tracked across polls (unlike the canonical evaluator's is_long transition
logic) — each poll evaluates entry/exit conditions independently on the latest bar.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from tios.trading_domain import MarketBar

import yaml

from tios.strategy.evaluator import _indicator_contexts, evaluate_rule_tree
from tios.strategy.spec import parse_spec

_SPEC_PATH = "strategies/research/eth-volume-breakout-prospective/canonical_strategy_spec.yaml"
_SOURCE = "Canonical ETH volume-breakout rule (live/unreviewed)"
_STRATEGY_ID = "STRAT-ETH-volume-breakout-prospective-v1"
_COOLDOWN_SECONDS = 900
_KLINES_URL = "https://api.binance.com/api/v3/klines"
_KLINES_LIMIT = 100  # >> Donchian window(40)+1, plenty of warm-up buffer

_WATCHLIST = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
    "BNBUSDT": "BNB",
    "ADAUSDT": "ADA",
    "DOGEUSDT": "DOGE",
    "AVAXUSDT": "AVAX",
    "LINKUSDT": "LINK",
}
_ASSET_NETWORK = {
    "BTC": "Bitcoin (native)",
    "ETH": "Ethereum (native)",
    "SOL": "Solana (native)",
    "BNB": "BNB Chain (native)",
    "ADA": "Cardano (native)",
    "DOGE": "Dogecoin (native)",
    "AVAX": "Avalanche (native)",
    "LINK": "Ethereum (ERC-20)",
}


@dataclass(frozen=True, slots=True)
class _LiveBar:
    """Just the OHLCV fields the real indicator math actually reads — no Market/
    Environment/Provenance ceremony, since those are structurally frozen-data-only.

    `close_time` is carried separately (defaults to None) so the rule-evaluation
    functions, which only ever touch OHLCV, are unaffected — it exists purely so
    callers can report *when the breakout bar actually closed*, not just when we
    happened to poll for it."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time: Any = None


def _get_json(url: str, *, timeout: float = 10) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def _fetch_bars(symbol: str) -> tuple[_LiveBar, ...]:
    # Binance always includes the still-forming current candle as the last row —
    # the spec's own assumptions require "evaluated only after the 1h bar close",
    # so we drop any row whose close_time hasn't passed yet.
    params = {"symbol": symbol, "interval": "1h", "limit": _KLINES_LIMIT}
    url = f"{_KLINES_URL}?{urllib.parse.urlencode(params)}"
    rows = _get_json(url)
    now_ms = time.time() * 1000
    closed_rows = [row for row in rows if row[6] < now_ms]
    return tuple(
        _LiveBar(
            open=Decimal(row[1]),
            high=Decimal(row[2]),
            low=Decimal(row[3]),
            close=Decimal(row[4]),
            volume=Decimal(row[5]),
            close_time=datetime.fromtimestamp(row[6] / 1000, tz=UTC),
        )
        for row in closed_rows
    )


def _load_spec(root: Path) -> Any:
    raw = yaml.safe_load((root / _SPEC_PATH).read_text(encoding="utf-8"))
    return parse_spec(raw)


# "Signal strength": 0-100, how far past the Donchian band the close actually is —
# NOT a probability. 3% overshoot on a single 1h bar is already a strong break for
# these assets, so it's used as the "max strength" reference point; disclosed
# heuristic, not derived from any backtest. See signals_inbox.py's
# `_signal_strength` docstring for the honesty framing this exists to preserve.
_BREAKOUT_STRENGTH_MAX_OVERSHOOT_PCT = 3.0


def _breakout_strength(action: str, close: float, context: dict[str, Any]) -> float | None:
    if action == "BUY":
        band = float(context["donchian_upper"])
        overshoot_pct = (close - band) / band * 100
    elif action == "SELL":
        band = float(context["donchian_lower"])
        overshoot_pct = (band - close) / band * 100
    else:
        return None
    return round(
        min(100.0, max(0.0, overshoot_pct / _BREAKOUT_STRENGTH_MAX_OVERSHOOT_PCT * 100)), 1
    )


def poll_canonical_eth_rule(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Free, keyless. Return (new signal dicts, error message or None)."""
    from tios.services.dashboard_api.signal_pollers import _seconds_since_last_seen

    age = _seconds_since_last_seen(root, _SOURCE)
    if age is not None and age < _COOLDOWN_SECONDS:
        return [], None
    try:
        spec = _load_spec(root)
    except (OSError, yaml.YAMLError, ValueError) as error:
        return [], f"Canonical rule poll failed to load spec: {error}"

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for pair, symbol in _WATCHLIST.items():
        try:
            bars = _fetch_bars(pair)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
            errors.append(f"{symbol}: {error}")
            continue
        # `_LiveBar` is a deliberate structural subset of `MarketBar` (see its docstring).
        # The cast is safe for this spec specifically: its indicators read only OHLCV.
        # A spec using a calendar indicator would need `open_time` and must not come here.
        contexts = _indicator_contexts(spec, cast("tuple[MarketBar, ...]", bars))
        context = contexts[-1] if contexts else None
        if context is None:
            continue  # not enough warm-up bars yet for this symbol
        entry = evaluate_rule_tree(spec.entry_long, context)
        exit_ = evaluate_rule_tree(spec.exit_long, context)
        if entry:
            action = "BUY"
            note = (
                "Donchian(40) breakout: close above prior 40-bar high, "
                "volume >= 1.5x its 40-bar average"
            )
        elif exit_:
            action = "SELL"
            note = "close back below the prior 40-bar low"
        else:
            action = "HOLD"
            note = "neither the entry breakout nor the exit condition is currently true"
        entry_price = float(bars[-1].close)
        records.append(
            {
                "source": _SOURCE,
                "symbol": symbol,
                "action": action,
                "rationale": (
                    f"{note} (independent live computation of {_STRATEGY_ID}'s published rule; "
                    "not the project's frozen/reviewed reproduction, not a preregistered "
                    "prospective observation, not position-state-tracked across polls)"
                ),
                "network": _ASSET_NETWORK.get(symbol),
                "strategy": f"{_STRATEGY_ID} (Donchian 40 + volume 1.5x) — unreviewed live run",
                "timeframe": "1h bars, evaluated on the latest closed bar",
                "entry_price": entry_price,
                "signal_strength": _breakout_strength(action, entry_price, context),
                # The real bar's own close time — when this breakout actually
                # happened, not when we happened to poll for it.
                "observed_at": bars[-1].close_time.isoformat() if bars[-1].close_time else None,
                # No stop_loss/take_profit: the real spec's risk block is
                # `stop_loss: null, take_profit: null` — exits are rule-driven
                # (see rationale), not a price level. Inventing one would misrepresent
                # the actual strategy.
            }
        )
    # Not named `error`: that name is bound by the `except ... as error` clauses above,
    # and Python unbinds it at the end of each block, so reusing it confuses type checkers.
    combined_error = "; ".join(errors) if errors else None
    return records, combined_error
