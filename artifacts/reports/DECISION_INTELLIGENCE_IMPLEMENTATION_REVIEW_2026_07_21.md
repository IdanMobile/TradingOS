# Decision Intelligence Implementation Review

Date: 2026-07-21

Status: offline vertical slice implemented and verified; broader goal remains active

Authority: historical research only; no venue connection, credential access, order, promotion, or live authority

## Outcome

The first end-to-end evidence and learning slice now exists in code:

```text
retained market/backtest evidence
  -> immutable decision or round-trip accounting
  -> deterministic classification
  -> append-only trace/report
  -> AI inspection proposal
  -> independent safety/evidence evaluation
  -> human-review eligibility only
```

The implementation does not try to explain every loss as a bug. Individual negative
round trips remain ordinary statistical losses unless evidence proves a defect. Aggregate
failure can be classified as strategy weakness when the failure repeats across development,
validation, holdout, walk-forward, parameter neighbors, and benchmark comparison.

## Implemented components

- `src/tios/trading_domain/decision_intelligence.py`
  - immutable `DecisionTrace`, `HistoricalTradeTrace`, `DecisionOutcome`, and
    `FailureAttribution` contracts;
  - explicit no-trade, risk-blocked, simulated-unfilled, and simulated-filled states;
  - exact gross - fees - slippage = net reconciliation;
  - fill-fee/outcome-fee reconciliation;
  - AI attribution remains `AI_HYPOTHESIS` unless deterministic or human-reviewed;
  - execution, venue, paper, and live capabilities remain disabled by construction.
- `src/tios/services/reporting/decision_intelligence.py`
  - canonical hashing, fsync'd append-only JSONL, idempotent replay, conflicting-replay and
    tamper detection;
  - prevalidated single-write batch retention for historical trade learning records;
  - deterministic decision funnel and separate profitable, ordinary-loss, confirmed-defect,
    AI-hypothesis, and unknown counts.
- `src/tios/services/reporting/backtest_attribution.py`
  - normalized long-only fill pairing and exact round-trip accounting;
  - cost-flipped loss detection;
  - evidence-driven aggregate diagnosis and recommendation without automatic V2 creation.
- `src/tios/approval/authority_audit.py`
  - fail-closed detection of the current S2/no-demo versus D-105/demo-active conflict.
- `src/tios/ai_eval/decision_inspector.py`
  - versioned agent/model/prompt proposals;
  - independent evidence, competing-hypothesis, protected-path, gate, self-approval, and
    deployment checks;
  - frozen-case evaluation records; `auto_apply` is forbidden.
- Fast and evidence runners under `scripts/run_*decision*`, `scripts/run_inspector_*`, and
  `scripts/run_backtest_loss_attribution.py`.

## Hard evidence

### Real canonical ETH signal flow

- Frozen bars evaluated: **48,154**.
- Canonical signals reproduced: **511**.
- Canonical verifier runtime: approximately **2.70 seconds**.
- Decision projection runtime: approximately **1.65 milliseconds**.
- Repeated run: ledger remained **1 record** with identical trace and ledger hashes.
- Orders created: **0**.
- Authority audit: **CONFLICT**, order-path changes denied.

Trace SHA-256: `680bb15c6ea5cdaf62202853f663d8b253a803917cce63feefa740148d7ef54f`

Ledger SHA-256: `2869151dbb768ae740776baaac7587e4649dfe8db7c44186c5b813b0b87442f6`

### Real B2 backtest loss attribution

Retained development, validation, and already-open holdout normalized fills were analyzed:

| Measure | Result |
|---|---:|
| Round trips | 1,407 |
| Profitable | 242 |
| Losing | 1,165 |
| Gross-positive but fee-flipped | 329 |
| Gross P&L | -165.9356942 USDT |
| Recorded fees | 2,813.09721472 USDT |
| Net P&L | -2,979.03290892 USDT |

The validation split was slightly gross-positive but deeply net-negative after costs;
development and holdout were already gross-negative. Existing validation evidence also
records zero positive walk-forward windows, all parameter neighbors negative, and benchmark
underperformance. Deterministic diagnosis: `STRATEGY_WEAKNESS`. Recommendation:
`REJECT_WITHOUT_RESCUE`. No V2 was created and promotion remains false.

All **1,407** round trips are now retained as unique historical learning traces. Reprojection
from the ledger independently recovers 242 profitable, 1,165 losing, 329 fee-flipped, and the
exact aggregate P&L above. The ledger deliberately contains **zero fabricated signal or risk
fields**, records the reconstruction limitation on every trade, and has execution authority
`NONE` throughout.

Historical learning ledger SHA-256:
`8bf2d97b922da11b0e2bf9d5b4589d445ef6fd97b830cf4d3b2a20a2c10fa4ed`

