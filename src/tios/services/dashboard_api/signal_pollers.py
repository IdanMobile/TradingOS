"""Outbound pollers that turn real external market APIs into signals_inbox records.

Unlike `signals_inbox.ingest_signal` (a webhook we receive), these pollers make
outbound HTTPS calls (we call them) — no server exposure beyond loopback is needed.

Active by default (genuinely free, no signup, no API key):
- Fear & Greed Index (alternative.me) — market-wide sentiment.
- CoinGecko 24h momentum — per-coin price change, keyless public API.
- Binance 24h momentum — same idea, second independent exchange/data provider,
  keyless public endpoint (this project already uses Binance elsewhere for data).
- Canonical ETH volume-breakout rule (canonical_signal_poller.py) — an independent
  live computation of this project's real STRAT-ETH-volume-breakout-prospective-v1
  rule across the whole watchlist. Explicitly NOT the frozen/reviewed reproduction
  pipeline and NOT a preregistered prospective observation — see that module's
  docstring for why (Environment has no "live" value in this codebase).

Not active by default: Whale Alert and LunarCrush both require a paid plan for the
endpoints this module needs — confirmed live (LunarCrush: every endpoint tried, incl.
/public/coins/list/v2, /public/coins/:coin/v1, /public/topic/:topic/v1, returned
402 "You must have an active Individual or higher subscription", even with a valid
key). Both pollers are kept implemented and correct against the real API, just
excluded from `_POLLERS` per an explicit "free tiers only" decision. Re-add either
with its env var if you get a paid plan.

Every mapping from raw provider data to a BUY/SELL/HOLD action is a simple, documented
heuristic, not certainty — the rationale text always states the raw numbers and the
heuristic used, so the inference is auditable rather than a black box.

Each signal also carries, where the source actually has it: network (which chain the
asset settles on), strategy (short label for the heuristic), timeframe, entry_price,
and stop_loss/take_profit. The latter three are a fixed ±5%/±10% percentage scaffold
(`_risk_levels`) — not derived from volatility, ATR, or any backtest. A field a source
can't honestly derive is left unset rather than filled with an invented number.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tios.services.dashboard_api.canonical_signal_poller import (
    _SOURCE as _CANONICAL_ETH_RULE_SOURCE,
)
from tios.services.dashboard_api.signals_inbox import append_polled_signal, build_signals

_WHALE_ALERT_URL = "https://api.whale-alert.io/v1/transactions"
_WHALE_ALERT_SOURCE = "Whale Alert (on-chain)"
_WHALE_ALERT_MIN_VALUE_USD = 500_000  # paid-tier floor
_WHALE_ALERT_LOOKBACK_SECONDS = 3600  # paid-tier historical limit
_WHALE_ALERT_LIMIT = 20

_LUNARCRUSH_URL = "https://lunarcrush.com/api4/public/coins/list/v2"
_LUNARCRUSH_SOURCE = "LunarCrush (sentiment)"
_LUNARCRUSH_WATCHLIST = {"BTC", "ETH", "SOL", "BNB", "ADA", "DOGE", "AVAX", "LINK"}
_LUNARCRUSH_COOLDOWN_SECONDS = 300  # avoid spamming a fresh snapshot every click

_FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
_FEAR_GREED_SOURCE = "Fear & Greed Index (free)"
_FEAR_GREED_COOLDOWN_SECONDS = 3600  # index typically updates roughly once a day

_COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"
_COINGECKO_SOURCE = "CoinGecko 24h momentum (free)"
_COINGECKO_COOLDOWN_SECONDS = 900
# CoinGecko needs its own coin-id slugs, not tickers.
_COINGECKO_WATCHLIST = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB",
    "cardano": "ADA",
    "dogecoin": "DOGE",
    "avalanche-2": "AVAX",
    "chainlink": "LINK",
}

_BINANCE_URL = "https://api.binance.com/api/v3/ticker/24hr"
_BINANCE_SOURCE = "Binance 24h momentum (free)"
_BINANCE_COOLDOWN_SECONDS = 900
_BINANCE_WATCHLIST = {
    "BTCUSDT": "BTC",
    "ETHUSDT": "ETH",
    "SOLUSDT": "SOL",
    "BNBUSDT": "BNB",
    "ADAUSDT": "ADA",
    "DOGEUSDT": "DOGE",
    "AVAXUSDT": "AVAX",
    "LINKUSDT": "LINK",
}

# Which chain each watchlisted asset actually settles on — real, static facts, not
# a data feed. LINK is an ERC-20 token, not its own base layer.
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

# Simple, fixed percentage risk scaffold — NOT derived from volatility, ATR, or any
# backtest. It exists so a BUY/SELL signal has a concrete illustrative level attached
# instead of none at all. Documented here so the number in the UI is auditable.
_RISK_STOP_PCT = 0.05
_RISK_TAKE_PROFIT_PCT = (0.05, 0.10)


def _risk_levels(entry_price: float | None, action: str) -> tuple[float | None, list[float] | None]:
    if entry_price is None or action not in ("BUY", "SELL"):
        return None, None
    sign = 1 if action == "BUY" else -1
    stop_loss = entry_price * (1 - sign * _RISK_STOP_PCT)
    take_profit = [entry_price * (1 + sign * pct) for pct in _RISK_TAKE_PROFIT_PCT]
    return stop_loss, take_profit


# "Signal strength": 0-100, how far past its own trigger threshold a reading is —
# NOT a probability, NOT backtested accuracy (no outcome-tracking exists yet). The
# scale endpoints (e.g. "20% move = max strength" for momentum) are disclosed
# heuristic reference points, not statistically derived. See signals_inbox.py's
# `_signal_strength` docstring for the honesty framing this exists to preserve.
_MOMENTUM_STRENGTH_MAX_PCT = 20.0  # a 24h move this large or larger reads as "max strength"


def _momentum_strength(change_pct: float, threshold_pct: float) -> float:
    span = _MOMENTUM_STRENGTH_MAX_PCT - threshold_pct
    return round(min(100.0, max(0.0, (abs(change_pct) - threshold_pct) / span * 100)), 1)


def _fear_greed_strength(value: int, action: str) -> float | None:
    if action == "BUY":  # value <= 25; 0 is the most extreme possible fear reading
        return round((25 - value) / 25 * 100, 1)
    if action == "SELL":  # value >= 75; 100 is the most extreme possible greed reading
        return round((value - 75) / 25 * 100, 1)
    return None


def _get_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 10) -> Any:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read())


def _last_seen(root: Path, source: str) -> str | None:
    for entry in build_signals(root)["sources"]:
        if entry["name"] == source:
            return entry["last_received_at"] or None
    return None


def _seconds_since_last_seen(root: Path, source: str) -> float | None:
    last_seen = _last_seen(root, source)
    if not last_seen:
        return None
    try:
        return datetime.now(tz=UTC).timestamp() - datetime.fromisoformat(last_seen).timestamp()
    except ValueError:
        return None


def poll_fear_greed(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Free, keyless. Return (new signal dicts, error message or None)."""
    age = _seconds_since_last_seen(root, _FEAR_GREED_SOURCE)
    if age is not None and age < _FEAR_GREED_COOLDOWN_SECONDS:
        return [], None
    try:
        payload = _get_json(_FEAR_GREED_URL)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        return [], f"Fear & Greed poll failed: {error}"
    entries = payload.get("data") or []
    if not entries:
        return [], "Fear & Greed poll returned no data"
    entry = entries[0]
    try:
        value = int(entry["value"])
    except (KeyError, TypeError, ValueError):
        return [], "Fear & Greed poll returned a malformed value"
    classification = entry.get("value_classification", "Unknown")
    try:
        observed_at = datetime.fromtimestamp(int(entry["timestamp"]), tz=UTC).isoformat()
    except (KeyError, TypeError, ValueError):
        observed_at = None  # alternative.me's own timestamp for this reading was unparseable
    if value <= 25:
        action = "BUY"
        note = "contrarian: extreme fear often marks local bottoms"
    elif value >= 75:
        action = "SELL"
        note = "contrarian: extreme greed often precedes pullbacks"
    else:
        action = "HOLD"
        note = "neither extreme — no contrarian edge"
    return [
        {
            "source": _FEAR_GREED_SOURCE,
            "symbol": "BTC",
            "action": action,
            "rationale": (
                f"index {value}/100 ({classification}) — {note} "
                "(heuristic threshold, not certainty; market-wide index applied to BTC)"
            ),
            "network": _ASSET_NETWORK.get("BTC"),
            "strategy": "Fear & Greed contrarian (index <=25 or >=75 only)",
            "timeframe": "medium-term (index updates ~once/day)",
            "signal_strength": _fear_greed_strength(value, action),
            "observed_at": observed_at,  # alternative.me's own timestamp for this reading
            # No entry_price/stop_loss/take_profit: this is a market-wide index
            # reading, not a price level — inventing one here would misrepresent it.
        }
    ], None


