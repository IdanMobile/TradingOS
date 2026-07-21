# Decision Intelligence Probe Evidence

Date: 2026-07-21

Mode: offline historical research; no venue connection or order capability

## Observed result

- Frozen dataset bars: **48154**
- Canonical signals reproduced: **511**
- Canonical verifier runtime: **2704.992 ms**
- Decision trace projection runtime: **1.646 ms**
- Trace ledger records: **1**
- Risk-blocked decisions: **1**
- Orders created: **0**

## Integrity

- Trace SHA-256: `680bb15c6ea5cdaf62202853f663d8b253a803917cce63feefa740148d7ef54f`
- Ledger SHA-256: `2869151dbb768ae740776baaac7587e4649dfe8db7c44186c5b813b0b87442f6`
- Net P&L reconciles gross P&L, fees, and slippage by contract.
- Replaying the same trace is idempotent; conflicting content under the same trace ID fails.
- Ordinary statistical losses are counted separately from confirmed defects.

## Authority result

Status: **CONFLICT**

Order-path changes allowed: **False**

Blockers: `CONTRADICTORY_DEMO_AUTHORITY_CLAIMS`

The probe proves the first offline vertical slice. It does not validate or promote the
strategy and does not simulate, submit, or authorize a venue order.
