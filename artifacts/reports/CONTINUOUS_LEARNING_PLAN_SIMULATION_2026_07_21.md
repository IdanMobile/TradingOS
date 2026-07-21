# Continuous-Learning Plan Simulation

Date: 2026-07-21  
Mode: offline tabletop and existing-test simulation; no orders, credentials, or live state

## Test evidence

- Fast suite baseline: `uv run pytest -m 'not slow' --durations=25` -> **1,120 passed, 29 deselected in 52.30s**.
- Focused simulation slice covering trading domain, synthetic execution/risk/stability, campaigns, eligibility, experiment execution, paper runtime, and AI evaluation -> **passed in approximately 1.8s**.
- The first focused command referenced nonexistent `tests/test_validation_campaign.py` and failed at collection. The corrected command used the actual `tests/test_campaign.py` path and passed. This demonstrates why command/collection failures must be retained in test reports rather than overwritten by a successful retry.
- Current slowest observed areas include data profiling, secret scanning, canonical baseline setup, calendar/vectorized work, and research-lab paths. These are the first optimization targets; correctness gates must remain intact.

## Tabletop scenarios

### S0 — Conflicting authority

Input: an implementation agent reads the S2-only start handoff and D-105 `ACTIVE` demo status.  
Expected: authority resolver returns `CONFLICT`; no order-path work begins; human decision required.  
Result against plan: **PASS**. Phase 0 blocks safely.  
Current-system concern: **OPEN** because the conflicting documents remain.

### S1 — Losing but correctly executed trade

Input: valid point-in-time data, valid signal, risk approval, expected fill quality, negative realized return within the preregistered distribution.  
Expected: classify as ordinary statistical loss unless evidence supports a defect; do not manufacture a “fix.”  
Result: **PASS by design**. Outcome and attribution contracts allow `ORDINARY_STATISTICAL_LOSS`/unknown and no recommendation.

### S2 — Attractive but overfit backtest

Input: high in-sample Sharpe selected after many variants; weak walk-forward/reserve stability.  
Expected: multiplicity/DSR/PBO and sealed validation block promotion; creating V2 does not reset the family budget.  
Result: **PASS by design**.

### S3 — Inspector invents a cause

Input: LLM claims slippage caused a loss but supplies no execution evidence.  
Expected: unsupported causal claim fails schema/evaluation, remains a hypothesis, and cannot reach the Fixer.  
Result: **PASS by design**.

### S4 — Fixer weakens the test

Input: proposed patch removes a failing test or lowers a risk threshold.  
Expected: protected-path/semantic policy check rejects it; independent evaluation and human approval remain required.  
Result: **PASS by design**; policy implementation still required.

### S5 — Stale real-time feed

Input: market sequence gap or timestamp beyond freshness budget.  
Expected: `DecisionPacket` expires and risk returns block/`NO_TRADE`; no stale prediction is actionable.  
Result: **PASS by design**.

### S6 — Partial fill plus cancel/fill race

Input: multiple executions, asynchronous cancel acknowledgement, duplicate terminal `Filled` events.  
Expected: deduplicate by execution/event identity, accumulate fills/fees, reconcile final order/position/balance, and only then close the trace.  
Result: **PASS in proposed design**.  
Current-system concern: the existing demo script primarily polls for terminal `Filled` and does not yet demonstrate this full stream/reconciliation state machine.

### S7 — Restart after venue acknowledgement

Input: local process persists intent, submits, receives venue acknowledgement, then crashes before recording terminal state.  
Expected: restart searches by client idempotency key, reconciles existing order/executions, and refuses a duplicate submit.  
Result: **PASS in proposed design**.  
Current-system concern: the current order request does not visibly carry the planned venue client idempotency key, and cursor advancement after an attempted signal can obscure recovery. This requires focused implementation review after Phase 0.

### S8 — Strategy V2 proposal

Input: evidence supports one bounded parameter or logic change.  
Expected: create a new immutable child spec with a falsification test; rerun development/validation/reserve/shadow gates; do not replace V1 or move directly to live.  
Result: **PASS by design**.

## Simulation verdict

The proposed architecture handles the critical research, AI, real-time, and execution failure modes on paper and is grounded in existing passing primitives. It is **not yet an executable proof** of the new capabilities because the new contracts and state machine do not exist. The first safe implementation is Phase 0, followed by one offline end-to-end decision trace. No demo or live simulation was performed.

