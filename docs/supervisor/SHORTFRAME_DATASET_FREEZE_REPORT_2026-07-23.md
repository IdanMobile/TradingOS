# Short-Frame Dataset Freeze Report — 2026-07-23

Status: `VERIFIED`

Dataset: `DS-CRYPTO-SPOT-SHORTFRAMES-V1`

Execution authority: `NONE`

## Supervisory conclusion

Verified fact: the bounded BTCUSDT/ETHUSDT 1m/5m/15m dataset freeze completed successfully
at 2026-07-23 03:58:06 UTC. The published dataset contains six Parquet tables, 7,318,824
rows, and 393,818,589 bytes covering 2021-01 through 2026-06, with a strict cutoff at
2026-07-01 00:00:00 UTC.

Inference: this materially improves the system's reproducible short-frame research and
backtesting input surface. It does not, by itself, show that any strategy has edge or that
any service is ready to consume the data.

## Frozen evidence chain

Verified facts:

- Code identity:
  `977791f3ef458cc317137a0f663adba5500395d5`
  (`git_state=committed`, `git_commit_valid=true`).
- Official-checksum-required 1m proof:
  `data/raw/manifests/klines/raw_manifest_2d8fb43921fd2c0537f439e1b8b30ef54ae44d4e7fb7b2192fabc43c55ef4834.json`
  with SHA-256
  `2d8fb43921fd2c0537f439e1b8b30ef54ae44d4e7fb7b2192fabc43c55ef4834`.
- The raw proof binds 396 monthly archives: 132 one-minute archives with official checksum
  verification and 264 retained 5m/15m archives matched to canonical bake-off raw authority.
- Dataset manifest:
  `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest_05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4.json`
  with SHA-256
  `05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4`.
- Quality report:
  `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT_cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186.json`
  with SHA-256
  `cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186`.
- The stable manifest and quality-report files have the same hashes as their
  content-addressed copies.

## Per-table audit

All tables start at 2021-01-01 00:00:00 UTC. Each table ends at the final aligned open
strictly before the common cutoff.

| Table | Rows | Bytes | Parquet SHA-256 | Logical SHA-256 | Gaps / missing bars | Pinned early closes |
|---|---:|---:|---|---|---:|---:|
| BTCUSDT 1m | 2,889,007 | 154,474,085 | `687365f487d40e96e4605afd7fde6b5f259c2260ca14cbe5f543e5e93ed51725` | `04a313511fed2423cc428571b31eab4c64b9810232ab87bc042ca5585cd0bedf` | 7 / 1,073 | 5 |
| BTCUSDT 5m | 577,803 | 35,542,487 | `d4d6b3306c44e242f3fb7f71c44bacabf9a6af1f1f8d507ca2de0853b6a727d0` | `3ec05eb0ea618310209ae92de4bf1940b929ed2c889bccb0b3f749ff0a8a17fa` | 7 / 213 | 5 |
| BTCUSDT 15m | 192,602 | 13,541,836 | `3c39eb7e988f5f9740260ce89cb53ea2e4ad152df576e4691f483997b6151821` | `f8126080e029281a5a8982fc3311cbd8d573d04be74ccc248e709c28b7ccb2e5` | 7 / 70 | 5 |
| ETHUSDT 1m | 2,889,007 | 143,942,836 | `46cc5fd8e1722db4616160763324e8d13ea105c46277531b04b67a584e425233` | `7298d2d48fdea149f9b5b6b3a6e907be400bf52d4f4a33646f0cdce0fcf3f9fb` | 7 / 1,073 | 5 |
| ETHUSDT 5m | 577,803 | 33,450,877 | `79c4678cebf490b82e3adb34c31f8e696bf14f6d35ddd3bdfa09658078d68dff` | `c4ca5cb07e5a4f09d87207639a16ffcba1eccbdd9ec0a85b55be16e80ea841f5` | 7 / 213 | 5 |
| ETHUSDT 15m | 192,602 | 12,866,468 | `230e7ef993e70ffc708ab61bb18fbfdbe9de6d71ae31d9a78535cde20e1d5759` | `5489b08439c2dc4f3b2a57842f06b8da7ae0d8a9eabf6681f7314b1ece55e025` | 7 / 70 | 5 |
| **Total** | **7,318,824** | **393,818,589** | — | — | **42 / 2,712** | **30** |

Verified fact: gaps are informational and were not filled. The freeze did not synthesize
candles or modify retained source close timestamps.

## Failed-closed attempts and bounded corrections

Verified facts:

1. The first production dry run stopped during canonical authority verification before
   publication. Identical logical rows had been read with different Arrow chunk boundaries.
   Commit `5ff3b38b1d5c76638649bfa9f914892c0d03f8dd` made the three Parquet reread hashes
   chunk-invariant without changing the legacy retained hash contract.
