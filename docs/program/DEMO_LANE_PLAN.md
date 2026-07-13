# Demo-lane integration plan (venue testnet/demo)

Prepared: 2026-07-13. Purpose: everything needed to connect the paper lane to a real exchange
**demo** account (fake money, real exchange system) the moment an account confirms — designed
so live activation is a small, safe, human-triggered step, never an automatic one.

Boundary: this plan and the preflight tool touch **no venue and no credentials** until you have
demo keys and explicitly proceed. Demo keys must be **least-privilege, isolated, revocable, and
never withdrawal-enabled** (`.env` rule + AD §AA). Real-money keys are never used here.

## The three rungs (unchanged)
1. **Local synthetic simulator** — built now; no account, no money, on your machine.
2. **Venue demo/testnet** — *this plan*; fake money on the exchange's real live system, via API.
3. **Limited-live** — real money, capped (HG-5).

Demo sits behind a light human step (you generate the keys + say go); real money is HG-4/HG-5.

## Venue recommendation

**Primary: Bybit demo.** Best fit for driving a bot by API — a real demo API
(`api-demo.bybit.com`), generous virtual balance (~50k USDT + 1 BTC + 1 ETH), and it covers
**both spot and perpetuals** (the perp leg matters if a funding-carry-style strategy is ever the
one validated). Secondary: **OKX demo** (simulated trading on real live prices, demo API keys) —
a clean fallback; its connector is a ~15-line signer swap from Bybit's.

| Venue | Demo API | Spot | Perps | Notes |
|---|---|---|---|---|
| **Bybit** | `api-demo.bybit.com` | ✓ | ✓ | Keys from the **Demo Trading** module on bybit.com (NOT testnet.bybit.com); recommended |
| **OKX** | demo flag on `www.okx.com` API | ✓ | ✓ | Real live prices; good fallback |
| Binance | Spot Testnet | ✓ | testnet | More manual-oriented; usable with caveats |

Whichever account confirms first, tell me and I build that exact connector.

## Env vars (add to `.env` only when keys exist; never commit real values)
```
DEMO_VENUE=bybit                 # bybit | okx
BYBIT_DEMO_API_KEY=              # a DEMO key — trade permission, NO withdrawal
BYBIT_DEMO_API_SECRET=
# OKX alternative:
# OKX_DEMO_API_KEY=
# OKX_DEMO_API_SECRET=
# OKX_DEMO_API_PASSPHRASE=
```

## Activation checklist (when your account confirms)
1. In the exchange UI, create a demo API key. On **Bybit**: log in at bybit.com → switch to the
   **Demo Trading** module (a separate demo account) → hover avatar → **API** → create key. Enable
   **trade** permission; **disable withdrawal/transfer**. Copy key + secret into `.env`. (Use the
   Demo Trading module, not testnet.bybit.com — testnet keys are meaningless here. Demo
   orders/data persist ~7 days.)
2. Run **`python scripts/demo_preflight.py`** (built now). It verifies, without placing any order:
   - you are pointed at the **demo host** (never mainnet);
   - the connection + signing work;
   - the key is **safe** — trade-only, no withdrawal permission;
   - your demo balances are visible.
3. Only after preflight is green do we build/enable the **execution adapter** that routes the
   paper lane's orders to the demo endpoint (a scoped follow-up, behind the same gate guard as
   the local simulator). It stays inert until you switch the lane mode on.
4. Run the strategy on the demo lane for the defined stability window; compare demo fills vs the
   backtest via the existing divergence report.

## What is built now vs later
- **Now (safe, no venue):** this plan + `scripts/demo_preflight.py` + its offline tests.
- **When keys confirm:** the venue-specific signer is already the recommended Bybit one; OKX is a
  small swap.
- **After preflight green + your go:** the execution adapter (order routing) — not before.
