# Initial Reuse Decision Matrix

Checked: 2026-07-05
Status: Provisional; architecture not approved.

| Capability | Existing candidates | Reuse fit | Current decision | Why |
|---|---|---:|---|---|
| Event-driven simulation/live engine | NautilusTrader, LEAN | High | Bake-off | Strong existing infrastructure; no basis to custom-build first |
| Crypto-native bot/research lane | Freqtrade | Very High | Bake-off / Reuse+Adapter candidate | Backtest, dry-run, hyperopt, bias helpers, UI/API patterns |
| Market-making / crypto bot fleet | Hummingbot | High | Selective reuse candidate | Strong CEX/DEX and market-making prior art |
| Fast strategy sweeps | vectorbt | High | Reuse candidate | Rapid broad screening; must be behind anti-overfit controls |
| Technical indicators | TA-Lib, vectorbt integrations | High | Reuse Existing | Reimplementing canonical indicators adds little value |
| Hyperparameter optimization | Optuna | High | Reuse Existing candidate | Mature optimizer already integrated by ecosystem tools |
| Experiment tracking | MLflow | Very High | Leading candidate | Params/code/metrics/artifacts/datasets + AI eval/tracing |
| Data versioning | DVC, lakeFS | High | Compare / likely hybrid by scale | Laptop-first vs object-store scale differ |
| Crypto exchange abstraction | CCXT | High | Reuse + native fallback | Broad normalization, but venue semantics remain |
| Crypto deep historical data | Tardis, Databento, native sources | High | Shortlist | Strong existing products; cost/coverage unresolved |
| Statistical overfit validation | PBO, DSR | High | Reuse method / implement adapter | Established methods directly match North Star |
| Lookahead diagnostics | Freqtrade helper + custom cross-engine tests | High | Hybrid | Reuse helper where applicable; cross-engine need remains |
| Portfolio/risk primitives | LEAN, Nautilus | Medium/High | Reuse + custom policy likely | Existing primitives strong; OS-wide governance remains custom |
| Strategy source corpus | QuantConnect Strategy Library, Hummingbot, academic papers, Pine/GitHub | High | Build registry over reused sources | Corpus exists; our value is provenance/testing |
| AI/agent experiment tracking | MLflow + quant benchmarks | High | Reuse infrastructure + custom scoring | Generic infrastructure exists; downstream economic linkage is custom |
| Dictionary seed | authoritative exchange/broker/regulator glossaries | High | Reuse + normalize | No reason to author world vocabulary manually |
| Trading ontology | existing terms + custom canonical IDs/context | Medium | Hybrid | Source definitions reusable; cross-OS semantics are custom |
| Evidence Registry | None found as complete fit | High custom need | Build Custom likely | Cross-engine strategy×market×timeframe evidence lineage is core differentiator |
| Approval Engine | Existing workflow primitives only | High custom need | Build Custom likely | Promotion/demotion based on trading evidence is domain-specific |
| Research Asset layer | MLflow/artifacts/knowledge systems partial | Medium/High | Hybrid | Storage/versioning reusable; freshness/reuse semantics custom |
| Dashboard/control plane | Hummingbot/QuantConnect prior art, generic UI stacks | Partial | Unresolved | Dedicated UI reuse discovery incomplete |
