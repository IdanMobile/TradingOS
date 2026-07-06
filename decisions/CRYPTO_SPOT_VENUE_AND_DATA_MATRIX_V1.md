# Crypto Spot Venue & Data Decision Matrix V1

Date: 2026-07-05
Decision status: Shortlist only. No live venue approved.

## Hard gates for a live venue
A venue must pass all of the following before live approval:
1. Operator/account eligibility from Israel is verified for the exact account.
2. Spot product and required pairs are available.
3. API trading is allowed for the account/product.
4. Automated-trading terms are acceptable.
5. Fee schedule is captured for the actual account tier.
6. REST/WebSocket reliability is proven in our own soak tests.
7. Required order types and filters are mapped.
8. Deposit/withdrawal and quote-asset workflow is workable.
9. Tax/accounting exports are operationally acceptable.
10. Contract tests and kill-switch behavior pass.

## Technical shortlist

| Candidate | API breadth | Real-time feeds | Testing path | Strength | Main unresolved issue | Status |
|---|---|---|---|---|---|---|
| Binance Spot | Very strong | Strong | Spot Testnet | Broad API surface, filters, active changelog | Operator eligibility, account fit, realistic testnet behavior | TECHNICALLY_SHORTLISTED |
| Kraken Spot | Very strong | Strong | UAT/testing material must be mapped exactly | REST/WS/FIX, L3 guidance, automated trading support | Operator eligibility, exact pair/fee fit | TECHNICALLY_SHORTLISTED |
| Coinbase Advanced | Strong | Strong | Exact sandbox/paper path needs verification | Official API + Python SDK | Operator eligibility, fee fit, paper parity | CANDIDATE |
| OKX Spot | Strong | Strong | Demo API keys | Unified V5 API, demo mode | Operator eligibility, account/product fit | CANDIDATE |

## Provisional ranking for bake-off connectivity tests
1. Kraken
2. Binance
3. Coinbase
4. OKX

This ranking is **not** a live-exchange recommendation. It only prioritizes which adapters to test first based on current documented API capability and the need to diversify beyond one venue.

## Data-tier decision

| Tier | Purpose | Preferred initial source | Approval state |
|---|---|---|---|
| 0 | Candles/basic trades for engine parity | Native exchange historical endpoints/downloads | APPROVED FOR BAKE-OFF WHERE COVERAGE SUFFICES |
| 1 | Normalized multi-venue crypto history | CoinAPI / Kaiko shortlist | UNRESOLVED |
| 2 | Tick and order-book replay | Tardis.dev leading candidate | VALIDATED CANDIDATE, PURCHASE NOT APPROVED |
| 3 | Future multi-asset expansion | Databento | VALIDATED FUTURE CANDIDATE |

## Decision
- No paid data purchase yet.
- No live venue approval yet.
- Engine bake-off starts with Tier 0 data.
- The first strategy requiring microstructure must trigger a Tier 2 data decision.
