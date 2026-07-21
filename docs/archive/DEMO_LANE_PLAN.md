# Demo-lane integration plan (venue testnet/demo)

**Status: QUARANTINED under D-046. This is a historical design note, not an activation
checklist. No current authenticated demo transport may reach a venue.**

Prepared: 2026-07-13. Historical purpose: outline a possible connection from the paper lane to
a real exchange **demo** account (fake money, real exchange system). It is now retained only as
design context for a future fully governed integration.

Correction: historical authenticated Bybit demo activity occurred without the complete durable
approval chain and is retained as governance-breach evidence, not S3 qualification. The
preflight and order transports now fail before network access. Future reactivation requires
HG-3, HG-4, validation approval, security review, venue-specific approval, and a typed
adapter/reconciliation review; merely removing a guard or possessing demo keys is insufficient.

## The three rungs (unchanged)
1. **Local synthetic simulator** — built now; no account, no money, on your machine.
2. **Venue demo/testnet** — *this plan*; fake money on the exchange's real live system, via API.
3. **Limited-live** — real money, capped (HG-5).

Demo is venue execution with fake funds. It is therefore behind the complete D-046 predicate,
not a light key-generation step. Real money additionally remains behind HG-5.

## Venue recommendation

**Historical candidate: Bybit demo.** It offers a real demo API
(`api-demo.bybit.com`), generous virtual balance (~50k USDT + 1 BTC + 1 ETH), and it covers
**both spot and perpetuals** (the perp leg matters if a funding-carry-style strategy is ever the
one validated). Secondary: **OKX demo** (simulated trading on real live prices, demo API keys) —
a possible fallback requiring its own current research, approvals, and typed integration.

| Venue | Demo API | Spot | Perps | Notes |
|---|---|---|---|---|
| **Bybit** | `api-demo.bybit.com` | ✓ | ✓ | Keys from the **Demo Trading** module on bybit.com (NOT testnet.bybit.com); recommended |
| **OKX** | demo flag on `www.okx.com` API | ✓ | ✓ | Real live prices; good fallback |
| Binance | Spot Testnet | ✓ | testnet | More manual-oriented; usable with caveats |

This table is capability context only; it does not select or approve a venue.

## Historical env shape (do not populate while quarantined; never commit real values)
```
DEMO_VENUE=bybit                 # bybit | okx
BYBIT_DEMO_API_KEY=              # a DEMO key — trade permission, NO withdrawal
BYBIT_DEMO_API_SECRET=
# OKX alternative:
# OKX_DEMO_API_KEY=
# OKX_DEMO_API_SECRET=
# OKX_DEMO_API_PASSPHRASE=
```

## Future reactivation checklist (not currently executable)
1. Record current HG-3, HG-4, validation, security-review, and venue-specific approvals for the
   exact strategy, operator, venue, account, permissions, and time window.
2. Implement and review a typed adapter behind the locked paper contracts, including
   fail-closed partial/unknown-fill handling, asymmetric-leg recovery, final position/balance
   reconciliation, idempotency, and append-only evidence.
3. Verify least-privilege isolated demo credentials without exposing them and prove the exact
   demo origin; fund removal remains forbidden.
4. Only after all predicates are durable and current may a bounded preflight or demo exercise be
   separately authorized. Empirical fills must be recorded as G12/divergence evidence; static
   synthetic cost stress does not qualify.

## What is built now vs later
- **Now:** retained historical scripts, fail-closed network quarantine, and injected offline
  tests. There is no active authenticated signer or venue connection.
- **Later, only after the full predicate:** a venue-specific typed adapter and reconciliation
  review. Another venue is not a trivial signer swap; it needs its own semantics and approval.
