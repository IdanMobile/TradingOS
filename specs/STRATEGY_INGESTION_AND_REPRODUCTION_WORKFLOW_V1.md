# Strategy Ingestion & Reproduction Workflow V1

Status: Planning approved; automation not yet approved.

## Objective
Turn external strategies, indicators, methods, papers, scripts, repositories and community ideas into provenance-preserving internal hypotheses without importing claimed profitability.

## Canonical lifecycle
```text
DISCOVERED
  ↓
SOURCE_CAPTURED
  ↓
LICENSE_CHECKED
  ↓
SEMANTIC_EXTRACTED
  ↓
AMBIGUITIES_RECORDED
  ↓
CANONICAL_SPEC_CREATED
  ↓
REFERENCE_REPRODUCED
  ↓
PARITY_CHECKED
  ↓
INTERNAL_BASELINE_RUN
  ↓
VALIDATION_ELIGIBLE or REJECTED
```

## Source classes
1. Primary academic paper.
2. Official framework/reference implementation.
3. Maintained open-source implementation.
4. Transparent community script.
5. Social/forum description.
6. Proprietary or opaque claim.

## Required source record
```yaml
source_id: SRC-...
source_class: official_framework
url: ...
title: ...
author: ...
published_at: ...
retrieved_at: 2026-07-05
license: ...
version_or_commit: ...
market_claimed: ...
timeframe_claimed: ...
profit_claims_inherited: false
```

## Canonical strategy specification
Every reproduced strategy should be translated into a framework-neutral spec before cross-engine testing:

```yaml
strategy_id: STRAT-...
family: mean_reversion
inputs:
  - close
  - volume
indicators:
  - name: bollinger_bands
    parameters: {window: 20, std: 2}
entry_long:
  all:
    - close < lower_band
exit_long:
  any:
    - close >= middle_band
position_sizing:
  type: fixed_fraction
risk:
  stop_loss: null
  take_profit: null
assumptions:
  - signal evaluated at bar close
ambiguities: []
```

## Reproduction gates
| Gate | Requirement |
|---|---|
| Source fidelity | Rules match source meaning |
| Syntax | Reference implementation runs where possible |
| Semantic parity | Observable trades reflect stated rules |
| Timing | No accidental same-bar/future information |
| Costs | Fees/slippage are explicit |
| Warm-up | Indicator warm-up is explicit |
| Data | Required fields and resolution are explicit |
| License | Reuse/derivation path is documented |

## First manual seed batch
Use a deliberately mixed sample:
- 2 QuantConnect Strategy Library items
- 2 official Freqtrade repository strategies
- 2 Hummingbot controllers
- 2 open-source Pine strategies
- 2 academic-paper strategies

Purpose: test the workflow before building automated ingestion.

## Automation rule
Do not build a mass scraper/importer until the manual seed batch reveals stable schemas, recurring ambiguities, and license-handling requirements.
