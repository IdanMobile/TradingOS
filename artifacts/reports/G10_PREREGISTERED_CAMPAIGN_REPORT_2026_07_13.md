# Preregistered G10 campaign report — 2026-07-13

Campaign: `SEARCH-BASELINE-G10-REPRO-V1`

Run commit: `77827521c09c2ffeee7f12490a9ef2ec3555d474`

Status: **COMPLETED / METHOD_BLOCKED**

Authority: `execution_authority=NONE`, `promotion_eligible=false`, no winner

## What was tested

The campaign reproduced the frozen 66-trial legacy vectorbt accelerator population:

- B2 moving-average crossover proxy: 34 trials
- B3 Bollinger mean-reversion proxy: 16 trials
- B4 volatility-breakout proxy: 16 trials

Selection, both CSCV/PBO halves, and DSR used non-annualized per-bar Sharpe within
each family. No global 66-trial winner was selected. The run used the frozen
BTCUSDT 5-minute dataset, the pinned retained lab, and the exact F1/S0 fee-only
proxy environment. No network, venue, credential, or order path was used.

## Results

| Family | Selected proxy | Raw / effective trials | PBO | DSR | Numeric result | Gate |
|---|---|---:|---:|---:|---|---|
| B2 | `fast=15,slow=60` | 34 / 11.7340 | 0.2960 | 0.0 | FAIL | METHOD_BLOCKED |
| B3 | `window=3,deviation=1.5` | 16 / unavailable | 0.0163 | withheld | METHOD_BLOCKED | METHOD_BLOCKED |
| B4 | `lookback=3,exit_window=10` | 16 / 7.7053 | 0.3810 | 0.0 | FAIL | METHOD_BLOCKED |

B3 contains undefined trial correlations caused by no-trade/constant-return trials,
so its effective-trial estimate and DSR are correctly withheld.

## Supervisory interpretation

The declared 66-trial artifact scope is complete and internally verifiable, and every
family has an immutable all-trial input, result hash, and validated metadata sidecar.
An exact rerun is still local-only because the hashed source dataset and pinned virtual
environment are retained on this machine but are not distributed through Git or DVC.
The outcome does **not** complete G10 because the historical process that admitted these
three families was not retained.

These are also legacy accelerator proxies, not canonical strategy reproductions:
they fill on the signal-bar close rather than next-bar open, B2 uses a crossover event
rather than its declared eligible state, and the cost scenario omits slippage. The
campaign therefore answers only whether the old proxy population survives the corrected
family-level statistics. It does not—and no further parameter mining is justified.

## Evidence

The immutable campaign index is:

`artifacts/validation/campaigns/SEARCH-BASELINE-G10-REPRO-V1/campaign_index_4caf259b6485b57f7838ad0887c9ffa44b879a8155316dce2cacb26db18b4f57.json`

`scripts/run_preregistered_g10_campaign.py --verify-only` recomputes every referenced
input/result/metadata hash and re-runs the fail-closed substantive-research metadata
validator.

## Next action

Do not expand these proxy grids. If baseline-strategy conformance is still valuable,
create a new preregistered campaign using canonical next-bar-open semantics, B2's declared
state rule, a canonical F1/S1-or-stricter cost scenario, and distributable frozen data.
Keep that work separate from funding-carry or other strategy-family research.
