# Funding-pressure Spot V2 operational abort

Status: **ABORTED BEFORE SELECTION — no strategy verdict**

V2 started from clean commit `68d0436`. Its import bootstrap succeeded, but pandas 3 rejected
the mixed naive/UTC-aware development slice bounds in the first vectorbt worker. The runner
failed closed and removed temporary outputs. Development reference computation had begun in
memory; no selection artifact, validation/reserve/full/period evaluation, campaign output, or
inspectable metric artifact was created.

V3 changes only external-worker parsing of the already-frozen segment strings into explicit UTC
timestamps. It inherits the V1 strategy/statistical contract by hash. No strategy or gate changes
and no network, venue, credential, bot, order, paper/demo/live state, or authority are involved.
