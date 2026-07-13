# S3 Paper-Trading Qualification — Readiness Package

Prepared: 2026-07-12. Audience: operator (human gate-holder). Purpose: collapse the
remaining work to finish Stage S3 down to the irreducible decisions only a human can make,
and record the AI-completable work as done. Nothing here activates a gate, connects a venue,
or crosses `execution_authority=NONE`.

Source of truth: `docs/program/PROGRAM_PLAN.md` (S3 exit criteria + HG-3/4/5),
`todos/15_paper_trading.md` (T-015 tasks), `MISSING_AND_OPEN_ITEMS.md` (ten human-only items).

## S3 exit criteria — status against the plan

PROGRAM_PLAN S3 exit = **(a)** divergence model quantified; **(b)** paper stability period
defined and met; **(c)** human-only venue gates resolved; **human gate:** HG-5 limited-live
review (cannot be delegated).

| Exit criterion | Owner | Status |
|---|---|---|
| (a) Divergence model quantified | AI | **DONE** — typed backtest-vs-paper divergence reports (signal/fill/cost/P&L); exercised on the carry candidate. |
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
- **T-015-03 — Backtest-vs-paper divergence tracking.** **AI-part DONE.** Real observations
  need an active lane (gated by T-015-02).
- **T-015-04 — Operational drills.** **AI-part DONE** (lifecycle/evaluation). Real
  operational evidence needs an active lane.
- **T-015-05 — Human-only venue gates package.** **100% operator-owned** (HG-4 prep).

## The real bottleneck: there is no genuinely-validated strategy, and carry cannot be backtest-validated

T-015-02 requires a strategy that passed validation. The full research arc (recorded in
`PROJECT_STATE.md`) found none:

- Predictive / single-asset & cross-sectional TA: rigorously ruled out (best DSR ~0.69–0.95, fragile).
- Professional stat-arb (cointegration + hedge ratio + OOS + 1h): **fails out-of-sample**
  (DSR 0.0088) — cointegration decays.
- **Funding carry** is the one real market-neutral edge, but its DSR "pass" is stamped
  `verdict_is_genuine: false`, and that is not a formality that more computation can clear:

  1. **The dominant risk is off-sample.** Carry's killer is exchange counterparty default
     (FTX/LUNA 2022) — a one-shot, unrecoverable tail that is simply absent from the
     historical return series. Any Sharpe/DSR computed on carry returns is therefore
     structurally optimistic; the stress sweep shows a 100% haircut is unrecoverable at any
     carry rate. A backtest number cannot validate away a risk it cannot see.
  2. **The headline is regime-inflated.** Realistic-execution carry is +42.6%/yr in the 2021
     bull but −3.8%/yr in the 2022 bear and +3.7%/yr in 2023–26. The 8.4%/yr full-period
     figure is mostly one regime.

**Conclusion:** carry's remaining validation is *definitionally* execution-level (needs a
real paper lane) and operational (eventual venue/counterparty facts). Local-simulator
activation requires HG-3 plus a validation-approved strategy context; HG-4 is required only
for a later venue testnet/demo path. This is not a gap in the work; it is the exact reason the
project made activation and venue eligibility hard human gates. **S3 cannot be "finished" by
the AI — by design.**

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

Do **not** rush carry to live capital on the strength of its backtest. The evidence supports a
*deliberate, staged, diversified* entry, not an autonomous one:

1. Resolve **HG-3** to formally enter the paper phase.
2. Treat carry only as a candidate: after HG-3, it may enter the **local synthetic paper
   lane** only if its specific strategy context becomes validation-approved. Until both
   conditions hold, do not run it; the local lane needs no venue or credentials.
3. Resolve **HG-4** for a *specific* venue, with **per-venue equity caps** so no single
   default is fatal (directly attacks the −100% tail).
4. Only then **HG-5** limited-live with a capital amount you can fully lose.

After HG-3 and validation approval for a specific context, the hardening/fine-tuning targets
are already known. HG-4 is additionally required before multi-venue carry allocation or a
venue-testnet adapter: counterparty diversification, a funding-regime deploy filter (skip the
2022-style bleed), and the venue-testnet adapter behind the paper contracts.
