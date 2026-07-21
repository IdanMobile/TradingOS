> SUPERSEDED (2026-07-21): see docs/supervisor/*_2026-07-21.md and PROJECT_STATE.md.

# Trading OS supervisory baseline — 2026-07-13

Status: active full-project baseline under the repository-local Trading OS Supervisor.  
Reviewed commit: `672e2da9209d494a0bbdabd8e55bcd00f6c7fa44` plus the corrective working-tree changes listed below.  
Environment: local single-operator repository; no venue, wallet, credential, or live/demo command was used during this review.

## Executive conclusion

The repository has a substantial, test-covered S1/S2 research and evidence platform, but the current project is not yet professionally defensible as a validated trading system. Two critical defects invalidate stronger claims:

1. authenticated Bybit demo orders were executed without the durable HG-3/HG-4, validation, security-review, and venue-specific approval chain required by the project SSOT; and
2. the shared Deflated Sharpe Ratio implementation used the null/noise Sharpe threshold instead of the observed Sharpe in the non-normality adjustment.

The current safe operating state is therefore **constrained offline S2 research**. Authenticated Bybit demo networking is quarantined. No strategy is validated, promotion-eligible, paper-approved, or live-approved. Historical demo-order artifacts are retained as evidence of machinery and a governance breach, not as S3 qualification evidence.

## Review mode and scope

Mode: full baseline review, explicitly requested by the project goal. The review covered governance, SSOT alignment, architecture, source/data provenance, strategy research, backtest statistics, synthetic risk/execution, authenticated demo scripts, dashboard projections, tests, packaging, and current Git state.

The review did not:

- inspect or expose `.env` values;
- contact Bybit, Binance, or any other venue;
- place, cancel, modify, or simulate a new authenticated order;
- use a wallet, account, paid service, or live capital;
- discard or rewrite the operator's committed work.

## Authoritative sources inspected

- `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md`
- `TRADING_OS_NORTH_STAR.md`
- `PROJECT_STATE.md`, `DECISION_LOG.md`, `MISSING_AND_OPEN_ITEMS.md`
- all mandatory decisions/specifications in the SSOT read order
- `docs/architecture/AD.md`, module and type/contract catalogs
- program, product, test, traceability, audit, and current handoff documents
- repository-local supervisor skill and all deep-review references
- current source, scripts, tests, tracked evidence, manifests, and Git state

External primary sources checked on 2026-07-13:

- [Bybit Demo Trading Service](https://bybit-exchange.github.io/docs/v5/demo): demo is an isolated account on `api-demo.bybit.com`, but it uses real trading rules and supports `/v5/order/create`; it is therefore venue execution with fake funds, not an inert local simulator.
- [Bybit API-key information](https://bybit-exchange.github.io/docs/v5/user/apikey-info): permissions distinguish read-only, spot/derivatives trade, transfers, and withdrawals.
- [Bybit V5 integration guidance](https://bybit-exchange.github.io/docs/v5/guide): HMAC payload and timestamp/receive-window semantics.
- [Bailey and López de Prado, Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf): DSR adjusts for multiple selection and non-normal returns; its denominator uses the selected strategy's observed Sharpe, sample length, skewness, and kurtosis.
- [Bailey et al., Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253): CSCV estimates how often an in-sample-selected strategy underperforms out of sample.

## Verified project facts

- **Verified fact:** `main` is one commit ahead of `origin/main`; the operator committed the former dirty worktree as `672e2da` with message `wip before supervisor codex`.
- **Verified fact:** the repository has no currently running demo bot, paper worker, job worker, or dashboard process.
- **Verified fact:** Git tracks `.env.example`, not `.env`; secret values were not inspected.
- **Verified fact:** no retained HG-3, HG-4, Bybit-specific approval, or post-D-044 decision exists.
- **Verified fact:** `PROJECT_STATE.md` records authenticated Bybit demo spot and perp orders despite D-036/D-037/D-042/D-043 and AD §AA keeping those capabilities gated.
- **Verified fact:** direct offline checks passed before corrective changes: Ruff, Ruff formatting, strict mypy, offline lock validation, offline wheel/sdist build, and a 577-test safe subset.
- **Verified fact:** the package integrity manifest did not match six controlled files at intake.
- **Verified fact:** no strategy has a complete approvable validation package.

## Unknowns and rejected assumptions

- **Unknown:** whether an informal chat instruction authorized a historical demo run. It is not durable evidence and cannot satisfy the missing validation, security, HG-3, HG-4, or venue-specific predicates.
- **Unknown:** current demo-key presence, validity, scope, IP restrictions, and rotation state. These were intentionally not inspected.
- **Unknown:** corrected funding-carry economics after a full two-leg capital, collateral, rehedging, liquidation, point-in-time universe, and event-timing model.
- **Rejected assumption:** fake money means no execution authority. Bybit documents demo orders as venue orders under real trading rules, even though no real capital is at risk.
- **Rejected assumption:** a second implementation is independent merely because it is in another function when it repeats the same equation and assumptions.
- **Rejected assumption:** causal feature alignment alone makes a post-hoc regime filter out-of-sample.
- **Rejected assumption:** a negative or profitable backtest proves or disproves an entire strategy family when its source, universe, costs, and holdout design are incomplete.

## Current system map

`data → normalization → features → strategies → portfolio → risk → execution proposal → reconciliation → monitoring → memory`

| Layer | Current owner/path | Verified state | Main gap |
|---|---|---|---|
| Data | `tios.dataset`, raw/normalized Parquet, public Binance files | Real public data and frozen S1 dataset; expanded multi-pair data exists | expanded raw/normalized manifests are mutable/incomplete; point-in-time universe and official checksum reuse need repair |
| Normalization | `src/tios/dataset/*` | Real converters and quality checks | the expanded dataset lacks one immutable per-run provenance chain |
| Features | canonical evaluator plus research scripts | SMA/EMA/BB/RSI/Donchian and several ad hoc features are implemented/tested | many research features live only in scripts and bypass canonical spec/version identity |
| Strategies | canonical baselines/seeds plus standalone research scripts | Baselines and seed specs are versioned; many negative experiments are retained | funding, stat-arb, cross-sectional, MTF, combinations, and generic public strategies lack complete canonical specifications |
| Portfolio | `tios.trading_domain.synthetic`, paper runtime, carry accounting | Local synthetic projections plus deterministic two-leg capital/basis/funding/fee/isolated-margin primitives exist | no gate-approved active portfolio; the carry lifecycle and venue-specific collateral/liquidation model are not integrated |
| Risk | validation gates, pure synthetic risk evaluator, exit ladder | Independent inert/synthetic checks exist | no active risk authority; demo scripts bypassed these contracts; some risk primitives need stronger input bounds |
| Execution proposal | local paper runtime; standalone `scripts/demo_*` | local simulator is synthetic; historical Bybit demo orders were real venue-demo activity | authenticated scripts are outside the locked adapter/gate architecture and are now quarantined |
| Reconciliation | synthetic ledger/divergence; demo wallet/status probes | deterministic synthetic evidence exists; historical demo probes attempted reconciliation | demo scripts had fail-open/unknown-fill paths; the funding “paper” artifact is static cost stress, not observed fills |
| Monitoring | dashboard API/UI, jobs projection, artifacts | substantial read-only and bounded-action visibility | some views said venue execution was absent while displaying retained Bybit demo orders |
| Memory | decisions, state, ResearchAssets, concepts, reports | durable evidence and negative results are retained | authoritative docs/manifests drifted; market/industry claims need claim-level evidence records |

## Real, simulated, mocked, incomplete, and undocumented classification

| Classification | Components |
|---|---|
| Real | source code, local tests, public market datasets, historical authenticated Bybit demo orders, Git/artifact history |
| Simulated | historical backtests, synthetic fills/ledger/account/portfolio, S3 probe artifacts, hardcoded fee/slippage stresses |
| Mocked | AI null provider, injected test transports, probe-only readiness records |
| Incomplete | G10 independence/selection design, funding carry capital/risk model, expanded-data lineage, public-strategy holdout, stat-arb validation, canonical strategy registry coverage, active risk/execution/recovery |
| Undocumented or contradictory | historical demo authorization chain, Bybit credential naming/intake, demo activity versus S2-unreachable reports, top-N/perp research scope decisions |

## Corrective changes started in this review

- corrected the shared DSR non-normality denominator and both comparison implementations;
- added a non-normal known-answer regression fixture;
- hard-quarantined the authenticated Bybit GET/POST transports while leaving injected offline tests usable;
- tightened the demo origin, permission, wallet, environment-name, and ignore-file checks;
- removed fail-open demo fill assumptions and made failed flattening visible;
- added repository-level authenticated order-path coverage;
- added package-integrity verification to `make check`.

These changes do not approve or activate any venue, strategy, paper lane, wallet, or real-money capability.

## Supervisory decision

Continue the full review as a dependency-ordered remediation program. Critical statistical and execution-governance defects take precedence over new strategy searches, dashboard expansion, additional venues, or further demo runs. A negative-result research system with honest provenance is acceptable; a profitable-looking but method-invalid artifact is not.

## Completion criteria for this baseline cycle

- all critical findings in the companion improvement plan are fixed and regression-tested;
- every affected DSR artifact is recomputed or explicitly superseded;
- package integrity and the full offline local gate pass;
- authoritative documents agree on the current safe stage and historical demo evidence;
- no authenticated network transport is reachable without the full durable human/evidence predicate;
- unresolved quant claims are downgraded to hypotheses or supported by corrected reproducible evidence;
- no secret, live-capital path, or unapproved authority is introduced.
