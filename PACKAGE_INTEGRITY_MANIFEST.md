# Package Integrity Manifest

Package version: v8 planning system (2026-07-06). Supersedes v7 hashes.

Regeneration rule (D-030 / task T-000-02): any controlled edit to a file listed below requires regenerating this manifest in the same change and noting it in `PACKAGE_CHANGELOG.md`. A hash mismatch against an unmodified checkout is a hard blocker; a mismatch caused by a logged, changelog-recorded edit means the manifest regeneration step was missed — fix the manifest, do not fork the file.

## Required handoff inputs — operational core

| Path | SHA-256 |
|---|---|
| `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` | `0befe16dc4417eed19d84ddfc66ddcb537628302d5d7f9f8583f43eeb0b6b077` |
| `TRADING_OS_NORTH_STAR.md` | `2a47f65612bd8f103335de828e398f83713d660f74aedc6ca1c2435077e593d8` |
| `PROJECT_STATE.md` | `b3bb1f4b7fed74697223de2a31b08bb92f313eb63bc07bb3cddc60864e8aeed6` |
| `DECISION_LOG.md` | `b55e9a650798a33e4e0ab6daa9098f923b0d2708e934281c8800786dc83ca88e` |
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
| `MISSING_AND_OPEN_ITEMS.md` | `63868b1d37b38256de7f8698bf28e95620751f9c5548a9fbb1da889d230184ed` |

## Required handoff inputs — planning system (added v8)

| Path | SHA-256 |
|---|---|
| `docs/architecture/AD.md` | `7a021b3c9f84f8b9177cd473281c61e7469fb79882a55fbc15fab3e039fc4a3e` |
| `docs/architecture/MODULE_CATALOG.md` | `342f36ffdc8cf6e9122ac24941dabf5df4a638a1397ccc1639a0ec62659e15ee` |
| `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` | `a213dade69ea34d92e90e43569aa8e5518e146266d9ce00743aca3b7df316982` |
| `docs/program/PROGRAM_PLAN.md` | `b491591bc5376a4bf3b93f7c42f68c25200f7e4420c05445a925bca7bd60f298` |
| `docs/product/MVP_SCOPE.md` | `5cdcc8a4249951117baee31cb0ac1b9b5141a150272abe920db3a93a6a9cfc54` |
| `docs/testing/TEST_MASTER_PLAN.md` | `fb4bd18aed50ff4367c1fb15ff8dbfe33b4399ca7f74ee78e06ed365af350b54` |
| `docs/traceability/TRACEABILITY_MATRIX.md` | `cc4b43ba2613ecd1948cd86f5c243243546e2340944cb346cc232b80fa1513e9` |
| `docs/ai/AGENT_ROLES.md` | `87fcdc8f5a92a4ee98f4262c0c06e10022534353452c30321e6bdfdd643cd99d` |
| `TODO.md` | `ac8e730831c4c27049ca337bc10f5d1310ecaaba7911b1d4c8e7672d53fe3abd` |
| `research/EXISTING_CAPABILITY_REGISTRY.md` | `f01d15ad4dae4be25f12bfab29e230192d49f08d3bf8e47ca10890098da7fc82` |
| `research/RESEARCH_GAP_MATRIX.md` | `034953642ebd11143366f65a0d892041120aacbb333fffc49c5d2c220e01b93d` |
| `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md` | `729af643828c44b8b59d6dd95a209d9bfe53ed90e9ffd9a404e62db60944cef0` |
| `audits/TODO_COMPLETENESS_AUDIT.md` | `22ca004dfd4049637db6be5128186a3e51411e2b606c45413d344d46508ad666` |
| `audits/RED_TEAM_PLAN_REVIEW.md` | `a8d0f8850fdce2fbcfa985016b69d8755a52ed16b8c01e7d8652f6bcb9ee833c` |
| `audits/PLANNING_HANDOFF_SIMULATION.md` | `99f70334d411ebbeb58039f95d6e8a20636700269e5b8755b72f4d71316694b3` |
| `skills/README.md` | `3d84002f72c58dc744fa8beb582701cd610e766e992c2ddd4d8de3fa1ef134c7` |
| `todos/00_program.md` | `4adf5d986585321d8e2ecc0d59abceede8eb4d6481ae2f90781f62c7742ed37c` |
| `todos/01_research_completion.md` | `eedc085faf2f3003f0a1ec717dadb10602de81610181a055f000e9686e7f17b8` |
| `todos/02_architecture_foundation.md` | `aa52165c68cef78d223e827c355260395578bbf11f625bb8df6384c904ea4cda` |
| `todos/03_repository_foundation.md` | `180208e84db8c3a55007aadbf125e8b9e454a1bcf7c0fcb277d521ada5221a6d` |
| `todos/04_data_foundation.md` | `7510144b128ba2e0f1b14882b2bb617f457d5487a8d6a4d7dead67f62247bb19` |
| `todos/05_strategy_domain.md` | `e11b0f27f518eddf521b8250e27624279b14782b20e80284d6923c21b914934a` |
| `todos/06_engine_bakeoff.md` | `9fe41a0037b98f37886cd398b06c03a4c4e0c8aad67e389a8aa75ca474df1987` |
| `todos/07_experiment_lineage.md` | `df00bed7820d90805b7b74968b4f74507b04c14579ba55cd883613a8398a85ea` |
| `todos/08_backtesting.md` | `1e66847a6baec6c964635778c939187780264a5674924e31cf9b7e2d213b836a` |
| `todos/09_validation.md` | `2eb3a095ae17bca8afc4b1af8e28c66fc0b53871c82284ea48c228bcced8c9c5` |
| `todos/10_strategy_ingestion.md` | `3e010c63a00469ccf9c55a82771f7c31d6a2998bb6ffa60960b4af43e709085d` |
| `todos/11_ai_agent_eval.md` | `4961be04f4c69f604b8b0e1f59b1c2a2e511addb6f97ef066c38cf318c64ecf8` |
| `todos/12_dictionary_ontology.md` | `52aaa0283f70d5955aba96d1b3a912e31cc4f7670f1a36fc51d0268d847018c5` |
| `todos/13_research_assets.md` | `ed05d26c4a802e5e3499c8afc36ae089af6cb6120cacbb34fa6aa2f0d7e41058` |
| `todos/14_dashboard.md` | `cb0a80f969787b52d2af4d94771521fc141b1ae1ed13e24430cd05e1e889a5bf` |
| `todos/15_paper_trading.md` | `f5bd29869937172ff82fed29cb1e0631784cdd4e1c84825015a73fc6b1e13b1b` |
| `todos/16_risk_approvals.md` | `0238f7e06c6642b957751ddc8fc2ff075477eaf7f800ade961600c4c81d5377d` |
| `todos/17_observability.md` | `65fb01ab96e11528229354af920f781f7bfeb5d846dfc1c91238ff66e5545a50` |
| `todos/18_security.md` | `7561ceae55d611627b8dae1a3702483be6c1e78107dcf08fd74c026dfa8e62ab` |
| `todos/19_operations.md` | `8c2511cba16ea30abb9226ab9d35030783fa969db992c229972ee3292dd2e3f0` |
| `todos/20_future_market_expansion.md` | `425922d959ec7f4f04135cb8d538c09f62f9be4b115828095ebd65c1f19f4f04` |
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
