# Operator Access Prep Checklist — 2026-07-11

## Scope

This checklist prepares future Trading OS platform work without enabling any
connection today. It records official entry points, reserved environment-variable
names, and the human decisions that must still happen before an agent can use any
credential.

No secret, API key, private key, passphrase, wallet credential, exchange password,
withdrawal permission, live-trading permission, or real-money authorization belongs
in Git, chat, screenshots, Markdown, logs, or retained artifacts.

## Current binding state

- S2 remains constrained: no validated strategy, no venue connection, no order
  routing, no paper/demo/testnet activation, no live trading, and no real money.
- The canonical S1/S2 crypto-spot dataset remains Binance public Spot data and
  requires no credential.
- `.env.example` now contains only commented, inactive future variable names.
- `.env` and local secret files remain gitignored.

## What the operator can prepare now

1. Create accounts with candidate exchanges and data vendors, but do not create
   API keys until a later gate asks for the exact key type.
2. Verify country/account eligibility, product access, API terms, fee tier,
   tax/accounting constraints, and support for API key restrictions.
3. Prepare a password-manager vault/folder for future Trading OS credentials.
4. Prefer separate subaccounts, demo accounts, or sandbox-only credentials when
   a future gate approves a connection.
5. When keys are eventually created, start with read-only where possible, bind
   IP addresses where supported, use the narrowest permissions, and keep
   withdrawal permissions disabled.

## Exchanges and venues

| Integration | Prepare now | Future credential gate | Reserved names |
|---|---:|---|---|
| Binance public Spot data | No account needed | None for frozen public data | Not applicable |
| Binance Spot Testnet | Optional account/login prep only | S3+ paper/demo gate; testnet only | `BINANCE_SPOT_TESTNET_API_KEY`, `BINANCE_SPOT_TESTNET_API_SECRET` |
| Kraken | Account eligibility review only | Private/account/trading gate; never withdrawal | `KRAKEN_API_KEY`, `KRAKEN_API_SECRET` |
| Coinbase Advanced Trade | Account/product/API eligibility review only | Private/account/trading gate; exact CDP key handling reverified then | `COINBASE_CDP_API_KEY_NAME`, `COINBASE_CDP_PRIVATE_KEY` |
| OKX Demo Trading | Demo/account eligibility review only | S3+ paper/demo gate; demo only | `OKX_DEMO_API_KEY`, `OKX_DEMO_API_SECRET`, `OKX_DEMO_API_PASSPHRASE` |

Official references checked 2026-07-11:

- Binance public data: `https://github.com/binance/binance-public-data`
- Binance public data portal: `https://data.binance.vision/`
- Binance Spot Testnet: `https://developers.binance.com/docs/binance-spot-api-docs/testnet/general-info`
- Kraken API key creation: `https://support.kraken.com/articles/360000919966-how-to-create-an-api-key`
- Coinbase Advanced Trade API: `https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/overview`
- OKX API guide / Demo Trading API: `https://www.okx.com/docs-v5/en/`

## Paid or external market-data providers

| Provider | Prepare now | Future credential gate | Reserved names |
|---|---:|---|---|
| CoinAPI | Account/pricing review only | Approved dataset/license/spend gate | `COINAPI_API_KEY` |
| Kaiko | Account/pricing review only | Approved dataset/license/spend gate | `KAIKO_API_KEY` |
| Tardis.dev | Account/pricing review only | Approved dataset/license/spend gate | `TARDIS_API_KEY` |
| Databento | Account/pricing review only | Approved dataset/license/spend gate | `DATABENTO_API_KEY` |

Official references checked 2026-07-11:

- CoinAPI docs: `https://www.coinapi.io/docs`
- CoinAPI Market Data API: `https://www.coinapi.io/products/market-data-api/docs/rest-api`
- Kaiko API key docs: `https://docs.kaiko.com/stream/general/general-information/api-key`
- Tardis.dev HTTP API: `https://docs.tardis.dev/api/http-api-reference`
- Databento quickstart: `https://databento.com/docs/quickstart`
- Databento official Python client: `https://github.com/databento/databento-python`

## Non-exchange services

- MLflow/DVC remain local-first for the current prototype; no hosted credentials
  are needed now.
- AI-provider credentials are handled by the existing AI benchmark gate and are
  intentionally not expanded in this checklist.
- Hosted infrastructure, notifications, object storage, cloud databases, and
  monitoring vendors remain deferred until a specific architecture decision says
  local mode is insufficient.

## Future-agent rule

Before using any variable reserved here, a future agent must reverify official
docs, confirm the operator decision artifact, confirm `.env` contains the key
without printing it, and prove that the code path cannot route live orders or
real money unless a later human gate explicitly approved that exact capability.
