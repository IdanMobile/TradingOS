# Session handoff — Stage B demo-evidence decision packet — 2026-07-23

## Outcome

A review-only operator decision packet now specifies the security, risk,
evidence, sanitization, cohort-disclosure, activation, and rollback contract for
a possible in-lane Stage B demo-evidence tap:

`docs/supervisor/STAGE_B_DEMO_EVIDENCE_SECURITY_DECISION_PACKET_2026-07-23.md`

The packet creates execution authority `NONE`. No Stage B code was written, no
service was restarted, and no implementation or activation was authorized.

## Recommendation and preserved boundary

Option A, full evidence-first Stage B, is recommended for a separately approved
implementation and independent review. It requires durable evidence and a
persisted unique client idempotency key before any risk-increasing submission,
terminal reconciliation, fail-closed new entries on evidence failure, and an
unconditional path for risk-reducing exits, stops, cancels, and reconciliation.

Option B is a passive partial observer that cannot establish a complete chain.
Option C retains manual Stage A. Stage A cannot report realized PnL.

The latest retained point-in-time check described the fake-money demo runtime
as healthy, but the only real captured episode is legacy, open, incomplete, and
has zero realized outcomes. It is excluded from all future Stage B cohorts.
There is no strategy validation, promotion, profitability, live-trading, or
real-money claim.

## Exact next decision

The operator should either:

1. paste the packet's exact Option A implementation-approval statement, after
   which the agent must first present the exact proposed
   `STAGE-B-DEMO-EVIDENCE-ONLY` integrity/decision-log exception scope; or
2. select Option B or C using the exact wording in the packet.

Implementation approval does not authorize activation. Activation needs a
second exact approval after independent security review, `make check`, mode
hardening of the observed legacy raw lane from `0755`/`0644` to `0700`/`0600`,
dashboard projection redaction, rollback evidence, and a preferably-flat
controlled restart window.

Phases 3 and 4 remain blocked on the separate Phase-2b external trust and
independent-review gates.