2. The second production attempt stopped during staged quality validation before
   publication. The validator treated every non-nominal terminal close as invalid.
   Commit `977791f3ef458cc317137a0f663adba5500395d5` authenticated and pinned all 30 exact
   early closes and enforced the bounded source contract
   `open <= close < open + timeframe` with exact production inventory reconciliation.
3. The next production run passed and published the dataset and its content-addressed
   evidence.

Unknown: the retained source evidence establishes the exact timestamps and archive hashes,
but it does not establish why the upstream source produced those 30 early-close values.
This report makes no exchange-incident or causal claim.

## Verification gates

Verified facts:

- Both full regenerations passed exact table-grid, identical-schema, coverage, UTC,
  row-identity, OHLC, nonnegative-volume, alignment, source-unit, source-row-accounting,
  cutoff, null, duplicate, fsync, and source-lineage checks.
- The two regenerations produced identical logical hashes for all six tables.
- The 5m and 15m table logical hashes matched the retained canonical bake-off authority.
- All 30 expected early closes were present with exact symbol, timeframe, open, close,
  source path, and source SHA-256. Missing, unexpected, changed, invalid-bound, and
  source-mapping-failure counts were all zero.
- Normal millisecond and microsecond terminal-close precision remained accepted and
  preserved.
- The production quality report status is `PASS`; execution authority is `NONE`.

## Frozen output locations

The dataset publisher treats an existing mismatching output as a hard failure rather than
replacing it. The authoritative published table directory is:

`data/normalized/DS-CRYPTO-SPOT-SHORTFRAMES-V1/`

The content-addressed manifest and quality report listed above are the immutable evidence
records. Their stable-name counterparts are:

- `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest.json`
- `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT.json`

These locations must not be edited in place. Any future dataset version requires a new,
explicitly governed evidence cycle.

## Operational implications

Verified facts from the post-freeze service/readiness recheck:

- Exactly one dashboard, demo-lane, job-worker, and orchestrator process was present.
- The dashboard shell and API probe passed.
- The orchestrator was fresh and not halted.
- Jobs status was `AVAILABLE` with integrity `PASS`: four succeeded, one cancelled, and
  zero failed, queued, or running.
- The demo lane was `RUNNING` with fake money, `promotion_eligible=false`, and the active
  disaster stop retained.
- Overall readiness reported `operational=true`, status `AUTHORITY_GATED`, and execution
  authority `NONE`.
- The only external-intake gate was
  `ROOT_OWNED_ACTIVATION_AUTHORITY_NOT_INSTALLED`.
- No service restart was needed.

Inference: consumers can now be evaluated against a stable six-table short-frame dataset,
and the existing services were healthy at the recheck time. This point-in-time health does
not prove future liveness, strategy validity, profitability, or authority. Dashboard 1m
integration is not authorized by this freeze.

The dashboard integration surface is integrity-controlled:
`src/tios/services/dashboard_ui/server.py`,
`src/tios/services/dashboard_ui/dashboard.html`,
`src/tios/services/dashboard_api/status.py`, and
`tests/test_dashboard.py` are manifest-listed, while
`PACKAGE_INTEGRITY_MANIFEST.md` is immutable to the orchestrator. A dashboard 1m change
therefore requires a new, explicit, narrow operator integrity exception before edits.

## Limitations and unknowns

- No strategy was created, selected, approved, promoted, or scored by this freeze.
- No backtest result, paper/demo result, profitability result, or future return is implied.
- No venue, credential, wallet, bot, order, or live-trading authority was enabled.
- The observed gaps remain in the data and must be handled explicitly by every consumer.
- The service/readiness result is a point-in-time observation, not a continuity guarantee.
- `PROJECT_STATE.md` has not been updated for this result because it is integrity-controlled;
  until a separately authorized reconciliation, it remains stale relative to this report.

## Next safe action

Commit exactly this bounded durable evidence set:

- `PACKAGE_CHANGELOG.md`
- `docs/supervisor/SHORTFRAME_DATASET_FREEZE_REPORT_2026-07-23.md`
- `handoffs/SESSION_HANDOFF_2026_07_23_SHORTFRAME_FREEZE.md`
- `data/raw/manifests/klines/raw_manifest_2d8fb43921fd2c0537f439e1b8b30ef54ae44d4e7fb7b2192fabc43c55ef4834.json`
- `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest.json`
- `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest_05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4.json`
- `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT.json`
- `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT_cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186.json`

The six normalized Parquets under
`data/normalized/DS-CRYPTO-SPOT-SHORTFRAMES-V1/` remain ignored, local frozen data; do not
stage or commit them.

Keep dashboard 1m integration gated until the operator grants a separate narrow integrity
exception, and keep external activation gated until the root-owned authority is installed
through its separate ceremony. Do not infer live authority from a healthy service or a
passing dataset gate.