The no-trade diagnostic avoids 2,979.03 USDT of modeled loss relative to these retained
backtests, but it is not labeled trading profit.

### Inspector version simulation

Four frozen real-data-derived cases were evaluated: a correct risk block, a profitable B2
round trip, an ordinary B2 loss, and a gross-positive trade flipped negative by fees.

- Inspector V1: **0/4**, rejected for evidence/safety/classification failures.
- Inspector V2: **4/4**, correct classifications and bounded recommendations, eligible only
  for human review.
- Pass-rate delta: **+1.0 on these four frozen cases**.
- Auto-applied changes: **0**; orders: **0**; execution authority: **NONE**.

This proves evaluator discrimination and versioning on four cases. It does not prove general
model quality; both proposals are deterministic fixtures and no external model was used.

### Test-speed evidence

- Final focused decision-intelligence lane: **26 passed**, scoped lint and strict typing green,
  **7.045s**.
- Final broad non-slow lane: **1,136 passed**, 29 deselected, **57.32s**.
- Focused feedback is approximately **8.1x faster** while the broad gate is preserved.
- Full repository lint currently reports eight unrelated pre-existing long-line findings in
  `benchmarks/ai_agent/fixtures/build_fixtures.py` and `engines/lean/scripts/lane.py`; all files
  in this change are green.
- Full `src/tios` strict mypy: green across 124 source files.
- Slow large-data baseline: **29 passed in 2,021.27s (33m41s)**.
- Identical slow large-data gate after optimized UTC conversion: **29 passed in 361.43s (6m01s)**.
- Slow-gate improvement: **1,659.84s saved, 82.1% lower runtime, 5.6x faster**.
- Complete current test population across broad and slow lanes: **1,165 passed**.

## Change review

### Findings fixed during review

1. A blocked/no-trade outcome was initially counted as reconciled execution. Projection now
   counts reconciliation only when an order reference exists.
2. Outcome classification initially did not enforce the sign of net P&L. Profit, breakeven,
   ordinary loss, no-trade, and correct-block signs are now checked.
3. Filled outcomes initially did not reconcile reported fees to retained fills. Exact equality
   is now mandatory.
4. Ledger validation initially checked payload hashes but not row/payload identity or duplicate
   trace IDs. Both are now fail-closed.
5. AI evaluation objects could theoretically be instantiated with auto-apply or a verdict that
   disagreed with their checks. Contract invariants now reject both.
6. The Fixer guard did not protect the newly added evaluator and evidence contracts. Authority,
   Inspector evaluation, backtest attribution, and decision-trace files are now immutable to
   autonomous self-modification.
7. Backtest timestamps now require UTC and paired quantities must reconcile exactly.
8. Sampling the slow suite found PyArrow timezone conversion repeatedly resolving timezone
   metadata for each value. A strict epoch-integer UTC converter now preserves timestamp
   semantics while removing the repeated lookup. The same 29 tests prove the speedup.
9. Historical fills initially had only aggregate attribution. All 1,407 round trips now have
   deterministic content-addressed records, batch conflict protection, explicit missing-history
   limitations, and immutable self-modification boundaries.

### Residual limitations

- Only the last canonical ETH signal has a full decision trace; all 511 transitions are
  reproduced but not individually traced to outcomes.
- The authority audit is a transitional prose-marker detector and intentionally never grants
  order-path permission. One canonical machine-readable authority record is still required.
- Backtest attribution supports normalized long-only one-buy/one-sell round trips; partial-fill
  and multi-leg backtests need separate adapters.
- The B2 analysis reuses retained artifacts; it does not rerun the engine or create a new
  strategy experiment. Its registered 3/5 SMA strategy identity is verified, while absent
  historical signal IDs and risk decisions remain explicitly unknown.
- No external AI model, prospective AI evaluation set, Recommender-to-sandboxed-Fixer patch,
  or independent human review workflow has been run.
- No structured real-time shadow feed or `DecisionPacket` exists yet.
- The repository remains a dirty, multi-change baseline owned by the operator.
- The execution authority conflict remains unresolved; order-path work is blocked.

## Supervisory verdict

The offline slice is correctly implemented, materially improves feedback speed and evidence
quality, and produces reproducible hard evidence. It also demonstrates the financially honest
outcome for a failed family: reject it and avoid loss rather than force a new version.

The full continuous-learning objective is not complete. Historical trades and the multi-case
Inspector benchmark are now implemented. The next offline increment is an isolated
proposal-to-patch evaluation workflow with independent regression and economic gates. Real-time
shadow `DecisionPacket` work follows only after that workflow is reliable. Execution work
remains blocked by the authority conflict.
