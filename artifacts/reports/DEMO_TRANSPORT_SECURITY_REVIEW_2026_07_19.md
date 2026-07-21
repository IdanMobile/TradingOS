# Demo Transport Security Review — Stage 1 (2026-07-19)

Authority: D-104 (operator-approved S3 demo lane, execution-measurement mode).
Mandate: D-046 requires a security review and typed adapter/reconciliation review before any
reactivation of the quarantined authenticated Bybit demo transports.
Scope of THIS review (stage 1): read-only signed GET transport only. Order POST transports
remain quarantined pending stage 2.

## Files reviewed

- `scripts/demo_preflight.py` (207 lines, full read) — signing, host lock, key-safety checks.
- `scripts/demo_roundtrip.py` (346 lines, full read) — order flow, caps, reconciliation.
- `scripts/demo_strategy_bot.py`, `scripts/demo_carry_bot.py`, `scripts/demo_managed_bot.py`,
  `scripts/demo_pnl.py` (pattern check) — all route GETs through `pf._urllib_transport` and
  POSTs through `rt._post_transport`; all gate on GREEN preflight; all carry notional caps
  (50 / 300 / managed cap USDT).

## Findings

1. **Single chokepoint design confirmed.** Every authenticated GET in all six scripts flows
   through `pf._urllib_transport`; every order POST flows through `rt._post_transport`.
   Un-quarantining GET does not enable any order path.
2. **Host lock is sound.** `require_demo_base` rejects any base that is not exactly
   `https://api-demo.bybit.com` (no port, no userinfo, no path/query/fragment). Stage-1 adds
   defense in depth: the transport itself independently refuses non-https or non-demo-host
   URLs, so a future caller bug cannot redirect signed headers elsewhere.
3. **Key-safety checks are correct.** Preflight fails (`ok:false`) any key with withdraw or
   transfer permission, any read-only key, or any auth failure. A mainnet key simply fails
   auth on the demo host (Bybit demo host does not accept mainnet keys) — safe failure mode.
4. **No secret egress.** Keys are read from git-ignored `.env` (0600) only by name filter;
   preflight report prints host/permissions/balances, never key or secret. `.env` confirmed
   ignored (`.gitignore:2`) and untracked; `.env.example` confirmed placeholder-only.
5. **Naming rail honored.** `PYBIT_API_KEY` remains deliberately rejected
   (`test_first_reads_only_documented_name`) so mainnet-tutorial key names cannot flow in;
   operator keys were renamed in place to `BYBIT_DEMO_API_KEY`/`BYBIT_DEMO_API_SECRET`.
6. **Known ceilings (accepted for stage 1).** BTCUSDT base-step hardcoded (1e-6);
   `place_market_sell` is bounded by held position rather than an independent notional cap;
   scripts are procedural, not the typed adapter — all three are stage-2 review items.

## Decision

- `pf._urllib_transport` un-quarantined: real https GET, demo-host-locked, 10s timeout.
  New refusal property tested offline (`test_get_transport_refuses_non_demo_urls`).
- `rt._post_transport` remains quarantined; its message now cites D-104 stage 2. The
  existing quarantine test (`test_authenticated_post_transport_is_quarantined`) still holds.
- Stage 2 (order transports) requires: typed execution adapter wrapping, independent sell
  cap, instrument-info step lookup, reconciliation contract wiring, and a recorded review.

Status: **Stage 1 APPROVED — read-only GETs live; orders still quarantined.**
