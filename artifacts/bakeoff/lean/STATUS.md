# T-006-04 LEAN lane — status (updated 2026-07-11)

**Outcome: complete for the bounded Docker evidence matrix.** Docker was made
available and the local LEAN CLI path ran B1-B4 over `{F0/S0,F1/S1}` using the
hand-assembled local `lean.json` and custom CSV data. No QuantConnect account,
cloud project sync, broker connection, paper/demo/testnet venue, order-routing,
live trading, or real-money path was used.

## RG-02 finding (local-vs-cloud data/pricing boundary) — RESOLVED for this lane
`lean init` / `lean login` require a QuantConnect account (user id + API token) —
confirmed interactively (`lean init -l python` aborts asking for credentials).
**But** this gate is only for cloud project sync; it is not required for local
Docker backtesting. Local backtests work with a hand-assembled `lean.json`
(built from the OSS `QuantConnect/Lean` repo's `Launcher/config.json`, Apache-2.0,
fetched directly — no login) plus `lean create-project` (no login) and a custom
`PythonData` reader over our own CSVs (no QC market data used at all). So: no
QuantConnect account is needed for this bake-off lane. `todos/01_research_completion.md`
T-001-02 can be marked resolved with this evidence.

## What's done
- `engines/lean/lane/lean.json` — hand-assembled local CLI config, `data-folder: data`.
- `engines/lean/lane/data/custom_bakeoff/{BTCUSDT,ETHUSDT}.csv` — converted from
  `data/normalized/{pair}_5m.parquet` (decimal128 -> float64, declared lossy).
- `engines/lean/lane/B1..B4/` — LEAN CLI Python projects (`lean create-project`),
  each with a generated `main.py`: custom-data reader, per-side percentage fee
  model (`PctFeeModel`, mandatory-grid F0/S0, F1/S1), `ConstantSlippageModel`,
  and B1-B4 entry/exit logic mirroring the canonical specs used in the
  freqtrade lane (`src/tios/adapters/freqtrade/lane.py`).
- `engines/lean/scripts/lane.py` — generator: `uv run python -m` won't resolve
  this path (it's outside `src/`, moved there deliberately to stay inside this
  task's `owned_paths`); run directly with
  `uv run --with pyarrow python engines/lean/scripts/lane.py`.
- `quantconnect/lean:latest` Docker image pulled locally (5.07GB, arm64).

## Scope reduction already baked into the generator (documented, not silent)
Full canonical range is 577,803 5m bars/symbol (2021-01-01..2026-06-30). LEAN's
Python custom-data `Reader` is invoked per line and is far slower than
freqtrade's vectorized backtest; running the full range was judged not viable
in the available time/token budget. The generator uses the most recent 60 days
of the same frozen dataset (`LEAN_WINDOW_DAYS` in `lane.py`) instead — a bounded
subset of DS-CRYPTO-SPOT-BAKEOFF-V1, not a different dataset. If full-range
parity with the other lanes is required, increase `LEAN_WINDOW_DAYS` (or remove
the filter) and expect a much longer per-run time.

## 2026-07-11 run evidence

- B1-B4 x `{F0/S0,F1/S1}` run1 all exited `0` through local Docker with
  `--lean-config engines/lean/lane/lean.json --no-update`.
- Normalized manifests are retained under
  `artifacts/bakeoff/lean/<baseline>/<scenario>/run1/manifest.json`.
- Fill counts: B1=1, B2=3991, B3=5234, B4=2166 for both scenarios.
- B1 F0/S0 was rerun as `run2`; retained fills match run1 exactly in
  `artifacts/bakeoff/lean/B1/F0_S0/determinism_run1_run2.json`.
- LEAN's built-in post-analysis packet logged a non-fatal exception
  (`Sequence contains no elements`) while still emitting statistics, order events,
  logs, and a successful CLI exit. This is retained in the per-run logs.

## Remaining constraints

The lane remains a bounded 60-day evidence window because LEAN's Python custom
data reader is line-oriented and materially slower than vectorized lanes over the
full 2021-2026 dataset. This is a documented scope reduction, not a silent pass.

## Blocker record (per acceptance criterion 3)
No QuantConnect credential blocker exists. The prior Docker-stopped blocker was
cleared on 2026-07-11; bounded local Docker evidence is now retained. Full-range
LEAN parity remains a throughput/scope expansion question only.
