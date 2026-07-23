# Session Handoff — Short-Frame Dataset Freeze — 2026-07-23

## Current state

The production `DS-CRYPTO-SPOT-SHORTFRAMES-V1` freeze is complete and verified:

- six BTCUSDT/ETHUSDT 1m/5m/15m Parquet tables;
- 7,318,824 rows and 393,818,589 bytes;
- fixed 2021-01 through 2026-06 window with 2026-07-01 UTC cutoff;
- two complete regenerations with identical logical hashes;
- canonical bake-off logical equality for 5m/15m;
- exactly 30 authenticated and pinned early closes, with exact inventory reconciliation;
- observed gaps retained and unfilled;
- execution authority `NONE`.

The complete audit is:

`docs/supervisor/SHORTFRAME_DATASET_FREEZE_REPORT_2026-07-23.md`

## Post-freeze service/readiness recheck

The recheck completed without restarting any service:

- exactly one dashboard, demo-lane, job-worker, and orchestrator process;
- dashboard shell/API probe `PASS`;
- orchestrator fresh and not halted;
- jobs `AVAILABLE`, integrity `PASS`, with four succeeded, one cancelled, and zero failed,
  queued, or running;
- demo lane `RUNNING` with fake money, `promotion_eligible=false`, and active disaster stop;
- readiness `operational=true`, status `AUTHORITY_GATED`, execution authority `NONE`;
- only external-intake gate:
  `ROOT_OWNED_ACTIVATION_AUTHORITY_NOT_INSTALLED`.

This is a point-in-time health result, not strategy, profitability, continuity, promotion,
or execution authority.

## Evidence pointers

- 1m raw proof SHA-256:
  `2d8fb43921fd2c0537f439e1b8b30ef54ae44d4e7fb7b2192fabc43c55ef4834`
- Dataset manifest SHA-256:
  `05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4`
- Quality report SHA-256:
  `cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186`
- Published tables:
  `data/normalized/DS-CRYPTO-SPOT-SHORTFRAMES-V1/`
- Content-addressed evidence:
  `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest_05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4.json`
  and
  `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT_cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186.json`

## Implementation commits

1. `cb5a6451075365ce50b63174fcc532b14653c031` —
   bounded short-frame freeze capability.
2. `5ff3b38b1d5c76638649bfa9f914892c0d03f8dd` —
   chunk-invariant logical hashes at Parquet reread boundaries.
3. `977791f3ef458cc317137a0f663adba5500395d5` —
   verified early-close source evidence and bounded close semantics.

The first two production attempts failed closed before publication. The first exposed
Arrow chunk-boundary sensitivity at canonical reread; the second exposed an incorrect
nominal-close-duration assumption. The bounded corrections above were reviewed and tested
before the successful freeze.

## Integrity-control note

`PROJECT_STATE.md` remains stale relative to the completed freeze and was deliberately not
modified. It is listed in `PACKAGE_INTEGRITY_MANIFEST.md`; the manifest itself is an
orchestrator-immutable path. This handoff and the supervisor report are the current durable
authority for this completed dataset task until an operator-authorized state reconciliation.

Dashboard 1m integration remains gated. It would require changes across the protected
UI/server/status/test surface, including:

- `src/tios/services/dashboard_ui/server.py`
- `src/tios/services/dashboard_ui/dashboard.html`
- `src/tios/services/dashboard_api/status.py`
- `tests/test_dashboard.py`

Those paths are integrity-manifest-listed, and `PACKAGE_INTEGRITY_MANIFEST.md` is immutable
to the orchestrator. Do not begin dashboard 1m integration without a new, explicit, narrow
operator integrity exception naming the exact files and rehash obligation.

## What has not been done

- No dashboard 1m integration has been implemented.
- No strategy validity, edge, profitability, or promotion claim was created.
- No bot, venue, credential, wallet, order, paper/demo promotion, or live authority was
  enabled.
- The source evidence does not explain why the upstream early-close timestamps occurred;
  no incident-reason claim is authorized.

## Next safe action

1. Commit exactly these eight durable evidence files:
   - `PACKAGE_CHANGELOG.md`
   - `docs/supervisor/SHORTFRAME_DATASET_FREEZE_REPORT_2026-07-23.md`
   - `handoffs/SESSION_HANDOFF_2026_07_23_SHORTFRAME_FREEZE.md`
   - `data/raw/manifests/klines/raw_manifest_2d8fb43921fd2c0537f439e1b8b30ef54ae44d4e7fb7b2192fabc43c55ef4834.json`
   - `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest.json`
   - `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.manifest_05ccd69008c54f14f3b3299226e27c313d60fa224bf9b701e11ecc92beec7ce4.json`
   - `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT.json`
   - `artifacts/datasets/DS-CRYPTO-SPOT-SHORTFRAMES-V1.QUALITY_REPORT_cd281975e187f8e1cf43fd62fe03585891cf8c02cd44baf319575e42837f1186.json`
2. Leave all six Parquets under
   `data/normalized/DS-CRYPTO-SPOT-SHORTFRAMES-V1/` ignored and local. They are frozen
   dataset bytes, not commit content.
3. If dashboard 1m integration is still desired, request a separate narrow operator
   integrity exception before editing any listed path.
4. Keep external intake authority gated until the root-owned activation authority is
   installed through its separate operator ceremony.

Do not treat a healthy service, passing dataset gate, or demo process as evidence of
profitability or live-trading authority.
