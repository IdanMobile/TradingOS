# Strategy Research Direction — CEO/CTO Brief (2026-07-12)

Written as CEO/CTO/broker after a research + backtest sweep. Sources:
`research/SOURCE_REGISTRY.md` → strategy-discovery.

> **Supervisor correction (2026-07-13; D-045).** The scoreboard below is historical
> exploratory evidence, not current validated performance. The shared DSR equation required
> correction, effective-independent-trial/selection lineage remains unresolved, several data
> and source identities are incomplete, and no strategy has passed a complete approvable
> validation package. Treat family conclusions and carry economics as hypotheses until the
> supervisory improvement plan is satisfied.

---

## 1. Historical exploratory scoreboard (numeric DSR evidence superseded by D-045)

| Strategy family | Best (realistic sizing) | DSR | Verdict |
|---|---|---|---|
| Predictive single-asset TA (25 strategies, 2,277 trials) | Sharpe ~1.46 | 0.69 | FAIL |
| Cross-sectional momentum, long-only | Sharpe 1.14 | 0.9456 | FAIL (fragile; degrades with more pairs) |
| Cross-sectional momentum, long-short | Sharpe 0.97 | 0.70 | FAIL (retained implementation; family conclusion unsupported) |
| Stat-arb pairs, naive daily | Sharpe 0.58 | 0.15 | FAIL (retained implementation; family conclusion unsupported) |
| **Funding carry, single-exchange** | **~8.8%/yr** | 1.0* | *NON-GENUINE — hypothesis; economics/risk model incomplete |

## 2. The central insight

The retained predictive price implementations failed their tests. That supports deprioritizing
those exact implementations, not declaring price forecasting in liquid crypto a dead family.

**Market-neutral strategies are a research direction, not a proven local edge.** External
benchmark and manager claims require claim-level primary-source evidence and do not establish
achievable performance for this implementation.

**The constraint that defines this path:** many market-neutral implementations need
**shorting / perps / margin / multi-exchange** — capabilities behind the S4 gate or
requiring data we don't yet have. Spot-long-only *cannot* be market-neutral. So the
route to a tradeable validated strategy is: (a) PROVE a market-neutral edge in honest
backtest, then (b) the operator UNLOCKS the perp/margin capability (S4 human gate) to
trade it. Research and go-live gate are now explicitly connected.

Historical failures show that carry risk is not only price; counterparty and custody risk also
matter. The current local model does not establish the relative contribution of those risks and
must treat them as first-class.

## 3. The strategy menu — dynamic options & variants

| Option | What it is | Status for us | Needs |
|---|---|---|---|
| **A. Funding carry** | long spot / short perp, collect funding | unvalidated hypothesis; current economics/model incomplete | capital+collateral+basis+rehedging+counterparty+liquidation+event-timing model; immutable data; perps to trade |
| **B. Stat-arb pairs (pro)** | cointegration-tested spread, hedge ratio, intraday | retained naive and pro implementations fail; family conclusion unsupported | correct family statistics + rolling hedge ratio + nested temporal validation + 1h data |
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

1. **Carry model reconstruction** — use immutable spot/perp/funding inputs to model two-leg
   capital, collateral, basis, rehedging, funding events, missing data, liquidation, and costs.
   *This tests the hypothesis; it does not presume a real signal.*
2. **Professional stat-arb** — add an in-sample cointegration test + rolling hedge ratio
   + 1h frequency on BTC-ETH and majors (data in hand).
3. **Risk-parity combination framework** — blend sleeves by equal risk contribution once
   ≥2 validate honestly.

## 6. Recommendation

Prioritize correcting provenance and market-neutral methodology before expanding search.
Immediate next build: reconstruct funding carry on immutable spot/perp/funding inputs with a
complete two-leg capital and risk model; basis is only one of several missing dimensions.
Retain stat-arb as an exploratory family until its statistics and nested validation are fixed;
combine sleeves only after at least two validate. Trading any of it remains an explicit
operator decision to unlock the perp/margin S4 capability. `execution_authority=NONE`.
