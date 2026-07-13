# HG-3 / HG-4 / HG-5 — Operator Decision Packages

Prepared: 2026-07-12 by the AI. Purpose: prepare evidence for each human gate without
delegating the gate decision. Nothing here activates a gate, connects a venue, enters a
credential, or moves money. `execution_authority=NONE`.

> **Supervisor correction (2026-07-13; D-045/D-046).** These packages are drafts, not
> ready-to-sign attestations. The DSR/search-lineage, carry-model, provenance, and empirical
> divergence gaps in the supervisory improvement plan remain open. Historical authenticated
> Bybit demo activity is not qualification evidence, and current authenticated demo networking
> is quarantined.

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
- Typed synthetic divergence machinery and drill evaluators exist, but empirical divergence
  and operational evidence are not complete.
- S3 readiness assessment — `docs/program/S3_READINESS_PACKAGE.md`.

**Residual you must weigh:** accepting HG-3 does not create a tradeable strategy. T-015-02
still requires a *validation-approved* strategy context, and none exists yet (see the memo).
Granting HG-3 would not by itself start trading, but this draft does not recommend approval
until the supervisory corrective acceptance criteria are satisfied.

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
- Counterparty-risk scenario sketch — `run_carry_counterparty_diversification.py` illustrates
  a single-venue total-loss assumption and a simplified independent-venue `p^K` model. It is
  not an empirical default/correlation estimate or a validated allocation rule.

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

**Illustrative constraint, not sizing guidance:** diversification and per-venue caps can reduce
single-venue concentration, but venue independence is unverified and the retained `1/K`/`p^K`
scenario is too simple to select a venue count or allocation. Item 8 must bound the total
program to a loss the operator can fully absorb.

**The one thing only you can do:** complete items 1–10 from your own account/venue facts and
record the HG-4 decision. The agent must not create the account, enter credentials, or sign.

---

## HG-5 — Limited-live review (S3 exit)

**Certifies:** explicit review authorizing *real capital*, after HG-3 + HG-4 + a met paper
stability period.

**Preparatory evidence (not completed prerequisites):**
- Static synthetic execution-cost stress — `run_funding_carry_s3_paper.py` applies modeled
  spot+perp taker fees and slippage; it does not measure fills, empirical divergence, or G12.
- Exploratory regime sensitivity — `run_funding_carry_robustness.py` and
  `run_funding_carry_regime_filter.py`; the latter is causally aligned but has not passed nested
  out-of-sample validation and is not an approved deploy gate.
- Counterparty diversification scenario — as HG-4; not a validated allocation plan.

**Preconditions that are NOT yet met (must hold before HG-5 is even reviewable):**
1. A strategy is genuinely validation-approved (none is — see memo).
2. HG-3 granted; HG-4 completed for the specific proposed venue setup.
3. A paper stability period defined *and met* on the live paper lane.

**Residual you must weigh:** carry is an unvalidated, regime-dependent research hypothesis.
Its capital/collateral, liquidation, event-timing, point-in-time universe, execution, and
counterparty model is incomplete. Current evidence supports no live start.

**The one thing only you can do:** conduct the limited-live review and authorize a specific
capital amount you can fully lose. The agent will not route the first order.

---

## Recommended sequence (also in S3_READINESS_PACKAGE.md)
1. Complete the supervisory corrective acceptance criteria, then review **HG-3**; approval
   still starts nothing by itself.
2. Get a strategy to *genuine* validation, or explicitly accept carry as a
   research-grade candidate for paper only.
3. Run it on the **local synthetic paper lane** for the defined stability window (no venue).
4. **HG-4** — complete the ten items for the specific proposed venue setup, including explicit
   concentration and correlated-counterparty assumptions.
5. **HG-5** — limited-live review, capital you can fully lose.

Each numbered step gates the next. Offline methodology, provenance, strategy, and divergence
work remains before these packages can be treated as decision-ready.