def poll_coingecko_momentum(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Free, keyless. Return (new signal dicts, error message or None)."""
    age = _seconds_since_last_seen(root, _COINGECKO_SOURCE)
    if age is not None and age < _COINGECKO_COOLDOWN_SECONDS:
        return [], None
    params = {
        "vs_currency": "usd",
        "ids": ",".join(_COINGECKO_WATCHLIST),
        "price_change_percentage": "24h",
    }
    url = f"{_COINGECKO_URL}?{urllib.parse.urlencode(params)}"
    try:
        coins = _get_json(url)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        return [], f"CoinGecko poll failed: {error}"
    if not isinstance(coins, list):
        detail = (
            coins.get("error", "unexpected response shape")
            if isinstance(coins, dict)
            else "unexpected response shape"
        )
        return [], f"CoinGecko error: {detail}"
    records = []
    for coin in coins:
        coin_id = coin.get("id")
        symbol = _COINGECKO_WATCHLIST.get(coin_id)
        change = coin.get("price_change_percentage_24h")
        entry_price = coin.get("current_price")
        if symbol is None or change is None:
            continue
        if change >= 5:
            action = "BUY"
        elif change <= -5:
            action = "SELL"
        else:
            action = "HOLD"
        stop_loss, take_profit = _risk_levels(entry_price, action)
        records.append(
            {
                "source": _COINGECKO_SOURCE,
                "symbol": symbol,
                "action": action,
                "rationale": (f"{change:+.2f}% over 24h (heuristic ±5% threshold, not certainty)"),
                "network": _ASSET_NETWORK.get(symbol),
                "strategy": "24h momentum threshold (±5%)",
                "timeframe": "short-term (24h-based)",
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "signal_strength": _momentum_strength(change, 5.0) if action != "HOLD" else None,
                "observed_at": coin.get("last_updated"),  # CoinGecko's own timestamp, not poll time
            }
        )
    return records, None


def poll_binance_momentum(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Free, keyless. Second independent price source alongside CoinGecko."""
    age = _seconds_since_last_seen(root, _BINANCE_SOURCE)
    if age is not None and age < _BINANCE_COOLDOWN_SECONDS:
        return [], None
    symbols_param = json.dumps(list(_BINANCE_WATCHLIST), separators=(",", ":"))
    url = f"{_BINANCE_URL}?{urllib.parse.urlencode({'symbols': symbols_param})}"
    try:
        tickers = _get_json(url)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        return [], f"Binance poll failed: {error}"
    if not isinstance(tickers, list):
        message = (
            tickers.get("msg", "unexpected response shape")
            if isinstance(tickers, dict)
            else "unexpected response shape"
        )
        return [], f"Binance error: {message}"
    records = []
    for ticker in tickers:
        symbol = _BINANCE_WATCHLIST.get(ticker.get("symbol", ""))
        if symbol is None:
            continue
        try:
            change = float(ticker["priceChangePercent"])
            entry_price = float(ticker["lastPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            observed_at = datetime.fromtimestamp(ticker["closeTime"] / 1000, tz=UTC).isoformat()
        except (KeyError, TypeError, ValueError):
            observed_at = None  # Binance's own window-close timestamp was unparseable
        if change >= 5:
            action = "BUY"
        elif change <= -5:
            action = "SELL"
        else:
            action = "HOLD"
        stop_loss, take_profit = _risk_levels(entry_price, action)
        records.append(
            {
                "source": _BINANCE_SOURCE,
                "symbol": symbol,
                "action": action,
                "rationale": (
                    f"{change:+.2f}% over 24h on Binance (heuristic ±5% threshold, not certainty)"
                ),
                "network": _ASSET_NETWORK.get(symbol),
                "strategy": "24h momentum threshold (±5%)",
                "timeframe": "short-term (24h-based)",
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "signal_strength": _momentum_strength(change, 5.0) if action != "HOLD" else None,
                "observed_at": observed_at,
            }
        )
    return records, None


def poll_whale_alert(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Not active by default (paid tier) — kept implemented for a future re-enable."""
    api_key = os.environ.get("WHALE_ALERT_API_KEY")
    if not api_key:
        return [], None
    now = int(datetime.now(tz=UTC).timestamp())
    start = now - _WHALE_ALERT_LOOKBACK_SECONDS
    last_seen = _last_seen(root, _WHALE_ALERT_SOURCE)
    if last_seen:
        try:
            start = max(start, int(datetime.fromisoformat(last_seen).timestamp()))
        except ValueError:
            pass
    params = {
        "api_key": api_key,
        "start": start,
        "min_value": _WHALE_ALERT_MIN_VALUE_USD,
        "limit": _WHALE_ALERT_LIMIT,
    }
    url = f"{_WHALE_ALERT_URL}?{urllib.parse.urlencode(params)}"
    try:
        payload = _get_json(url)
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        return [], f"Whale Alert poll failed: {error}"
    if payload.get("result") != "success":
        return [], f"Whale Alert error: {payload.get('message', 'unknown error')}"
    records = []
    for tx in payload.get("transactions", []):
        from_type = (tx.get("from") or {}).get("owner_type", "unknown")
        to_type = (tx.get("to") or {}).get("owner_type", "unknown")
        if to_type == "exchange" and from_type != "exchange":
            action, note = (
                "SELL",
                "large transfer INTO an exchange — often precedes selling pressure",
            )
        elif from_type == "exchange" and to_type != "exchange":
            action, note = "BUY", "large transfer OUT of an exchange — often reflects accumulation"
        else:
            action, note = "HOLD", "wallet-to-wallet or exchange-to-exchange — no clear direction"
        symbol = str(tx.get("symbol", "UNKNOWN")).upper()
        amount_usd = tx.get("amount_usd") or 0
        records.append(
            {
                "source": _WHALE_ALERT_SOURCE,
                "symbol": symbol,
                "action": action,
                "rationale": (
                    f"${amount_usd:,.0f} {symbol} on {tx.get('blockchain', '?')} — {note} "
                    "(heuristic from exchange-flow direction, not certainty)"
                ),
                "network": str(tx.get("blockchain", "")).title() or None,
                "strategy": "exchange-flow direction heuristic",
                "timeframe": "event-driven (single large transaction)",
                # No entry_price/stop_loss/take_profit: a transaction event, not a
                # price-level signal.
            }
        )
    return records, None


def poll_lunarcrush(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Not active by default (paid plan required) — kept implemented for a future re-enable."""
    api_key = os.environ.get("LUNARCRUSH_API_KEY")
    if not api_key:
        return [], None
    age = _seconds_since_last_seen(root, _LUNARCRUSH_SOURCE)
    if age is not None and age < _LUNARCRUSH_COOLDOWN_SECONDS:
        return [], None
    try:
        payload = _get_json(_LUNARCRUSH_URL, headers={"Authorization": f"Bearer {api_key}"})
    except (urllib.error.URLError, OSError, ValueError, TimeoutError) as error:
        return [], f"LunarCrush poll failed: {error}"
    records = []
    for coin in payload.get("data", []):
        symbol = str(coin.get("symbol", "")).upper()
        if symbol not in _LUNARCRUSH_WATCHLIST:
            continue
        sentiment = coin.get("sentiment")
        galaxy_score = coin.get("galaxy_score")
        if sentiment is None or galaxy_score is None:
            continue
        if sentiment >= 75 and galaxy_score >= 60:
            action = "BUY"
        elif sentiment <= 35:
            action = "SELL"
        else:
            action = "HOLD"
        records.append(
            {
                "source": _LUNARCRUSH_SOURCE,
                "symbol": symbol,
                "action": action,
                "rationale": (
                    f"sentiment {sentiment}/100, galaxy score {galaxy_score}/100 "
                    "(heuristic thresholds, not certainty)"
                ),
                "network": _ASSET_NETWORK.get(symbol),
                "strategy": "sentiment + Galaxy Score thresholds",
                "timeframe": "medium-term (social sentiment lag)",
                # No entry_price on this endpoint's response — never verified live
                # (402 on every attempt), so no field name to trust.
            }
        )
    return records, None


def _poll_canonical_eth_rule(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    # Deferred import: canonical_signal_poller imports back from this module
    # (_seconds_since_last_seen), so importing it at module load time would cycle.
    from tios.services.dashboard_api.canonical_signal_poller import poll_canonical_eth_rule

    return poll_canonical_eth_rule(root)


# (source name, poll function, required env var — None means always active/free)
_POLLERS: tuple[tuple[str, Any, str | None], ...] = (
    (_FEAR_GREED_SOURCE, poll_fear_greed, None),
    (_COINGECKO_SOURCE, poll_coingecko_momentum, None),
    (_BINANCE_SOURCE, poll_binance_momentum, None),
    (_CANONICAL_ETH_RULE_SOURCE, _poll_canonical_eth_rule, None),
    # Whale Alert and LunarCrush intentionally excluded — both confirmed paid-only
    # for the endpoints this module needs. See module docstring.
)


def poll_all_sources(root: Path) -> dict[str, Any]:
    """Poll every registered source, append new signals, and summarize the run."""
    from tios.services.dashboard_api.signal_reliability import resolve_pending_outcomes

    added: dict[str, int] = {}
    configured: dict[str, bool] = {}
    errors: list[str] = []
    for source, poller, env_var in _POLLERS:
        configured[source] = env_var is None or bool(os.environ.get(env_var))
        records, error = poller(root)
        for record in records:
            append_polled_signal(root, **record)
        added[source] = len(records)
        if error:
            errors.append(error)
    resolved_outcomes = resolve_pending_outcomes(root)
    return {
        "schema_version": 1,
        "added": added,
        "configured": configured,
        "errors": errors,
        "total_added": sum(added.values()),
        "resolved_outcomes": resolved_outcomes,
    }
