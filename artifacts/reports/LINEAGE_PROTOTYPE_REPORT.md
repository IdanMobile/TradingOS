# Lineage Prototype Report

Status: **COMPLETE — all seven acceptance gates evaluated**
Date: 2026-07-10

Decision: `MLFLOW_PLUS_DVC_RECOMMENDED`

## Executed composition

- MLflow 3.14.0: local SQLite run metadata and local filesystem artifacts.
- DVC 3.66.1: frozen BTCUSDT 5m Parquet snapshot in a local Git repository
  with a local DVC remote.
- Trading Evidence Registry: one thin JSONL domain record containing only public
  MLflow and DVC references.
- No cloud account, paid service, API credential, or live-trading capability.

The complete machine-readable result is
`artifacts/lineage/prototype/prototype_result.json`. The prototype is rerunnable
with `scripts/run_lineage_prototype.py`; MLflow and DVC are injected with `uv`
and were not added to the product runtime.

## Test A — deterministic strategy lineage

Two retained Freqtrade B2 F0/S0 runs were logged as separate MLflow runs with:

- project Git commit;
- dataset ID, SHA-256, DVC Git revision and tracked-file reference;
- strategy/version, engine, MA parameters, fee/slippage assumptions;
- normalized metrics and tracking runtime;
- trade, equity, metric, and manifest artifacts.

MLflow returned both runs through its native run query. Their trade artifacts
have the same SHA-256, and downloading each artifact through MLflow produced an
exact hash match. The local MLflow UI was also started against the retained
SQLite store and returned HTTP 200.

Important result: B2 is still negative and `NOT_ELIGIBLE`; lineage makes that
conclusion reproducible, not profitable.

## DVC restore and fresh-checkout reproduction

`data/normalized/BTCUSDT_5m.parquet` was DVC-tracked, pushed to a local remote,
and restored into a fresh Git clone. Source and restored SHA-256 are identical:
`d4d6b3306c44e242f3fb7f71c44bacabf9a6af1f1f8d507ca2de0853b6a727d0`.

The checked-in reproducer ran in both repositories and returned the same 577,803
rows and 132,921 MA-state transitions. This verifies restoration plus deterministic
re-execution without relying on the original working copy.

## Test B — AI trace

The existing offline null-provider seed output was logged through the same MLflow
store with exact provider (`null`), model ID (`null-v1`), prompt version, research
question, agent config, tool policy, corpus/context hashes, zero token/cost/latency
metrics, output artifact, and evaluator-schema result.

This is `PASS_MOCK_ONLY`: it proves trace plumbing while credentials are deferred.
It makes no claim about real-model quality, usefulness, or trading performance.

## Test C — thin domain link

`artifacts/lineage/prototype/trading_evidence.jsonl` links the rejected B2 evidence
to `mlflow:<run-id>` and `dvc:<revision>:<tracked-path>`. The custom record neither
duplicates generic telemetry nor imports/parses MLflow or DVC private schemas.

## Acceptance gates

| Gate | Result |
|---|---|
| Reproduce | PASS — fresh clone restored the exact dataset and matched deterministic reproduction output |
| Compare | PASS — two MLflow runs are natively queryable/comparable and the local UI loads |
| Trace | PASS — code, data, parameters, costs, metrics, trades, equity, and manifests are linked |
| AI trace | PASS_MOCK_ONLY — exact offline mock provenance; real-provider quality remains deferred |
| Domain link | PASS — thin record points to public MLflow/DVC references |
| Local-first | PASS — local SQLite/filesystem/Git remote, no credentials |
| Replaceability | PASS — custom record does not depend on either tool's internal schema |

## Failure-condition review

- Dataset restoration was deterministic, not brittle.
- Generic metadata remains in MLflow/DVC and is not copied into the domain record.
- No private storage schema is parsed.
- The one-command prototype completed locally; tools remain isolated from runtime.
- AI output links cleanly, with mock-only scope made explicit.

The composition therefore passes the prototype and is recommended as generic
lineage beneath the custom Trading Evidence Registry. Production hardening,
retention, backup, migration, and access policy remain S2 architecture work.
