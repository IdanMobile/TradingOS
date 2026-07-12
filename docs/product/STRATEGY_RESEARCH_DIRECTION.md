# Strategy Research Direction — CEO/CTO Brief (2026-07-12)

Written as CEO/CTO/broker after a full research + backtest sweep. Honest, no hype.
Every number below came through the project's own G1–G11 + production-G10 (Deflated
Sharpe Ratio ≥ 0.95) gate. Sources: `research/SOURCE_REGISTRY.md` → strategy-discovery.

---

## 1. The honest scoreboard

| Strategy family | Best (realistic sizing) | DSR | Verdict |
|---|---|---|---|
| Predictive single-asset TA (25 strategies, 2,277 trials) | Sharpe ~1.46 | 0.69 | FAIL |
| Cross-sectional momentum, long-only | Sharpe 1.14 | 0.9456 | FAIL (fragile; degrades with more pairs) |
| Cross-sectional momentum, long-short | Sharpe 0.97 | 0.70 | FAIL (crypto short side is noise) |
| Stat-arb pairs, naive daily | Sharpe 0.58 | 0.15 | FAIL (crypto pairs not cointegrated at daily freq) |
| **Funding carry, single-exchange** | **~8.8%/yr** | 1.0* | *INFLATED — real signal, risk model incomplete |

## 2. The central insight

**Predictive price forecasting is a dead end in liquid crypto.** Our results agree
with 2025 industry data ("directional funds bled red"). Every price-prediction
strategy fails DSR.

**Market-neutral strategies are the real edge** — and they are what actual funds run:
2025 dollar-neutral crypto benchmark ~31%, top venue 66% at Sharpe 2.39; stat-arb
BTC-ETH Sharpe ~2.23; market-neutral drawdowns <1%. Cross-exchange funding arbitrage
is a leading fund's *largest* book.

**The catch that defines our path:** every validated market-neutral edge needs
**shorting / perps / margin / multi-exchange** — capabilities behind the S4 gate or
requiring data we don't yet have. Spot-long-only *cannot* be market-neutral. So the
route to a tradeable validated strategy is: (a) PROVE a market-neutral edge in honest
backtest, then (b) the operator UNLOCKS the perp/margin capability (S4 human gate) to
trade it. Research and go-live gate are now explicitly connected.

Through the 2022 FTX/LUNA collapse, the killer of carry was **not** price
(delta-neutral handled it) — it was **counterparty risk** (funds trapped on failing
exchanges). Any real market-neutral book must treat exchange/counterparty risk as
first-class.

## 3. The strategy menu — dynamic options & variants

| Option | What it is | Status for us | Needs |
|---|---|---|---|
| **A. Funding carry** | long spot / short perp, collect funding | REAL (~8–9%/yr, tested); validation inflated (funding leg only) | basis+counterparty+liquidation modelling; perp price data (free); perps to trade |
| **B. Stat-arb pairs (pro)** | cointegration-tested spread, hedge ratio, intraday | naive daily FAILS; pro version untested | cointegration test + rolling hedge ratio + 1h data (have) + BTC-ETH focus |
| **C. Cross-exchange arb** | price/funding differences across venues | untested | multi-exchange data (have Binance only); low latency |
| **D. Market-making** | quote both sides, earn spread | untested | order book + low-latency infra (data + infra gap) |
| **E. Combination / ensemble** | risk-parity blend of uncorrelated sleeves | pending ≥2 validated sleeves | risk-parity weighting; crisis-correlation caveat |

**On "mixing data and timeframes":** multi-timeframe *confluence* gives directional
strategies a marginal lift; the bigger lever is multi-*data* fusion (funding + basis +
order-book + on-chain) feeding market-neutral signals. We have OHLCV + funding; the
frontier data (order book, on-chain) is the paid tier.

## 4. Operator decision points (only you can authorise)

1. **Unlock perps/margin (S4 capability)?** — required to trade *any* validated
   market-neutral strategy. Real money, real counterparty risk. The gate between
   "backtest edge" and "tradeable."
2. **Procure multi-exchange + order-book data?** — required for cross-exchange arb,
   market-making, and realistic basis/slippage modelling. Paid vendors.
3. **Which sleeve to validate first?** — recommendation below.

## 5. What can be built NOW, no gates

1. **Carry with basis modelling** — download Binance perp klines/mark (FREE, reuses our
   acquire pipeline) → model the spot-perp basis + liquidation → turn the inflated
   Sharpe-11 into a truthful risk-adjusted number. *Highest value: makes a real signal
   honestly validatable.*
2. **Professional stat-arb** — add an in-sample cointegration test + rolling hedge ratio
   + 1h frequency on BTC-ETH and majors (data in hand).
3. **Risk-parity combination framework** — blend sleeves by equal risk contribution once
   ≥2 validate honestly.

## 6. Recommendation

Pursue **market-neutral, not predictive.** Immediate next build: **download the (free)
Binance perp data and validate funding carry WITH basis + liquidation risk** — it is
the only strategy where the underlying signal is already proven real, and the honest
missing piece (basis) is one free download away. In parallel, build the professional
stat-arb. Then combine. Trading any of it remains an explicit operator decision to
unlock the perp/margin S4 capability — which is now a justified, evidence-backed
decision rather than a leap. No threshold was ever moved; `execution_authority=NONE`.
