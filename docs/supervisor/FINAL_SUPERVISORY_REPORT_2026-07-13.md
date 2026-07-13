# Trading OS final supervisory report — 2026-07-13

## Executive conclusion

The bounded full-system correction cycle is complete. The repository is now a
defensible **offline S2 research system** with explicit evidence and authority
boundaries. It is not trade-ready: no strategy is validated or promotion-eligible,
G10 is `METHOD_BLOCKED`, venue connectivity is quarantined, and execution authority
is `NONE`. No profitability claim is made.

The baseline and finding register remain authoritative:

- `docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md`
- `docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md`

## Verified work completed

- Quarantined every authenticated Bybit demo transport before network access and
  reclassified retained demo orders as unauthorized historical governance probes.
- Made demo fill, asymmetry, flatten, and residual-position handling fail closed.
- Corrected the Deflated Sharpe Ratio non-normality denominator against the primary
  method source; aligned selection, CSCV/PBO, and DSR on per-bar Sharpe; separated
  raw from correlation-derived effective trial counts.
- Regenerated corrected G10 diagnostics. B2 and B4 numerically fail, B3 is
  method-blocked, and the overall gate remains method-blocked because the upstream
  search hierarchy was not retained. The seed context also numerically fails and is
  promotion-blocked.
- Explicitly superseded obsolete G10 artifacts, reports, handoffs, and the pre-demo
  2026-07-10 live-unreachability report. The coding-agent SSOT now routes to the
  supervisor plan.
- Added deterministic normalized-data provenance, content-addressed current REST
  inputs, current/archive manifests, strict hash verification, and a fail-closed
  provenance envelope for future substantive research.
- Changed future public, signal, and universe searches to train-only selection with
  frozen context-level holdout evaluation. Existing affected runs remain exploratory.
- Executed the preregistered 66-trial baseline G10 campaign from a clean commit with
  immutable per-family evidence. B2/B4 fail, B3 is method-blocked, and no promotion
  or execution authority was created.
- Added research-only multi-leg canonical identity and deterministic Decimal carry
  accounting/lifecycle primitives for capital, funding, basis, fees, rehedging,
  closing, and isolated-margin breach. Venue-specific semantics remain absent.
- Reconciled package hashes, project state, decision records, security status,
  dashboard wording, strategy-method claims, and durable open items.

## Validation completed

- `make check`: PASS — package integrity, Ruff lint, Ruff formatting, strict mypy,
  and **720 tests**.
- Controlled package hashes: **76/76 PASS**.
- Current normalized manifest and its 69 table/source chains: PASS.
- `make audit`: PASS — no known dependency vulnerabilities.
- `git diff --check`: PASS.
- Secret-pattern review: no hits in nonignored deliverables. The ignored local `.env`
  was not read or exposed and its filesystem mode was restricted to owner-only.

## Remaining risks and classification

| Risk | Classification | Consequence |
|---|---|---|
| Historical search hierarchy and historical normalization run identity cannot be reconstructed | Not enough evidence | Historical G10 cannot pass; old results remain non-promotional |
| Stat-arb, cross-sectional, combination, ranking, MTF, and composition methods lack complete canonical/method ownership | Intentionally deferred corrective backlog | Family-wide conclusions and promotion remain blocked |
| Carry lacks sourced venue contract semantics, point-in-time funding inputs, collateral tiers, transfers, intraperiod liquidation, empirical costs/fills, and counterparty model | Not enough evidence / future scope | Carry is a research hypothesis, not G12 or a validated strategy |
| Exact public-strategy source/version/license identity and a single globally frozen candidate are incomplete | External evidence dependency | Public-strategy outputs remain exploratory |
| HG-3, HG-4, HG-5, venue/account eligibility, permissions, terms, fees, counterparty allocation, and capital limits are absent | Human decision required | No venue, paper/demo, or live activation |
| Ignored local credentials may predate this review | Human security action if exposure is uncertain | Rotate them outside the repository; no value was inspected or used |
| Oversized source distribution and release packaging | Intentionally deferred until release authority | No release should be published from this worktree yet |

## Decisions required from the operator

No decision is required to preserve the current safe offline state. Future expansion
requires separate human decisions for HG-3/HG-4/HG-5, a specific venue integration,
credential rotation if exposure is uncertain, and any paid data or release action.

## Recommended next phase

Continue offline only. Do not expand the failed legacy proxy grids. If baseline
conformance remains useful, preregister a new canonical next-bar-open, F1/S1-or-stricter
campaign on distributable frozen data. Otherwise reconstruct one strategy family's method
and canonical ownership before new parameter search. Do not reactivate authenticated
networking or treat any numeric diagnostic as promotion evidence.

## Primary method and venue references

- Bailey and López de Prado, *The Deflated Sharpe Ratio*:
  <https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf>
- Bailey et al., *The Probability of Backtest Overfitting*:
  <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253>
- Bybit V5 demo-trading service:
  <https://bybit-exchange.github.io/docs/v5/demo>
- Bybit V5 API key information and authentication guide:
  <https://bybit-exchange.github.io/docs/v5/user/apikey-info> and
  <https://bybit-exchange.github.io/docs/v5/guide>

All sources were last checked during this review on 2026-07-13. Venue documentation
supports only the classification and security boundary; it provides no operator
eligibility, validation, or activation approval.
