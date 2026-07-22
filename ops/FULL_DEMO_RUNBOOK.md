# Full demo runbook (read-only operator path)

This runbook demonstrates the currently implemented operating system without starting work or
changing runtime state. It may report retained historical validation and holdout-split metrics
that are already authorized for ordinary project inspection. It never reads preregistered
prospective outcomes or sealed holdout artifacts. The demo account uses fake venue funds. Every
strategy remains unvalidated and unpromotable, and execution authority remains `NONE`.

## Preflight

From the repository root, run exactly:

```sh
uv run python scripts/check_full_demo_readiness.py --pretty
```

The command performs two fixed loopback `GET` requests whose server handlers read no project
evidence: the static dashboard shell and a fixed negative API-schema probe. All other evidence
comes from bounded, descriptor-anchored local snapshots. The command does not start, stop,
restart, repair, enqueue, backtest, campaign, sign, trade, or contact a venue.

- `READY` (exit 0): all demo operations pass and a future root-owned authority explicitly
  reports an independently verified `ACTIVE_NO_DECISIONS` snapshot. Execution authority is still
  `NONE`.
- `AUTHORITY_GATED` (exit 0): all demo operations pass, but independent reviewer/activation
  evidence remains incomplete. This is the expected safe full-demo state until that ceremony is
  finished.
- `DEGRADED` (exit 1): at least one operational or safety check failed. Stop the walkthrough and
  inspect the named failed check; this command never repairs it.

Do not treat a zero exit as authorization to promote a strategy or use real money.

## Safe walkthrough

1. Require `READY` or `AUTHORITY_GATED` with `operational=true` from the preflight.
2. Present the generated readiness JSON. The `quality_gate`, `orchestrator_evidence`,
   `jobs_database`, and `demo_lane` checks are the audited read-only views for this walkthrough.
3. Explain that a passing `make check` certifies implemented scope, not profitability,
   statistical validation, or product completion.
4. Show that the orchestrator observation is fresh and `halted=false`. It observes and
   prioritizes; it cannot place orders.
5. Show the jobs schema, integrity, and state counts. Retired legacy work is not permission to
   re-run closed strategy families.
6. Show `VENUE_DEMO`, `real_money=false`, `promotion_eligible=false`, the fresh heartbeat, and
   currently corroborated disaster-stop evidence. Demo fills are execution-measurement evidence
   only.
7. Show the authority check. `AUTHORITY_GATED` is an honest external-review
   dependency, not an operational failure and not permission to bypass the gate.

Do **not** open the default dashboard page during this audited walkthrough. Its JavaScript loads
multiple projection endpoints; a separate holdout/prospective read audit has not yet established
that whole-page navigation as a safe demo surface. The checker probes the static shell without
executing JavaScript and probes `/api/readiness-probe`, whose fixed `410` JSON handler performs no
project reads. Default-dashboard navigation remains temporarily blocked for this runbook until
that audit closes.

## Dashboard controls are out of bounds during the demo

Do **not** click `START`, `STOP`, or `RUN_ONCE`. Those are write actions and are outside this
read-only walkthrough. Do not submit workspace decisions, trigger a data update, enqueue work,
run a campaign/backtest, touch a kill-switch file, or attempt an authority ceremony while
presenting the demo.

If the readiness report is `DEGRADED`, preserve the evidence and use the owning service's reviewed
operational procedure. Never improvise a restart or clear a kill switch merely to make the screen
look green.

## Claims the demo may and may not make

Safe claims: the dashboard, observer/orchestrator, bounded jobs worker, quality evidence, and
fake-money demo lane are observable; the lane's current protection is corroborated by fresh local
reconciliation evidence when the report says so.

Prohibited claims: guaranteed profit, validated edge, approved strategy, admission/promotion,
venue truth beyond the lane's retained reconciliation, live readiness, real-money authority, or
completion of Phase 3/4 while external activation remains gated.
