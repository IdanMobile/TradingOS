# Trading Intelligence OS — Product Strategy & Path to Live

Author view: written as PM/CEO, 2026-07-12. Honest, not promotional. This is the
strategic frame around the code; the SSOT for what is *authorized* is still the
program plan and decision log.

> **Supervisor correction (2026-07-13; D-045/D-046).** This is a strategic aspiration, not a
> deployment-readiness claim. The project has no validated strategy; DSR/search lineage, data
> provenance, carry economics, and empirical divergence remain incomplete. Historical Bybit
> demo activity is not qualification evidence, and authenticated demo networking is currently
> quarantined.

---

## 1. Where we actually are (the board-level truth)

- The repository has **substantial research infrastructure**: a validation harness, synthetic
  paper components, a human-readable backtester, and human gates. Critical statistical and
  execution-governance corrections are in progress, so the pipeline is not yet deployment-ready.
- The **product has both engineering/methodology gaps and no validated edge.** Retained strategy
  implementations have not produced a complete approvable package; this does not prove every
  family is statistically indistinguishable from luck.
- Negative results are useful when their exact data, source, selection procedure, and limits are
  retained. Claims about relative market efficiency remain hypotheses requiring evidence.

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

Not a magic strategy. The potential moat is a defensible pipeline from idea → validated →
paper → limited-live, with immutable lineage and disciplined rejection. That remains a target,
not a current product claim. Trust depends on completing the corrective plan and preserving
every human gate.

## 4. Path to live — the confidence ramp

Speed and confidence are reconciled by going live **small and staged**, the instant —
and only the instant — something passes honestly.

```
idea → offline backtest → HONEST SCREEN (holdout + beat B&H + robust)
     → full validation (G1–G11 + G10 DSR≥0.95)         ← the wall almost everything dies at
     → [HUMAN GATE HG-3] operator approves S2 exit
     → PAPER lane, defined observation window             ← tests backtest/live divergence
     → paper divergence within tolerance?
     → [HUMAN GATE] operator approves tiny live
     → LIVE, $100s, ONE strategy, kill switch armed       ← real money, real small
     → scale ONLY on live evidence, never on backtest
```

The key idea is to make each prerequisite explicit and independently reviewable. A candidate
must clear methodology, provenance, validation, security, paper evidence, venue eligibility,
and the applicable human gates; it is not currently one approval from deployment.

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

1. **Unknown, for the pipeline to be deploy-ready** — critical/high corrective criteria remain.
2. **Unknown, for a validated edge to appear** — methodology and immutable provenance take
   precedence over additional search breadth.
3. **Unknown, from validation to limited-live** — empirical paper evidence, venue/security
   review, and nondelegable human gates remain.

So the fastest responsible route is to repair statistical selection, provenance, canonical
strategy identity, and carry semantics before expanding breadth. A future limited-live proposal
must clear the full chain and scale only on decision-useful live evidence.

**What we will NOT do:** lower a statistical threshold to force a known-overfit strategy
through, connect a venue or credential without the operator's explicit gate, or size up
on backtest results instead of live results.

## 7. Top risks

- **Overfitting via search breadth** — more strategies/coins = more chances to find
  *fake* edge. Mitigation: preregister the full hierarchy, preserve the actual selection
  population, and justify effective independent trials; raw trial count is insufficient.
- **Backtest ≠ live** — no order book means slippage is assumed. Mitigation: acquire L2
  before meaningful size; the paper lane's divergence report is the early-warning.
- **Regime dependence** — an "edge" that only worked in the 2021 bull. Mitigation: the
  all-three-thirds screen + walk-forward.
- **Operational/venue risk** — key leakage, fat fingers, partial/unknown fills, asymmetric
  legs, outages, and counterparty failure. Current mitigation is quarantine; any future adapter
  needs typed reconciliation, least privilege, security review, and explicit human approval.

---

### Immediate recommended next actions
1. Complete the critical statistical and execution-governance corrections.
2. Repair immutable data/experiment provenance and canonical strategy identity.
3. Rebuild funding carry semantics or retain it explicitly as an unvalidated hypothesis.
