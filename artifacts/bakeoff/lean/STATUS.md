# T-006-04 LEAN lane — status (2026-07-07, attempt 3)

**Outcome: incomplete.** Environment/mechanism proven; no backtest executed yet.
Prior attempts 1-2 failed on session rate limits before any lane work started.
This attempt ran out of task budget mid-implementation, after the (slow, ~35min)
`quantconnect/lean:latest` Docker pull finally completed. Recorded here so the
next attempt does not repeat the investigation.

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

## Not done — what the next attempt should do first
1. Run `engines/lean/.venv/bin/lean backtest engines/lean/lane/B1 --parameter fee_rate 0 --parameter slippage_bps 0 --parameter scenario_id F0_S0 --parameter run_tag run1` (image is already pulled, so this should compile+run without a further multi-GB download).
2. This is unverified: whether `self.history(symbol, N, Resolution.MINUTE)` returns a
   DataFrame with `"close"`/`"high"` columns for a *custom* `PythonData` symbol (used
   in B2-B4's indicator logic) has not been confirmed against a real run — B1 (no
   history() call) is the right first smoke test before trusting B2-B4.
3. Once B1 runs clean, repeat for B2-B4 x {F0/S0, F1/S1}, then call
   `normalize_result()` in `engines/lean/scripts/lane.py` per run to produce the
   canonical `trades`/`manifest.json` artifacts under `artifacts/bakeoff/lean/<baseline>/<scenario>/<run_tag>/`,
   then rerun one config a second time to check byte-identical determinism
   (blueprint gate).
4. If `history()` on custom data doesn't expose named columns, the fallback is to
   maintain per-symbol Python `deque`s of the last N closes/highs manually inside
   `on_data` instead of calling `self.history()` — more code, but removes the
   dependency on that API's behavior with custom data types.

## Blocker record (per acceptance criterion 3)
No QuantConnect credential blocker exists: the lane is designed for local Docker
execution with custom data. The current environment does have an execution blocker:
the first smoke command using `--lean-config engines/lean/lane/lean.json` returned
`Please make sure Docker is installed and running` on 2026-07-10. Resume T-006-04
by starting Docker, then rerun B1 before attempting B2-B4. This is an environment
state blocker, not a missing account or data-source decision.
