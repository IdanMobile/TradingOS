# Market Data Acquisition Plan

Author view: data-strategy lead, 2026-07-12. Operator approved expansion; this
catalogs the FULL universe of market data before the first pull, so we acquire once
and well. Boundary: free public data can be fetched directly; **paid vendors and
payment/credentials are the operator's to set up — the agent never enters payment
details or API keys.**

Current holdings: BTCUSDT + ETHUSDT spot, 5m/15m/1h OHLCV + volume + taker-buy,
2021-01..2026-06. That is a thin slice of what exists.

---

## The value ladder — what more the market gives us

Ranked by (information gained ÷ cost/effort). ✅ = free public, 💳 = paid/vendor.

### Tier 1 — free, high value, pull now (Binance public data + CoinGecko free)

| Data | Signals it unlocks | Source | Size/effort |
|---|---|---|---|
| ✅ **More spot pairs** (top 50–100 by volume) | breadth = more shots on goal; less-efficient alts = more edge | `data.binance.vision` spot klines | moderate (GBs) |
| ✅ **All timeframes** (1m, 3m, 30m, 2h, 4h, 6h, 12h, 1d, 1w) | finer signals + more walk-forward folds; 1m the user asked for | same | small–moderate |
| ✅ **Perp futures klines + mark/index price** | the derivatives market that leads spot | binance-futures public | moderate |
| ✅ **Funding rate history** | crowd positioning / carry; extreme funding = reversal signal | binance-futures | tiny |
| ✅ **Open interest history** | leverage build-up, squeeze setups | binance-futures metrics | tiny |
| ✅ **Long/short account & top-trader ratios** | positioning/sentiment, contrarian signal | binance-futures metrics | tiny |
| ✅ **Liquidation history** | forced-flow cascades, capitulation timing | binance-futures | small |
| ✅ **Best bid/ask (bookTicker)** | **real spread** → measured (not assumed) transaction cost | binance public bookTicker | moderate |
| ✅ **Market cap + circulating/total supply** | cap-weighting, liquidity tiers, the field we're missing | CoinGecko free API | tiny (rate-limited) |
| ✅ **Fear & Greed index** | cheap sentiment baseline | alternative.me (free) | tiny |

### Tier 2 — free but heavy (do selectively)

| Data | Signals | Note |
|---|---|---|
| ✅ **Trade-level aggTrades (ticks)** | true microstructure: trade-size distribution, tick-level aggressor flow, realized spread | HUGE (100s of GB for many coins × years) — pull for a *few* focus pairs only |
| ✅ **Multi-exchange** (Coinbase/Kraken/OKX/Bybit) | cross-exchange spread, lead-lag, consolidated price, arb | each exchange = its own pipeline; start with 1–2 |
| ✅ **Options (Deribit): IV, put/call, skew** | forward-looking vol, tail-risk pricing | separate API/format |

### Tier 3 — paid / vendor (operator procures; agent never pays or holds keys) 💳

| Data | Signals | Vendor (example) |
|---|---|---|
| 💳 **Full historical L2 order-book depth** | true slippage/impact modeling — the #1 realism gap before real size | Tardis.dev / Kaiko / Amberdata |
| 💳 **On-chain** (exchange flows, active addrs, whales, stablecoin supply) | fundamental/flow edge others lack | Glassnode / CryptoQuant / Nansen |
| 💳 **Social/news sentiment** | event-driven, narrative rotation | Santiment / LunarCrush |

---

## What each new field concretely enables (why it's "much more information")

- **Funding + OI + liquidations + long/short ratio** → a whole *derivatives-positioning*
  strategy class we literally cannot build today (squeezes, funding-carry, crowded-trade
  reversals). All free. This is the biggest free unlock.
- **bookTicker (spread)** → we stop *assuming* 0.1% cost and start *measuring* it per bar,
  per pair. Directly improves every backtest's realism.
- **More pairs** → the single highest-probability place to actually *find* edge (alts are
  less efficient than BTC/ETH).
- **aggTrades ticks** → order-flow signals far richer than the bar-level taker-buy we
  already found value in (SIG-VOLUME-BREAKOUT).
- **Market cap/supply** → liquidity tiering, cap-weighted baskets, the missing fundamental.

---

## Recommended first pull (Tranche 1 — free, sized, one clean freeze)

Scope kept practical (tick/L2 excluded — too big for a blanket pull):

1. **Spot OHLCV** — top ~50 USDT pairs, timeframes {1m,5m,15m,1h,4h,1d}, 2021→now.
2. **Perp futures** — same top pairs: klines + **funding + open interest + long/short
   ratio + liquidations**.
3. **bookTicker** (best bid/ask) — top ~20 pairs (spread data).
4. **Market cap + supply** — top ~100 coins, daily (CoinGecko free).

Estimated footprint: OHLCV+derivatives ≈ low tens of GB; bookTicker adds more. All
run through the SAME normalize → quality-gate → checksum-freeze pipeline as
DS-CRYPTO-SPOT-BAKEOFF-V1, producing a new versioned frozen dataset (proposed
`DS-CRYPTO-MULTI-V1`). Nothing is trusted until it passes the quality gate.

**Deferred to Tranche 2 (selective):** aggTrades ticks for 3–5 focus pairs; a second
exchange. **Tranche 3 (operator procures):** L2 depth, on-chain, sentiment.

---

## REVISED APPROACH (2026-07-12) — feature-bars, not 78 GB of raw ticks

After measuring real sizes (ticks = 77.9 GB, not 55) and a disk review, the plan
changed to keep the laptop light while preserving reproducibility:

- **Core (~15 GB) stays local** — all-pairs OHLCV + funding. Small, fast, frozen.
- **Ticks are NEVER kept raw at 78 GB.** `tios.dataset.tick_features` streams each
  monthly aggTrades zip into **1-minute microstructure bars** (buy/sell imbalance,
  VWAP, whale-trade size, trade intensity), then discards the raw zip (`--drop-raw`).
  Validated: 65.2M BTC ticks (2021-01) → 44,640 minute-bars; full 5.5y BTC+ETH ends
  **~sub-GB**, checksum-frozen. This keeps the tick *information* local + reproducible
  at ~1/100th the disk.
- The heavy raw→features grind (~108s/month single-threaded) can run **anywhere** —
  locally over a few hours, or free Kaggle/Colab — because only the tiny frozen
  feature parquet lives here. Golden rule intact.
- **Daily updater** (next): a small CCXT/Binance-API job appends yesterday's bars to
  the frozen set, so data stays fresh without re-downloading.

Built & gate-green: `acquire.py` (checksum download), `normalize_multi.py`
(klines→parquet, BTCUSDT_1d full-span verified), `tick_features.py` (ticks→1m bars).

## Boundaries (unchanged)

- Agent pulls **free public** data only. **Paid subscriptions, billing, and API keys are
  operator-set-up; the agent never enters payment or credentials.**
- New data does not touch the validation gates or the live/venue gates. It only widens
  the research surface. Everything stays `execution_authority=NONE` until validated.
