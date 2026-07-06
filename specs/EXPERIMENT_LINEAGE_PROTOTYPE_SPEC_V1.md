# Experiment Lineage Executable Prototype Spec V1

Status: Ready for coding-agent execution after package handoff gate.
Goal: prove whether MLflow + DVC can provide the generic lineage foundation beneath the custom Trading Evidence Registry.

## Prototype hypothesis
- MLflow owns run tracking, metrics, artifacts, dataset references, model/agent traces, and comparison UI.
- DVC owns reproducible dataset snapshots and large-file version references.
- A tiny custom registry owns trading-domain semantics.

## Minimal repository shape
```text
lineage-prototype/
├── data/
├── dvc.yaml
├── params.yaml
├── experiments/
├── evidence/
│   └── trading_evidence.jsonl
├── src/
│   ├── run_strategy.py
│   ├── run_ai_research.py
│   └── evidence_registry.py
└── tests/
```

## Test A — deterministic strategy run
Input:
- BTC/USDT frozen candle dataset
- baseline moving-average crossover
- fixed fee model
- fixed random seed where applicable

Must record:
- git commit
- dataset identity/hash
- DVC revision/reference
- strategy ID/version
- engine
- parameters
- fee/slippage assumptions
- metrics
- trade artifact
- equity curve artifact
- runtime

## Test B — AI research run
Input:
- frozen research corpus
- one exact research question
- one exact agent configuration

Must record:
- provider
- exact model ID
- prompt version
- tool policy
- corpus version
- token usage
- monetary cost where available
- latency
- output artifact
- evaluator results

## Test C — custom Trading Evidence link
Create a domain record:
```json
{
  "evidence_id": "EV-...",
  "hypothesis_id": "HYP-...",
  "strategy_version_id": "STRAT-...",
  "market": "crypto_spot",
  "instrument": "BTC/USDT",
  "timeframe": "15m",
  "run_ref": "mlflow-run-id",
  "dataset_ref": "dvc-ref",
  "validation_state": "UNVALIDATED",
  "approval_state": "NOT_ELIGIBLE"
}
```

## Acceptance gates
| Gate | Pass condition |
|---|---|
| Reproduce | Fresh checkout can restore dataset reference and rerun |
| Compare | Two runs can be compared without custom plotting code |
| Trace | Strategy result traces to dataset, params, code, artifacts |
| AI trace | AI run traces to exact model/prompt/corpus |
| Domain link | Custom evidence record links cleanly without duplicating generic telemetry |
| Local-first | Prototype runs on developer laptop without mandatory paid cloud |
| Replaceability | Custom domain record does not depend on MLflow-internal DB schema |

## Failure conditions
Reject or redesign the composition if:
- dataset restoration is brittle;
- MLflow/DVC metadata must be duplicated extensively;
- the custom layer needs to parse private internal storage schemas;
- local operation is cumbersome enough to slow every experiment;
- AI traces cannot be linked cleanly to strategy/research lineage.

## Decision output
The coding agent must produce exactly one of:
- `MLFLOW_PLUS_DVC_RECOMMENDED`
- `MLFLOW_ONLY_RECOMMENDED`
- `DVC_ONLY_RECOMMENDED`
- `ALTERNATIVE_REQUIRED`

with evidence and artifacts.
