# Package Integrity Manifest

Package version: v8.8 S2 automation dashboard and scorecard evidence (2026-07-10). Supersedes v8.7 hashes.

Regeneration rule (D-030 / task T-000-02): any controlled edit to a file listed below requires regenerating this manifest in the same change and noting it in `PACKAGE_CHANGELOG.md`. A hash mismatch against an unmodified checkout is a hard blocker; a mismatch caused by a logged, changelog-recorded edit means the manifest regeneration step was missed — fix the manifest, do not fork the file.

## Required handoff inputs — operational core

| Path | SHA-256 |
|---|---|
| `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` | `4d21c7c4c134029e39905fed8d993a7e64fab4a2b628b5b1a5bc25a8ee32a694` |
| `TRADING_OS_NORTH_STAR.md` | `2a47f65612bd8f103335de828e398f83713d660f74aedc6ca1c2435077e593d8` |
| `PROJECT_STATE.md` | `75a4a2f4cee2626cf41ce5f630430cb1948538458a90a7f55483985b47b5215c` |
| `DECISION_LOG.md` | `d7a2414dc12e418e4cb80cd25a47df573785a6fbb3cd49964720dd985f7ecd4d` |
| `decisions/CODING_AGENT_READINESS_GATE_V1.md` | `b9d54695685dbc5bea0e1779c43274d5927fc9df03d8e0fe8321a9c005330a13` |
| `decisions/INITIAL_REUSE_MATRIX.md` | `113b6919f1121659b68219a6843cacf4bff24efd4afa961d0e7592716b46d7a9` |
| `decisions/CRYPTO_SPOT_VENUE_AND_DATA_MATRIX_V1.md` | `1989968805132385c4e81ef23f9f4bbc5b4ab84414716f4469814c21d8313d48` |
| `specs/CRYPTO_SPOT_MVP_VERTICAL_SLICE_V1.md` | `0cd571bd3a4d66db86080f9eea4af1c9cf84be36282d89ec15b2b61f03c65e2a` |
| `specs/ENGINE_BAKEOFF_BLUEPRINT_V1.md` | `55ed55aef13674be4b09a6abd635a51dd2ab83f3a51db028e56ebb3984eac9ac` |
| `specs/CANONICAL_BAKEOFF_DATASET_V1.md` | `b608143eab487eec9660915f5f4d2574c94d7cdd2223960e48befeca02c80530` |
| `specs/FEE_AND_SLIPPAGE_ASSUMPTION_PACKAGE_V1.md` | `6e5b999138fa473c821a0bb14077ee989464de527a5d8a17719b53a02d83c888` |
| `specs/BACKTESTING_VALIDATION_BLUEPRINT_V1.md` | `5f4d3c6afcb81a0978b971bf65c78364ab2795dc6f3ba1ed47b6b023aad42ed8` |
| `specs/EXPERIMENT_LINEAGE_PROTOTYPE_SPEC_V1.md` | `059eaef922083699a5ec7decfa5ef14e6a80ad98591925c867f948273b0c75ec` |
| `specs/STRATEGY_INGESTION_AND_REPRODUCTION_WORKFLOW_V1.md` | `8a1803ca0fd74f0e06a30960583e91819ca3722703bebde22dbba6edf9b4b9c0` |
| `specs/STRATEGY_SEED_BATCH_V1.md` | `2129fd4a70ec84a160b2d3e9f88d167937a14bd2ce7d229c60520da40238547a` |
| `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md` | `50e6f528e9e816a3f2700055f1e310554bb194c7c4b6cea3c94053d87d725626` |
| `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md` | `61d13a81b76ea0b0c49f465ce6cabf18d7c45130b433564216c319f04347652f` |
| `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md` | `0c53e737e82d1b984e6d252013bdb1eeab0145e2e15ee9643cfc98e7853f8160` |
| `RESEARCH_BACKLOG.md` | `cc422de856277be6b7a991777b51d8d4b9bef5f23688399d89087d59e39f3824` |
| `MISSING_AND_OPEN_ITEMS.md` | `aae084bf1689ce2481cc3415e8f970c0626f3c17cebeaeab0dba8dc0d4d7029c` |

## Required handoff inputs — planning system (added v8)

