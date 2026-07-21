# Adversarial Review — Continuous-Learning Plan

Date: 2026-07-21  
Verdict: **CONDITIONALLY READY** for implementation; blocked at Phase 0

## Critical finding

The repository has contradictory execution authority. The highest-precedence start handoff says S2-only and quarantined authenticated demo transports. D-104 authorizes an S3 execution-measurement lane, D-105 labels the sole demo order path active, and D-106 approves dashboard control. The documents try to preserve D-046 boundaries while activating a replacement route, but higher-precedence operational guidance was not reconciled.

Impact: an agent cannot determine the valid execution boundary without choosing between conflicting records. No order-path change is safe until one explicit decision updates the complete source-of-truth chain.

## Red-team findings and controls

| Risk | Failure mode | Required control |
|---|---|---|
| Evaluator capture | The Inspector/Fixer improves against its own judge and appears better | Independent evaluator, frozen fixtures, deterministic checks, prospective shadow set, human critical review |
| Profit gaming | Agent hides costs, blocks losing periods, or increases tail risk | Score net expectancy with uncertainty, drawdown, capacity, coverage, and rule compliance; report all attempts |
| Holdout contamination | AI sees reserve results through reports or memory | Access control and separate storage; record every dataset access; one authorized reveal |
| Version laundering | V2/V3 resets a failed trial budget | Family-level trial budget and parent lineage; versions remain within the same multiplicity accounting |
| False causality | A loss is attributed to one feature from a plausible narrative | Competing hypotheses, confidence, evidence links, one-variable counterfactuals, prospective falsification |
| Layer confusion | Poor execution is “fixed” by changing the strategy, or weak signal blamed on slippage | Deterministic P&L decomposition and mutually explicit data/strategy/risk/execution/operations labels |
| Async order errors | Polling assumes one fill or misses cancel/fill races | Persist-before-send, client idempotency key, stream-driven state machine, execution deduplication, reconciliation |
| Correlated votes | Several similar strategies appear to provide independent confidence | Exposure and return-correlation aggregation; cap shared factor/regime risk |
| Data freshness | Real-time decision uses stale/gapped/out-of-order input | Sequence/freshness/clock checks; fail closed to `NO_TRADE` |
| AI self-modification | Fixer deletes a test or relaxes a risk gate | Protected paths and semantic policy checks; no self-approval; isolated branch and rollback |
| Secret leakage | Prompts/traces contain credentials or signed requests | Structured allowlist, redaction tests, no secret access by analysis agents |
| Overbuilding | New services duplicate existing domain contracts | Modular-monolith vertical slices; extend existing types; adapters only where justified |
| Dirty baseline | Existing uncommitted work makes causality and rollback unclear | Phase 0 inventory and accepted baseline snapshot before implementation |

## Plan corrections resulting from review

- Added Phase 0 as a hard implementation gate.
- Put deterministic attribution before AI diagnosis.
- Separated Inspector, Recommender, Fixer, and Evaluator authority.
- Made family-level trial budgets survive V2/V3 creation.
- Required `NO_TRADE`, blocks, failed attempts, and unknown attribution in reports.
- Made real-time chart understanding operate on structured point-in-time feeds; rendered charts remain a human presentation layer.
- Made execution stream-driven and restart-recoverable rather than poll-until-filled.
- Kept MLflow/OpenTelemetry behind ports instead of replacing the canonical evidence ledger.

## Readiness gates

The design is ready. Implementation may start only with Phase 0. Phase 1 is ready after one authoritative decision resolves stage/demo status and the current dirty baseline is inventoried. Phases 7-8 require separate authority even if Phases 0-6 succeed.

