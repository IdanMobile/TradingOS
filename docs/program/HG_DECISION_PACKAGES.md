# HG-3 / HG-4 / HG-5 — Operator Decision Packages

Prepared: 2026-07-12 by the AI. Purpose: bring each human gate to the point where the only
remaining step is your signature. Everything an agent can legitimately do is done and linked;
what remains in each package is a human decision, by design. Nothing here activates a gate,
connects a venue, enters a credential, or moves money. `execution_authority=NONE`.

> **Boundary (why the AI stops here).** HG-3/4/5 are human-only gates (PROGRAM_PLAN;
> D-036/D-037/AD §AA) and D-042 records that this authority cannot be delegated to the agent.
> HG-4 and HG-5 additionally require actions the agent never performs: creating a venue
> account, entering credentials, and authorizing real capital. An AI that self-approves its own
> path to live money voids the whole guarantee. So each package below is *prepared*, and each
> ends with **the exact thing only you can do.**

---

## HG-3 — MVP / paper-phase acceptance (S2 exit)

**Certifies:** the research-lab + local paper machinery is accepted as ready to *enter* the
paper phase. It does **not** authorize a venue or real money; it unlocks activation of the
local synthetic simulator for a strategy context that is *also* validation-approved.

**AI-completed prerequisites (evidence):**
- Paper-lane architecture decided and locked — D-043 (local `SYNTHETIC_LOCAL_SIMULATOR` first).
- Paper machinery built + gate-guarded — `src/tios/services/paper/` (store/runner/market/models);
  refuses activation without an APPROVED S3 stage gate + validation approval; synthetic USDT;
  conservative immutable risk caps; append-only confined store.
- Divergence model (T-015-03) and operational drills (T-015-04) — AI-part done.
- S3 readiness assessment — `docs/program/S3_READINESS_PACKAGE.md`.

**Residual you must weigh:** accepting HG-3 does not create a tradeable strategy. T-015-02
still requires a *validation-approved* strategy context, and none exists yet (see the memo).
So HG-3 is safe to grant, but it does not by itself start any trading.

**The one thing only you can do — record the HG-3 human decision:**
```
GATE:      GATE-S3-PAPER-DEMO-READINESS
DECISION:  APPROVED | REJECTED | DEFER
BY:        <operator name>            DATE: <UTC>
BASIS:     reviewed S3_READINESS_PACKAGE.md + D-043; accept entry to paper phase
NOTE:      does not authorize any venue, credential, or real money
```
Record it through the console's audited human-decision route (D-038), signed as `CreatorType.HUMAN`.

---

## HG-4 — Venue / operator eligibility (before S3 exit)

**Certifies:** a *specific* venue is eligible and safe for the operator to use. Every item is an
account-level fact an agent cannot know or obtain.

**AI-completed prerequisites (evidence):**
- Public venue-capability slice — RG-05 (data.binance.vision public data confirmed; OKX demo
  confirmed per REG §6). This is *public capability only*, not your account eligibility.
- Counterparty-risk structure quantified — `run_carry_counterparty_diversification.py`:
  a single-venue default is an **unrecoverable −100%** tail; splitting across K venues with
  per-venue caps converts it to a recoverable 1/K loss and shrinks total wipeout to p^K. **This
  is why HG-4 is not one venue but a portfolio-of-venues decision.**

**The ten human-only items — fill and sign (MISSING_AND_OPEN_ITEMS §Human-only):**
| # | Item | Your finding |
|---|---|---|
| 1 | Israel/operator account eligibility for the selected venue | |
| 2 | Product availability in your account | |
| 3 | API trading permissions | |
| 4 | Current automated-trading terms | |
| 5 | Current fee tier | |
| 6 | Funding/deposit/withdrawal path | |
| 7 | Credential isolation & revocation process | |
| 8 | Capital amount + maximum acceptable drawdown | |
| 9 | Tax/accounting workflow | |
| 10 | Final human approval | |

**Sizing guidance from the counterparty model (yours to accept or override):** use **≥3
independent venues**, each capped at ≤1/K of deployed capital, so no single default exceeds a
recoverable loss. Correlated (systemic) default is the residual that *only capital sizing*
(item 8) bounds — size the whole program to a loss you can fully absorb.

**The one thing only you can do:** complete items 1–10 from your own account/venue facts and
record the HG-4 decision. The agent must not create the account, enter credentials, or sign.

---

## HG-5 — Limited-live review (S3 exit)

**Certifies:** explicit review authorizing *real capital*, after HG-3 + HG-4 + a met paper
stability period.

**AI-completed prerequisites (evidence):**
- Realistic execution measured — `run_funding_carry_s3_paper.py` (carry nets ~8.4%/yr after
  per-leg spot+perp taker+slippage).
- Regime robustness — `run_funding_carry_robustness.py` (headline is 2021-bull-heavy; bear
  −3.8%/yr) and `run_funding_carry_regime_filter.py` (a causal deploy gate lifts the bear to
  −0.7%/yr without lookahead).
- Counterparty diversification plan — as HG-4.

**Preconditions that are NOT yet met (must hold before HG-5 is even reviewable):**
1. A strategy is genuinely validation-approved (none is — see memo).
2. HG-3 granted; HG-4 completed for a specific multi-venue setup.
3. A paper stability period defined *and met* on the live paper lane.

**Residual you must weigh:** carry is a real but modest, regime-dependent edge whose dominant
risk (venue counterparty) is off-sample and can only be bounded operationally. The evidence
supports at most a *limited-live, multi-venue, capped* start — never a full-size autonomous one.

**The one thing only you can do:** conduct the limited-live review and authorize a specific
capital amount you can fully lose. The agent will not route the first order.

---

## Recommended sequence (also in S3_READINESS_PACKAGE.md)
1. **HG-3** — accept paper-phase entry (safe now; starts nothing by itself).
2. Get a strategy to *genuine* validation, or explicitly accept carry as a
   research-grade candidate for paper only.
3. Run it on the **local synthetic paper lane** for the defined stability window (no venue).
4. **HG-4** — complete the ten items for **≥3 venues** with per-venue caps.
5. **HG-5** — limited-live review, capital you can fully lose.

Each numbered step gates the next. The agent has finished every part of every step that is not
a human signature or an account-level fact.