| Path | SHA-256 |
|---|---|
| `docs/architecture/AD.md` | `9e633acaeaef52277005ad219edd95db117befd86cf2edddf7c8c73db6fe1c55` |
| `docs/architecture/MODULE_CATALOG.md` | `bd4fcc735ebfba09fec6fdba01c67878245f5320b73e599bec47319af2f50d88` |
| `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` | `33f2c3024ad619cc36d16ccc8beb20a6ef172fa1b397ea58b0b9b1f2781b9e63` |
| `docs/program/PROGRAM_PLAN.md` | `b491591bc5376a4bf3b93f7c42f68c25200f7e4420c05445a925bca7bd60f298` |
| `docs/product/MVP_SCOPE.md` | `5cdcc8a4249951117baee31cb0ac1b9b5141a150272abe920db3a93a6a9cfc54` |
| `docs/testing/TEST_MASTER_PLAN.md` | `fb4bd18aed50ff4367c1fb15ff8dbfe33b4399ca7f74ee78e06ed365af350b54` |
| `docs/traceability/TRACEABILITY_MATRIX.md` | `cc4b43ba2613ecd1948cd86f5c243243546e2340944cb346cc232b80fa1513e9` |
| `docs/ai/AGENT_ROLES.md` | `87fcdc8f5a92a4ee98f4262c0c06e10022534353452c30321e6bdfdd643cd99d` |
| `TODO.md` | `d83525f6b8bf227829d9b0a125e002f7ca352db5610b98a20219b218e0ea9ec5` |
| `research/EXISTING_CAPABILITY_REGISTRY.md` | `f01d15ad4dae4be25f12bfab29e230192d49f08d3bf8e47ca10890098da7fc82` |
| `research/RESEARCH_GAP_MATRIX.md` | `034953642ebd11143366f65a0d892041120aacbb333fffc49c5d2c220e01b93d` |
| `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md` | `729af643828c44b8b59d6dd95a209d9bfe53ed90e9ffd9a404e62db60944cef0` |
| `audits/TODO_COMPLETENESS_AUDIT.md` | `22ca004dfd4049637db6be5128186a3e51411e2b606c45413d344d46508ad666` |
| `audits/RED_TEAM_PLAN_REVIEW.md` | `a8d0f8850fdce2fbcfa985016b69d8755a52ed16b8c01e7d8652f6bcb9ee833c` |
| `audits/PLANNING_HANDOFF_SIMULATION.md` | `99f70334d411ebbeb58039f95d6e8a20636700269e5b8755b72f4d71316694b3` |
| `skills/README.md` | `3d84002f72c58dc744fa8beb582701cd610e766e992c2ddd4d8de3fa1ef134c7` |
| `todos/00_program.md` | `8e9a11b37f5728c8260eb96b0f4a9382a09a1da9bee25393d4fb1515e3d9082e` |
| `todos/01_research_completion.md` | `ecefcf56408bd9141f8d199547f810649f6b3bb06791b23f85532c5d68faa60b` |
| `todos/02_architecture_foundation.md` | `9f88444f3706e86a3a866d9b2f47b4c21438ee98d414510bb4fb09b057fc5b27` |
| `todos/03_repository_foundation.md` | `180208e84db8c3a55007aadbf125e8b9e454a1bcf7c0fcb277d521ada5221a6d` |
| `todos/04_data_foundation.md` | `7510144b128ba2e0f1b14882b2bb617f457d5487a8d6a4d7dead67f62247bb19` |
| `todos/05_strategy_domain.md` | `e11b0f27f518eddf521b8250e27624279b14782b20e80284d6923c21b914934a` |
| `todos/06_engine_bakeoff.md` | `085e89583dc7f5f51364d4cbd3efbe2b5cbc2bd081f1f75c323e8aa66a9355c8` |
| `todos/07_experiment_lineage.md` | `25bf4a12071412136ef52bcd1bf537def3eda56367557d013232bd0303836282` |
| `todos/08_backtesting.md` | `85bf5bc925fa217fc4bff13352ff586ab0753a71de5b528eb6db717ce942486f` |
| `todos/09_validation.md` | `09678da01f1a502d09ccdf4c54e748a4150ab3e919850abe7fbddaa4be07905b` |
| `todos/10_strategy_ingestion.md` | `544ffeb89068e553b5ca8bb75a1710812fa733eee087e64b56bef1d29a77bf5f` |
| `todos/11_ai_agent_eval.md` | `f32abb43c847f3c609192abbf127a43b7edb330ddbb455ab217301176c0cc80b` |
| `todos/12_dictionary_ontology.md` | `52aaa0283f70d5955aba96d1b3a912e31cc4f7670f1a36fc51d0268d847018c5` |
| `todos/13_research_assets.md` | `ed05d26c4a802e5e3499c8afc36ae089af6cb6120cacbb34fa6aa2f0d7e41058` |
| `todos/14_dashboard.md` | `7a742d758705bc6597f6468eadb6b50e1ac4743b81358dcc775704b8b93f7636` |
| `todos/15_paper_trading.md` | `a7cc6233f537ca2c58a37d5fa442f1257dc6c09126626c61877c2b75171a1b76` |
| `todos/16_risk_approvals.md` | `7f51e1758a0d16e306d9adff39720c6d1eeaba4c0e7f240cfedc0799f2291c6d` |
| `todos/17_observability.md` | `d04f87e3d3ea67e3770a720ad77f20126998ec69dcae6cfdae623788c41cee5f` |
| `todos/18_security.md` | `15456744f617e88b56483f7a2ddb1ba4feeb09517a95bdab5df6992afeff2df4` |
| `todos/19_operations.md` | `68f73a470e79241098afec113b99274ef498da7691169269eb7f9ce14188a260` |
| `todos/20_future_market_expansion.md` | `ab79c401b9d9f1cc7726ed81dc4e50c5e93d8df4bc994cecbcda513ee94f8915` |
| `skills/SKILL_ARCHITECTURE_GUARDIAN.md` | `c11eb205b3dc89bf3ed9be4436aaabbc1883488c2c8a4b47d911496c39a19a82` |
| `skills/SKILL_BACKTEST_RED_TEAM.md` | `bca1de4923f49505532fbb83f4ec1c746afe5ec82f69120bc6c5b6d9f137d5a9` |
| `skills/SKILL_BENCHMARK_RUNNER.md` | `591f83a0901a87af858a4b191c6b5ae18989c14cdb1b25756c7eaad42d648a98` |
| `skills/SKILL_CANONICAL_SPEC_VALIDATOR.md` | `1a46f6e1211866d7f9a5e1a970ba94340b7167766ed8a4e0d45badd4a59a1bb3` |
| `skills/SKILL_DATA_QUALITY_AUDITOR.md` | `476bf253971deb0b94a88598d792c08378716f7b28f8374054fd3552269110b6` |
| `skills/SKILL_ECOSYSTEM_SCOUT.md` | `108f8da9a4762241c1e2a8c61c79a43c723763890b736ee2900f7111cb92b1ac` |
| `skills/SKILL_ENGINE_PARITY_AUDITOR.md` | `e7396019d95a39a68ed21f2ea003b51b397e4084df0681f530d65b3557cb47fb` |
| `skills/SKILL_ONTOLOGY_CURATOR.md` | `ed6f8c6bd6e5590d85f7b9cca15d2c9c8ff6337afad3faf3946d9bcedef2902a` |
| `skills/SKILL_RESEARCH_ASSET_SYNTHESIZER.md` | `87fb67a3b2b3c3d2d942b6d974baf27d85b194329d56fd70e769e9a2fe69d559` |
| `skills/SKILL_SECURITY_REVIEWER.md` | `bd5e2601238e3e6fa90fa1f7a0eb12f7b385ea4021e0a36ea5b6dea159617ce1` |
| `skills/SKILL_SOURCE_VERIFIER.md` | `bbb949c922c4e3183df6540bb44066077fc6f1ba1b51763299cc6a3e471bcbd7` |
| `skills/SKILL_STRATEGY_SOURCE_INGESTOR.md` | `ee5891fce1aca39a2d11f75b78743345d4b27836cdb52ff30e3d522185b4e7a4` |
| `skills/SKILL_VALIDATION_STATS_SPECIALIST.md` | `e1ef21c8abef8519c4c9809afddc3d10e79cc30382a347ae4f403f36ef38ff13` |

