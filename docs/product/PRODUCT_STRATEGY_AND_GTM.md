# Trading Intelligence OS — Product Strategy & Path to Live

Author view: written as PM/CEO, 2026-07-12. Honest, not promotional. This is the
strategic frame around the code; the SSOT for what is *authorized* is still the
program plan and decision log.

---

## 1. Where we actually are (the board-level truth)

- The **infrastructure is strong and honest**: a strict validation harness (G1–G11 +
  production G10 DSR/PBO), a working synthetic paper lane (fill → ledger → position →
  portfolio → divergence), a human-readable backtester, and hard gates that keep
  anything unproven away from real money.
- The **product's problem is not engineering — it is that we have no edge yet.**
  Every strategy tested (our seeds, 20 copied public systems, and now volume/flow
  signals) is statistically indistinguishable from luck on liquid crypto majors.
- **That is the expected result, not a failure.** BTC/ETH spot is the most efficient,
  most-picked-over corner of crypto. If a simple public edge worked there, it would
  already be arbitraged away. Finding edge *here* is the hardest possible starting
  point.

**CEO takeaway:** we do not have a product until something passes the gates. Rushing an
unvalidated strategy to live is how a trading firm dies on day one. The gates are the
product's credibility — we protect them, we do not weaken them.

## 2. The strategic insight — where edge actually lives

Edge comes from one of five places. We should deliberately move toward them:

| Source of edge | Do we have it? | Move |
|---|---|---|
| **Data others don't have** (order book, on-chain, funding) | ❌ | acquire (§5) |
| **Signals others ignore** (volume, volatility regime, order flow) | ⚠️ partial | **build now** (done: signal search) |
| **Less-efficient markets** (smaller/newer coins) | ❌ (only BTC/ETH) | acquire more pairs |
| **Execution/cost advantage** (maker rebates, smart routing) | ❌ | later, needs venue |
| **Speed** (latency arb, HFT) | ❌ (not our game) | out of scope |

The two cheapest, fastest moves are **signals we ignore** (free — we already have the
data) and **less-efficient markets** (a data download). Everything else is heavier.

## 3. The real moat

Not a magic strategy — nobody has one reliably. Our moat is the **honest, automated
pipeline from idea → validated → paper → tiny-live**, with the discipline to reject
99% of ideas. A firm that can *safely and quickly* test hundreds of strategies and
deploy the one real winner at small size, with a kill switch, beats a firm chasing a
single overfit backtest. **We sell trust and speed-of-validation, not a crystal ball.**

## 4. Path to live — the confidence ramp

Speed and confidence are reconciled by going live **small and staged**, the instant —
and only the instant — something passes honestly.

```
idea → offline backtest → HONEST SCREEN (holdout + beat B&H + robust)
     → full validation (G1–G11 + G10 DSR≥0.95)         ← the wall almost everything dies at
     → [HUMAN GATE HG-3] operator approves S2 exit
     → PAPER lane, real observation window (weeks)       ← proves backtest ≈ live behaviour
     → paper divergence within tolerance?
     → [HUMAN GATE] operator approves tiny live
     → LIVE, $100s, ONE strategy, kill switch armed       ← real money, real small
     → scale ONLY on live evidence, never on backtest
```

The key idea: **be one approval away from deploying at all times.** Automate everything
up to each human gate so that when a winner appears, it reaches tiny-live in days, not
months. We are already ~80% of the way there on infra.

## 5. What to build / acquire, prioritized (value ÷ effort)

**Now, free (data we already have):**
1. ✅ Order-flow / volume / volatility signals (`run_signal_strategy_search.py`).
2. ✅ Data-character profile (`data_profile.py`).
3. Feed these signals into the canonical strategy engine + validation (currently
   strategies only see OHLC).

**Next, one data download each (operator decision — I cannot download unilaterally):**
4. **More coins** (top 20–50 by liquidity). Biggest expected payoff: smaller coins are
   less efficient, so edge is more likely to exist. Binance public klines, same
   pipeline, checksum-frozen. *Highest value / lowest effort.*
5. **Longer / more-granular history** (1m bars). Enables finer signals and more folds.

**Later, heavier (real cost, real value):**
6. **Order book / L2 depth** — turns our *assumed* slippage into *measured* slippage.
   The single biggest realism upgrade before risking real money.
7. **Funding + open interest** — unlocks perps and basis/carry strategies (currently
   deferred).
8. **On-chain + sentiment** — genuinely differentiated signals, but noisy and vendor-heavy.

**Execution layer (needs venue, human/credential gated):**
9. Smart order routing, maker-rebate capture, partial-fill handling — only meaningful
   once a strategy is validated and we're going live.

## 6. Go-to-market: fastest to real trading, with confidence

The honest answer to "how fast can we trade for real?":

1. **Weeks, for the *pipeline* to be deploy-ready** — mostly done.
2. **Unknown, for a *validated edge* to appear** — this is a search/data problem, and
   the way to shorten it is breadth: more coins + more signals = more shots on goal.
3. **Days from edge-found to tiny-live** — if we finish the automation up to the human
   gates.

So the fastest *responsible* GTM is: **maximize breadth of the search (more coins, more
signals) while keeping the deploy pipeline one-approval-ready, then go live at trivial
size the moment one strategy clears the gates, and scale only on live P&L.** Confidence
comes from the gates + small size + kill switch; speed comes from automation + breadth.

**What we will NOT do:** lower a statistical threshold to force a known-overfit strategy
through, connect a venue or credential without the operator's explicit gate, or size up
on backtest results instead of live results.

## 7. Top risks

- **Overfitting via search breadth** — more strategies/coins = more chances to find
  *fake* edge. Mitigation: the DSR deflation already scales with trial count; keep it.
- **Backtest ≠ live** — no order book means slippage is assumed. Mitigation: acquire L2
  before meaningful size; the paper lane's divergence report is the early-warning.
- **Regime dependence** — an "edge" that only worked in the 2021 bull. Mitigation: the
  all-three-thirds screen + walk-forward.
- **Operational/venue risk** — key leakage, fat fingers, outages. Mitigation: restricted
  credentials, kill switch, manual-only escalation (already modeled in the S4 contracts).

---

### Immediate recommended next actions
1. Wire the new volume/volatility/flow signals into the canonical engine + validation.
2. Operator decision: authorize a **top-N coin** klines download (highest value/effort).
3. Keep the paper→tiny-live automation moving so we are one approval from deploy.
