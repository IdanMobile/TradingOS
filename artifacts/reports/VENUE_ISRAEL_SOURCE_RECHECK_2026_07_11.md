# Venue Israel source recheck - 2026-07-11

## Scope

Operator decision `T-001-03 authorize_source_recheck` allows official-source
venue availability research only. No account opening, credentials, venue
connection, paper/demo/testnet, order routing, or trading path was enabled.

## Sources checked

| Venue | Official source | Finding |
|---|---|---|
| Kraken | `https://support.kraken.com/articles/where-is-kraken-licensed-or-regulated` | Kraken says it welcomes clients globally with specific exceptions and that verified residency may create account/product restrictions. Israel was not identified as a prohibited jurisdiction in the checked official source. |
| Kraken | `https://support.kraken.com/articles/360000381846-cash-deposit-options-fees-minimums-and-processing-times-` | Funding availability is region-specific and users are directed to geographic restrictions and provider-specific support pages. This keeps funding method eligibility as account/product-specific. |
| Coinbase | `https://help.coinbase.com/en/coinbase/managing-my-account/other/prohibited-regions` | Coinbase restricts access in prohibited regions. Israel was not identified in the checked prohibited-region source. |
| Coinbase | `https://help.coinbase.com/en/coinbase/getting-started/getting-started-with-coinbase/id-doc-verification-row` | Coinbase lists Israel among accepted foreign identity-document countries for verification. This is identity-document support, not a full trading/account eligibility guarantee. |
| Coinbase Prime | `https://help.coinbase.com/prime/get-started/id-verification` | Coinbase Prime lists Israeli driver's license, passport, and national ID card as accepted identity documents. This is not a retail trading approval. |

## Verdict

- Kraken is no longer demoted on the basis of Israel availability in the
  official-source slice checked here.
- Coinbase should be upgraded from "likely Israel-unavailable" to
  "identity-document support found; retail/product eligibility remains
  account-specific and human-gated."
- This does not select a paper venue. S3 paper-lane work still requires S2 exit,
  HG-3, a validated strategy, operator account checks, terms review, permissions,
  and explicit approval.

## Follow-up boundary

Before any S3 paper venue selection, the operator must still verify exact
account eligibility, product availability, API trading permissions, automated
trading terms, and fee tier in the operator's actual account. No AI agent can
complete those human/account-specific checks from public docs.