## Expected generated artifacts

These are intentionally absent at handoff time unless a prior run already created them. Their absence does not mean the package is broken.

- `artifacts/reports/PRE_CODE_ENVIRONMENT_INTAKE_REPORT.md`
- `decisions/PROTOTYPE_EVIDENCE_DECISION.md`
- `research/TOOL_AND_ENGINE_REGISTRY_V1.md`
- `research/EXISTING_STRATEGY_REGISTRY_V1.md`
- `artifacts/reports/ENGINE_BAKEOFF_REPORT.md`
- `artifacts/reports/LINEAGE_PROTOTYPE_REPORT.md`
- `artifacts/reports/BACKTEST_VALIDATION_REPORT.md`
- `artifacts/reports/STRATEGY_INGESTION_REPORT.md`
- `artifacts/reports/AI_BENCHMARK_SEED_REPORT.md`
- `artifacts/reports/PROTOTYPE_READINESS_REPORT.md`
- `artifacts/reports/STAGE_EXIT_*.md`

## Verification rule

A missing required input is a hard blocker. A missing expected generated artifact is normal before execution. Verify with:

```
python3 -c "import hashlib,re;t=open('PACKAGE_INTEGRITY_MANIFEST.md').read();[print(('OK  ' if hashlib.sha256(open(p,'rb').read()).hexdigest()==h else 'FAIL')+' '+p) for p,h in re.findall(r'\| `([^`]+)` \| `([a-f0-9]{64})`',t)]"
```
