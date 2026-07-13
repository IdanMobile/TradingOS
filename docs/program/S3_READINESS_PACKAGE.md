# S3 Paper-Trading Qualification — Readiness Package

Prepared: 2026-07-12. Audience: operator (human gate-holder). Original purpose: summarize S3
qualification evidence and human decisions. The 2026-07-13 correction below supersedes its
former readiness claim. Nothing here activates a gate, connects a venue, or crosses
`execution_authority=NONE`.

> **Supervisor correction (2026-07-13; D-045/D-046).** This package is not a current
> readiness attestation. The retained carry run applies static synthetic fee/slippage stress;
> it is not empirical paper divergence or G12 evidence. No strategy is validated, and
> authenticated Bybit demo networking is quarantined pending the complete durable approval,
> validation, security, venue, adapter, and reconciliation predicate.

Source of truth: `docs/program/PROGRAM_PLAN.md` (S3 exit criteria + HG-3/4/5),
`todos/15_paper_trading.md` (T-015 tasks), `MISSING_AND_OPEN_ITEMS.md` (ten human-only items).

## S3 exit criteria — status against the plan

PROGRAM_PLAN S3 exit = **(a)** divergence model quantified; **(b)** paper stability period
defined and met; **(c)** human-only venue gates resolved; **human gate:** HG-5 limited-live
review (cannot be delegated).

| Exit criterion | Owner | Status |
|---|---|---|
| (a) Divergence model quantified | AI | **BLOCKED** — typed synthetic comparison machinery exists, but the carry run is static cost stress, not observed paper fills or empirical G12 divergence. |
| (b) Paper stability period **defined** | AI | **DONE** — heartbeat-derived stability + immutable incident lifecycle + drill-evidence validation implemented. |
| (b) Paper stability period **met** | AI+gate | **BLOCKED** — requires a live paper lane running a *validated* strategy over the defined window. |
| (c) Human-only venue gates resolved | Human | **OPEN** — HG-4, ten items below. |
| HG-5 limited-live review | Human | **OPEN** — S3 exit gate. |

## Task-by-task (Initiative 15)

- **T-015-01 — Paper-lane architecture decision.** D-043 is operator-adopted and locks
  `SYNTHETIC_LOCAL_SIMULATOR` as the S3 architecture. This does not approve HG-3 or
  activate a bot; both HG-3 and a validation-approved strategy context remain required.
- **T-015-02 — Paper deployment of first validated strategy.** **BLOCKED — no strategy is
  genuinely validation-approved.** This is the true bottleneck (see next section). The
  deployment *machinery* (`src/tios/services/paper/`) exists; it has nothing valid to run.
- **T-015-03 — Backtest-vs-paper divergence tracking.** **PARTIAL.** Typed synthetic
  comparison machinery exists; empirical observations remain absent and require a properly
  approved active lane after T-015-02.
- **T-015-04 — Operational drills.** **AI-part DONE** (lifecycle/evaluation). Real
  operational evidence needs an active lane.
- **T-015-05 — Human-only venue gates package.** **100% operator-owned** (HG-4 prep).

## Current bottleneck: no genuinely validated strategy and an incomplete carry model

T-015-02 requires a strategy that passed validation. The full research arc (recorded in
`PROJECT_STATE.md`) found none:

- Predictive / single-asset and cross-sectional TA: retained implementations failed, but
  method/provenance gaps prevent a family-wide rejection claim.
- The retained professional stat-arb implementation fails out of sample; that result does not
  establish that cointegration as a family has decayed.
- **Funding carry** is a market-neutral research hypothesis, not a verified edge. Its DSR
  "pass" is stamped `verdict_is_genuine: false`; computation on the current model cannot make
  that result genuine:

  1. **Counterparty loss is outside the retained return series.** The simplified stress sweep
     assumes a 100% haircut is unrecoverable, but it is not an empirical default model. A
     Sharpe/DSR number cannot validate a risk absent from its observations.
  2. **The modeled headline is regime-dependent.** Static-cost outputs vary sharply by period;
     because the model is incomplete, those values are exploratory rather than realistic
     execution estimates.

**Conclusion:** carry still needs a corrected offline two-leg capital/collateral, funding-event,
rehedging, liquidation, point-in-time-universe, and provenance model before execution evidence
could become decision-useful. Empirical execution and operational venue/counterparty evidence
would then remain separate later requirements. Local-simulator
activation requires HG-3 plus a validation-approved strategy context; HG-4 is required only
for a later venue testnet/demo path. The offline model gaps are AI-remediable; the activation
and venue-eligibility decisions remain hard human gates. **S3 cannot be "finished" by the AI
alone — by design.**

## T-015-01 — Paper-lane architecture decision (adopted in D-043)

**Locked architecture: confined local synthetic simulator first; venue testnet/demo only after HG-4.**

- Rationale: a venue testnet/demo requires venue account eligibility and API permissions —
  those are HG-4 (unknowable to an agent). Before HG-4, the only permitted architecture is
  the local `SYNTHETIC_LOCAL_SIMULATOR` already built in `src/tios/services/paper/` (no venue,
  no credentials, synthetic USDT accounting, conservative immutable risk caps). Its activation
  still requires HG-3 plus a validation-approved strategy context.
- Graduation path: once HG-4 confirms a venue + permissions, add a venue-testnet adapter
  behind the same paper contracts and re-run the divergence model against real testnet fills.
- Evidence: OKX demo confirmed available (REG §6); Binance testnet/demo unconfirmed — a
  post-HG-4 recheck item.

## What the operator must decide (the irreducible human work)

**HG-3 — MVP / paper-phase acceptance** (S2 exit): accept the research-lab + paper machinery
as ready to *enter* the paper phase. The architecture is already adopted in D-043; HG-3
unblocks activation only for a matching validation-approved strategy context.

**HG-4 — Venue/operator eligibility** (before S3 exit): the ten human-only items —
1. Israel/operator account eligibility for the selected venue · 2. product availability in
your account · 3. API trading permissions · 4. current automated-trading terms · 5. current
fee tier · 6. funding/deposit/withdrawal path · 7. credential isolation & revocation process ·
8. capital amount + maximum acceptable drawdown · 9. tax/accounting workflow · 10. final human
approval. **All account-level facts an agent cannot know or obtain.**

**HG-5 — Limited-live review** (S3 exit): explicit review before any real capital.

## Honest recommendation

Do **not** move carry toward live capital on the strength of its current backtest. The evidence
supports no live entry; if a corrected strategy ever validates, any proposal should be staged:

1. Complete the supervisory corrective criteria, then review **HG-3**.
2. Treat carry only as a candidate: after HG-3, it may enter the **local synthetic paper
   lane** only if its specific strategy context becomes validation-approved. Until both
   conditions hold, do not run it; the local lane needs no venue or credentials.
3. Resolve **HG-4** for the specific proposed venue setup, with reviewed concentration and
   correlated-counterparty assumptions; do not use the simplified `1/K`/`p^K` scenario as a
   sizing rule.
4. Only then **HG-5** limited-live with a capital amount you can fully lose.

After HG-3 and validation approval for a specific context, further risk and execution work
would still be required. HG-4 is additionally required before any multi-venue allocation or
venue-testnet adapter; the current diversification scenario and regime filter are exploratory,
not approved controls.
