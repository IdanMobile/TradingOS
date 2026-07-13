# Package Integrity Manifest

Package version: v8.69 CFTC positioning family admission (2026-07-13). Supersedes v8.68 hashes.

Regeneration rule (D-030 / task T-000-02): any controlled edit to a file listed below requires regenerating this manifest in the same change and noting it in `PACKAGE_CHANGELOG.md`. A hash mismatch against an unmodified checkout is a hard blocker; a mismatch caused by a logged, changelog-recorded edit means the manifest regeneration step was missed — fix the manifest, do not fork the file.

## Required handoff inputs — operational core

| Path | SHA-256 |
|---|---|
| `handoffs/START_HERE_SINGLE_CODING_AGENT_PROMPT.md` | `63edd37b00b9f9606f60c1caa7a89f53181d9665e98df14e2b3005e7edd1ea39` |
| `TRADING_OS_NORTH_STAR.md` | `2a47f65612bd8f103335de828e398f83713d660f74aedc6ca1c2435077e593d8` |
| `PROJECT_STATE.md` | `59b9e9899fbb8ec19d7c4c75016bd5ac93a8c9eb074ef2f4a4ef00454d1e0211` |
| `DECISION_LOG.md` | `74b92045cc862ba6eb18edf2df2dfa03d1659f2cffb16a5d3ed6ea8f252e6319` |
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
| `specs/STRATEGY_SEED_BATCH_V1.md` | `57bde741f7b90e5739b58d62df4097bc71b807af4f36b9cad4ce89c008b02446` |
| `specs/AI_AGENT_EVALUATION_BLUEPRINT_V1.md` | `50e6f528e9e816a3f2700055f1e310554bb194c7c4b6cea3c94053d87d725626` |
| `benchmarks/ai_agent/FROZEN_BENCHMARK_SUITE_V1.md` | `61d13a81b76ea0b0c49f465ce6cabf18d7c45130b433564216c319f04347652f` |
| `specs/ENVIRONMENT_AND_CREDENTIALS_INTAKE_GATE_V1.md` | `0c53e737e82d1b984e6d252013bdb1eeab0145e2e15ee9643cfc98e7853f8160` |
| `RESEARCH_BACKLOG.md` | `cc422de856277be6b7a991777b51d8d4b9bef5f23688399d89087d59e39f3824` |
| `MISSING_AND_OPEN_ITEMS.md` | `c1d259ef3d2c48dbd5041b216c8d6a6417e6fdfffde50b7c6380d66a09fdf8d3` |

## Supervisory correction package (added v8.52)

| Path | SHA-256 |
|---|---|
| `docs/supervisor/SUPERVISORY_BASELINE_2026-07-13.md` | `63313a6771b5640fe620e6bea5ae036e44c8a06bf25650d68f0314e1259cf9f3` |
| `docs/supervisor/IMPROVEMENT_PLAN_2026-07-13.md` | `8c29b781bafabd522562eade37c388e752e3845b12460b5ed319b1cd0ef8a933` |
| `docs/supervisor/FINAL_SUPERVISORY_REPORT_2026-07-13.md` | `171ed81058caef3ba983eb55bdd274cbe4a922734b7936ba813299d35d8609d1` |
| `artifacts/reports/G10_PREREGISTERED_CAMPAIGN_REPORT_2026_07_13.md` | `67b0be7e43777bf31ba3e33dffa81795bdebd84d84683c7a010e84bc945bf59d` |
| `strategies/research/funding-carry-basis-delta-neutral/canonical_strategy_spec.yaml` | `87ee0ecfc39515547a09ffa2108b93f7f65785de2ec28e2f4a895190d1ca86b0` |
| `strategies/research/funding-carry-basis-delta-neutral/canonical_strategy_spec.sha256` | `02b3be727ee2d86a4b80eeb5fdf31779827b604f16e76f7c9f562d82ede8713a` |
| `research/BASELINE_G10_SEARCH_CAMPAIGN_V1.yaml` | `f7dd3393b95f644df6b38ee3602d0530bc4d91d1f4f873d956b49a10c8ff98fe` |

## Canonical baseline V2 formal-run freeze (added v8.54)

| Path | SHA-256 |
|---|---|
| `data/raw/manifests/DS-CRYPTO-SPOT-BTCUSDT-5M-V1.source.json` | `f9d986bd48c9baa060871721fc849be3f72b472d4c8859b35d07ec29b0d93139` |
| `research/CANONICAL_BASELINE_G10_CAMPAIGN_V2.yaml` | `effe683f7c41502b50efbc2070ee3246fc14dbb98f895f155de812dcf78d4e2f` |
| `research/CANONICAL_BASELINE_METHOD_SOURCES_V2.yaml` | `366643eb382c81d41043813c15fefb50ab2a05b31454b185ba597577bfe0d478` |
| `engines/vectorbt/canonical_baseline_returns.py` | `ffca97a92ecefe1be2b187316320e5c486ed64618962571d25f4d06c1850299e` |
| `scripts/restore_canonical_btcusdt_5m.py` | `5fa0417f23b4211f0ebccd6b32f903ae48e6fd61d9cafa5f272aa9001cbafca1` |
| `scripts/run_canonical_baseline_campaign.py` | `e7fbcb31a17ff7c3ecc9e4525c0d8c7ca765ccf0d9ef62f3e9f1f6881c02e7b1` |
| `artifacts/reports/CANONICAL_BASELINE_CAMPAIGN_V2_REPORT_2026_07_13.md` | `095795b94b3d232d7bc47aa12da366d4b7c55d36f38218c797922023b0ce967d` |
| `artifacts/validation/campaigns/SEARCH-CANONICAL-BASELINE-G10-V2/campaign_index_96d746a1e8084c6a9a39e2d8752936d166c32c2685a9c31b48f5feb7a7a93950.json` | `96d746a1e8084c6a9a39e2d8752936d166c32c2685a9c31b48f5feb7a7a93950` |

## Required handoff inputs — planning system (added v8)

| Path | SHA-256 |
|---|---|
| `docs/architecture/AD.md` | `3f029dcd3ac92cd14a0b9cdb2d6a669d0c98b644246d545deed06537026b6ff7` |
| `docs/architecture/MODULE_CATALOG.md` | `864d2f94da9dd2806cb44ebd1f17120e17c5dc509917aa639d2f8c142c3097af` |
| `docs/architecture/TYPE_AND_CONTRACT_CATALOG.md` | `143006284c36deeb4ecc10f514e5b155926426ad03c360ff27f081452118b8e5` |
| `docs/program/PROGRAM_PLAN.md` | `b491591bc5376a4bf3b93f7c42f68c25200f7e4420c05445a925bca7bd60f298` |
| `docs/product/MVP_SCOPE.md` | `5cdcc8a4249951117baee31cb0ac1b9b5141a150272abe920db3a93a6a9cfc54` |
| `docs/testing/TEST_MASTER_PLAN.md` | `fb4bd18aed50ff4367c1fb15ff8dbfe33b4399ca7f74ee78e06ed365af350b54` |
| `docs/traceability/TRACEABILITY_MATRIX.md` | `cc4b43ba2613ecd1948cd86f5c243243546e2340944cb346cc232b80fa1513e9` |
| `docs/ai/AGENT_ROLES.md` | `15059de1a50206ba8e85595d68dae8f5f568bc4a3b0270606973b4d947523d49` |
| `TODO.md` | `69a9c9016296410258d367dedd4f6f0d8194a30214b979dc071258bc7423f714` |
| `research/EXISTING_CAPABILITY_REGISTRY.md` | `f01d15ad4dae4be25f12bfab29e230192d49f08d3bf8e47ca10890098da7fc82` |
| `research/RESEARCH_GAP_MATRIX.md` | `c3abde01ff052dc96bd8f8fe4a51afbaf81e044b49e5bb97dbde62aefc2bda4e` |

## Post-V2 family selection V1 (added v8.55)

| Path | SHA-256 |
|---|---|
| `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V1.md` | `8c7b78df77486669f8587bbaf5cd9e6e4eb925741fbc5df2c1a88595643ef545` |
| `audits/ARCHITECTURE_COMPLETENESS_AUDIT.md` | `729af643828c44b8b59d6dd95a209d9bfe53ed90e9ffd9a404e62db60944cef0` |
| `audits/TODO_COMPLETENESS_AUDIT.md` | `22ca004dfd4049637db6be5128186a3e51411e2b606c45413d344d46508ad666` |
| `audits/RED_TEAM_PLAN_REVIEW.md` | `a8d0f8850fdce2fbcfa985016b69d8755a52ed16b8c01e7d8652f6bcb9ee833c` |
| `audits/PLANNING_HANDOFF_SIMULATION.md` | `99f70334d411ebbeb58039f95d6e8a20636700269e5b8755b72f4d71316694b3` |
| `skills/README.md` | `3d84002f72c58dc744fa8beb582701cd610e766e992c2ddd4d8de3fa1ef134c7` |
| `todos/00_program.md` | `8e9a11b37f5728c8260eb96b0f4a9382a09a1da9bee25393d4fb1515e3d9082e` |
| `todos/01_research_completion.md` | `20d8f8d5fad0f26ff9dd07efd65270163dbf2203f9d1c61029f0b5444df1b95b` |
| `todos/02_architecture_foundation.md` | `5f9d92c7246ad7b6249ba61fbfc30cebdf2f3be6a179fc3852a6b3153c8945ce` |
| `todos/03_repository_foundation.md` | `180208e84db8c3a55007aadbf125e8b9e454a1bcf7c0fcb277d521ada5221a6d` |
| `todos/04_data_foundation.md` | `7510144b128ba2e0f1b14882b2bb617f457d5487a8d6a4d7dead67f62247bb19` |
| `todos/05_strategy_domain.md` | `e11b0f27f518eddf521b8250e27624279b14782b20e80284d6923c21b914934a` |
| `todos/06_engine_bakeoff.md` | `4f56e8930f40f6390e353da5c2464435f7ea5f64f25b030debddd4d6c105e0b8` |
| `todos/07_experiment_lineage.md` | `25bf4a12071412136ef52bcd1bf537def3eda56367557d013232bd0303836282` |
| `todos/08_backtesting.md` | `85bf5bc925fa217fc4bff13352ff586ab0753a71de5b528eb6db717ce942486f` |
| `todos/09_validation.md` | `e1eda19285849cb5127660728ffc90eb018b59bb8d54d64e6d24c8aca4e0b485` |
| `todos/10_strategy_ingestion.md` | `544ffeb89068e553b5ca8bb75a1710812fa733eee087e64b56bef1d29a77bf5f` |
| `todos/11_ai_agent_eval.md` | `f32abb43c847f3c609192abbf127a43b7edb330ddbb455ab217301176c0cc80b` |
| `todos/12_dictionary_ontology.md` | `f1f19b5250ad1aaefecc7dbb87bb9d837a0f1f12e48af99d490e26cc6038ce4f` |
| `todos/13_research_assets.md` | `423f9814bfc6e920324cbc827ebd4ad65e7fb51cb50a6af72b42ae9eac2a40ee` |
| `todos/14_dashboard.md` | `02d09ccde77a854bed6360b7983c5b6be4ffac13c1ad4b09f6faab23bb7c8ed3` |
| `todos/15_paper_trading.md` | `055ed8032f4090100da330ce1429e5fe9547d69f78fa32ab947881d284ccc766` |
| `todos/16_risk_approvals.md` | `5dba2879e27ac1ce17ac3770afe21873969355ecfaef042d0775e905736966c7` |
| `todos/17_observability.md` | `242400130779daef1be64c532ba3dd883f68aacbf1eb12841cd82997798a9326` |
| `todos/18_security.md` | `222e9fe4c8b757ef431fad2bb1a974aa33e44e7c937288656b7239704eb0ee73` |
| `todos/19_operations.md` | `68f73a470e79241098afec113b99274ef498da7691169269eb7f9ce14188a260` |
| `todos/20_future_market_expansion.md` | `97cb7ff36f065aca69de5dce6493d02fa0e3fb67564ccc93d9884208122d1436` |
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

## UTC-weekday admission and campaign freeze (added v8.56)

| Path | SHA-256 |
|---|---|
| `research/PLATFORM_STRATEGY_VALIDATION_AND_SCORE_ELIGIBILITY_V1.md` | `dc07a74e16f61ec531a89b5734b1f30011563767034712f5005fdbafef29b39a` |
| `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V2.md` | `95c9383da7662343ce0644b213ad407d7534e1a0afb06bd430786ba64e2c6c1a` |
| `research/CALENDAR_UTC_DATA_PACKAGE_V1.json` | `2a0532c3da28586e8f99ccc0e362592473f548b8bc3bc472cfc5cec44db08e50` |
| `research/CALENDAR_UTC_G1_G11_CAMPAIGN_V1.yaml` | `dbf84679e97e892f86610e80fc735e4c4dad89942a9a3b5d6a610e634daff985` |
| `research/source_snapshots/calendar_utc_v1/binance_public_data_README.md` | `085ab91377aa9325d44f4c7ad27cce4ab381e158403e1d7df2bad39d1a66f7c6` |
| `strategies/research/calendar-utc-weekday/canonical_strategy_spec.yaml` | `b7f85a146818130abe330fe639b7b38c6b7f7cca7c84e1246c174d7cbc6bf9d4` |
| `src/tios/strategy/spec.py` | `5ed0aafdd71f75cd0ab902fd9fc5ec814e535a9052cd8986d317d0233830b1ee` |
| `src/tios/strategy/evaluator.py` | `81325dc8442a97082c35852d046ff217f0eb22dc7fba6d027bdd7be9ae4d6d20` |
| `engines/reference/calendar_utc.py` | `e7885a873d2c7e500a50c651f91c600f4534321fba6abfb2dcc669df3062733b` |
| `engines/vectorbt/calendar_utc_returns.py` | `cd04c0a2d4933f20b7b1f4b7675d0dc2f457d001131f5ebfd0de6a320239f0e0` |
| `scripts/verify_calendar_utc_data.py` | `f863b1d3f763daf11698096f624c9398cc42cc6511102cbe3a3e75453b1ebcd1` |
| `scripts/run_calendar_utc_campaign.py` | `2f765066ef920e089b263efc0a19d0763def43a84c9c61ff5f08733d0f1617f1` |
| `tests/test_calendar_utc_data.py` | `ad0148c9dab11d4b4dc5c6baf2492ba423ff49866db88c24c83db1eeffb3eefd` |
| `tests/test_calendar_utc_reference.py` | `1a23ba4a08149db235a02b710e72b5a9da8cc653bf672b36f9ee621d6297e988` |
| `tests/test_calendar_utc_strategy.py` | `4c9b503c31899807d7ca8727f9261c22ea578352eb35a7771cb59029c1023473` |
| `tests/test_calendar_utc_campaign.py` | `ba5bab4b7e39685321d9dd0a9ce81637017b09054f7cfcc0470557b180189f79` |
| `artifacts/reports/CALENDAR_UTC_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md` | `6199842b4b340e1f95b1e166dedabaff6a5f9b63062d6dd440641392b9dea724` |
| `artifacts/validation/campaigns/CALENDAR-UTC-G1-G11-V1/campaign_result_67b013d934b3648b76ed7a45449e0348efead0e6e0cc67430583e1d6d68c31e0.json` | `67b013d934b3648b76ed7a45449e0348efead0e6e0cc67430583e1d6d68c31e0` |
| `artifacts/validation/campaigns/CALENDAR-UTC-G1-G11-V1/preregistration_bce52193c0d7cf7335a25aef48f6e34b09c1545495f16e64e8fa75b65cf68eae.yaml` | `bce52193c0d7cf7335a25aef48f6e34b09c1545495f16e64e8fa75b65cf68eae` |
| `artifacts/validation/campaigns/CALENDAR-UTC-G1-G11-V1/reference_results_ac7300038092ba8239417517118195f5674ccb71bc3385d620ba859df4c0fa08.json` | `ac7300038092ba8239417517118195f5674ccb71bc3385d620ba859df4c0fa08` |
| `artifacts/validation/campaigns/CALENDAR-UTC-G1-G11-V1/vectorbt_results_3fdf3719e7284ec496d52b2b20b6591bc2991ff23f4f9a8d3d1f4cd2f8e685f0.json` | `3fdf3719e7284ec496d52b2b20b6591bc2991ff23f4f9a8d3d1f4cd2f8e685f0` |

## Funding-pressure family and data freeze (added v8.58)

| Path | SHA-256 |
|---|---|
| `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V3.md` | `0e74d76408fb75e0564be374281acb851f5acb0061a4ca000882479937c30f7a` |
| `research/FUNDING_PRESSURE_SPOT_DATA_PACKAGE_V1.json` | `df28e581ccd95755d620dafef18adbad202ea41038827bff5241716d1112b251` |
| `scripts/verify_funding_pressure_data.py` | `3135d084f7e84bae2e73a3a89c98dd5c6c35e7d909858a8690cc7481c16c376c` |
| `tests/test_funding_pressure_data.py` | `f443ad132b342d8e2e129c9123f35648ac5c156ac92dde988500450cad25d9e0` |

## Funding-pressure immutable campaign freeze (added v8.59)

| Path | SHA-256 |
|---|---|
| `research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V1.yaml` | `6b4fbff8936ba678b470c8ccdbe9c4c43b9e8fce8e5a34785946692efb900bab` |
| `strategies/research/funding-pressure-spot/canonical_strategy_spec.yaml` | `98bb073bd7c1ff46383d8837c39dee3dd2dfb2a7e303c22986afc8e2c5c742aa` |
| `src/tios/strategy/validator.py` | `0916085cd35cf1f7a48dddb0d49a8fe6a25d4b7f2428d5b25e8389e818a117be` |
| `src/tios/strategy/funding_pressure.py` | `2bb4bc766a54aff687824e0edc103213ce05abf8a077de29dad4975dcbe6a76a` |
| `engines/funding_pressure_data.py` | `1dca9cde1da9657c990a6d43026c883c15e6915918496b1262f9eae7c5bf9e8a` |
| `engines/reference/funding_pressure.py` | `8e660df18f0c001f2d06e10cd25c45b80ef71ac2399de5f163869adcaf9ef4f4` |
| `engines/vectorbt/funding_pressure_returns.py` | `b5d3aa597bd2e82377edc5c4aa7ea23c73b01ac56b3f9c221113fb939ba76a7d` |
| `engines/freqtrade/funding_pressure_signals.py` | `cdee9bb5f047f3d35537800e745cf5fe80f08d348f4884e07c1b2e63569daef2` |
| `engines/nautilus/funding_pressure_events.py` | `67bc37cc52810bade33c6055eb4ab7edc0c2f811a1b1017f171fb91f0a55b125` |
| `scripts/run_funding_pressure_campaign.py` | `ed32ce5905d94ec98f23e813380f326744cff97f517a9ce2814668c2faacf561` |
| `tests/test_funding_pressure_strategy.py` | `44c4f5c7baeebd8a77222a7c6dc1ab70a744915764a7d4f6e41f539db1e4dd95` |
| `tests/test_funding_pressure_reference.py` | `780566f9f4d8be9777a9aecf595fa0b2532dbdd7e8b26f4efeeab82351f9311e` |
| `tests/test_funding_pressure_campaign.py` | `6428d2729bab71e2c9b452761eac669e092df22cb6d1f4b2c48493d79f84989a` |

## Funding-pressure V1 abort and V2 freeze (added v8.60)

| Path | SHA-256 |
|---|---|
| `research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V2.yaml` | `7b4e4d2c7141d3cb83e263f0e3445706f2d9a232cda967a94027ea0ee107fe8c` |
| `artifacts/reports/FUNDING_PRESSURE_SPOT_V1_OPERATIONAL_ABORT_2026_07_13.md` | `ae1d59b7b1fc4365a54398ed3c947eef5d0326eaefd6811e47d94fd0edf345b8` |

## Funding-pressure V2 abort and V3 freeze (added v8.61)

| Path | SHA-256 |
|---|---|
| `research/FUNDING_PRESSURE_SPOT_G1_G11_CAMPAIGN_V3.yaml` | `ee4380411eb933f7f7374bcbe42251571b6fa5f341f01be58790008919178b32` |
| `artifacts/reports/FUNDING_PRESSURE_SPOT_V2_OPERATIONAL_ABORT_2026_07_13.md` | `f995c08f137428e9bc67d6de51f101f19237b9e41e4f67d80e17d6e501a30879` |

## Funding-pressure campaign rejection (added v8.62)

| Path | SHA-256 |
|---|---|
| `artifacts/reports/FUNDING_PRESSURE_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md` | `4be0adfea558dddbf5bce7bcd974ee324d842fea46b10912939ccddc8eac31bd` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/campaign_result_4f85fb195e3097a8d7a9b1b4484e51b0e8c4395bf16b6017801f39f196ccda76.json` | `4f85fb195e3097a8d7a9b1b4484e51b0e8c4395bf16b6017801f39f196ccda76` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/phase_one_reference_d54bc21f46cb588cb2fe2784975809f218ec3b3ae1ff041ef297468054687a3a.json` | `d54bc21f46cb588cb2fe2784975809f218ec3b3ae1ff041ef297468054687a3a` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/phase_one_workers_77039a1ed042066c2c0d0c2aa7005e60b7d460b96a2fdd9dc1e8a72f3d56017a.json` | `77039a1ed042066c2c0d0c2aa7005e60b7d460b96a2fdd9dc1e8a72f3d56017a` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/phase_two_reference_d72a162dd27c7704c392e72120ae09a8e8d77c2c82eb6ddddb43d06253f739c4.json` | `d72a162dd27c7704c392e72120ae09a8e8d77c2c82eb6ddddb43d06253f739c4` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/phase_two_workers_119b2b769de0d1f20ad79adc06274387651ba0a2b9cb83b5713c8a5866ac84ed.json` | `119b2b769de0d1f20ad79adc06274387651ba0a2b9cb83b5713c8a5866ac84ed` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/preregistration_79864bd116fdb50ff584a4f701a88571f482bb653dedc7aabb2ffc8a1c527044.yaml` | `79864bd116fdb50ff584a4f701a88571f482bb653dedc7aabb2ffc8a1c527044` |
| `artifacts/validation/campaigns/FUNDING-PRESSURE-SPOT-G1-G11-V3/selection_0ed042349014ef9b9d90011c41f33ad92d8bbdd155ecc0f38db59279da4030ed.json` | `0ed042349014ef9b9d90011c41f33ad92d8bbdd155ecc0f38db59279da4030ed` |

## Bitcoin transaction-activity family and data freeze (added v8.63)

| Path | SHA-256 |
|---|---|
| `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V4.md` | `8253dbbde2e61e62b8fd36c8e38707526a623e303bdbbba70d75c4658d25267f` |
| `research/BTC_TX_ACTIVITY_DATA_PACKAGE_V1.json` | `00b36574e6721ef46baf7bb6684c1cdd26f0a5741657058b5144db84dc51fd74` |
| `data/raw/onchain/blockchain_info_n_transactions_6y_2026-07-13.json` | `884abab27dbbae21e989d27808349acdbbe372cb90f10e758abfb214ea21a7f1` |
| `scripts/verify_btc_tx_activity_data.py` | `46d213cc07971c323ac561400d27d24221f405aa016f6650a3fb4413426264ad` |
| `tests/test_btc_tx_activity_data.py` | `f96d94fba2232aadd3d33c4559609fa4438975408f1d47834b0789968fa6f650` |

## Bitcoin transaction-activity campaign freeze (added v8.64)

| Path | SHA-256 |
|---|---|
| `strategies/research/btc-tx-activity/canonical_strategy_spec.yaml` | `45094612df881362d4ae81151413e1d1e263cb6959460726cda46976f56c8242` |
| `src/tios/strategy/transaction_activity.py` | `c1e3f6be3406ddf74f62cfe047c64570ccdb95896470b831d98ea1b9befc73c1` |
| `engines/transaction_activity_data.py` | `95e476332f14fce8882b5ed62cb308c3b305bb39dcfd7ad00f66525342fbec1a` |
| `engines/reference/transaction_activity.py` | `1fafde265b8c643dc55026cee7642c97d61ea0c70d2387d518d58152c78349ea` |
| `engines/vectorbt/transaction_activity_returns.py` | `55080d409dde349538546e4d790f74a27d54428e3145ab1784c311b914ea326a` |
| `engines/freqtrade/transaction_activity_signals.py` | `ad1e214b425c6ecda0113f9bd894328112231fce5e6368f5be52087452b1d24c` |
| `engines/nautilus/transaction_activity_events.py` | `a62d246d539f8318a69f0d7437dcc125d3f42fd04f9a1fb00c09bc9c95e9db3a` |
| `research/BTC_TX_ACTIVITY_SPOT_G1_G11_CAMPAIGN_V1.yaml` | `9ee7608393fe2cc963abb8910faa804060b610eb0f1f4b37eb18b09418badd68` |
| `scripts/run_transaction_activity_campaign.py` | `4c49ab03196da60103e8c4df3c713b75a2fdd2b73c64e493d9e5ebd20b23ab28` |
| `tests/test_transaction_activity_strategy.py` | `fefda8ff54c41857a2f944e067addec2b594f470b7c3f7682028029d838aa4f7` |
| `tests/test_transaction_activity_reference.py` | `325e94c4d287a734bbc868b6933195e8e4881bee4b702c8a81a8c422d93a5ec3` |
| `tests/test_transaction_activity_campaign.py` | `789015d7c30acac189ba29acecbe32a4bee3ec3c98b1f5545748d7906dd01746` |

## Bitcoin transaction-activity campaign rejection (added v8.65)

| Path | SHA-256 |
|---|---|
| `artifacts/reports/BTC_TX_ACTIVITY_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md` | `012919bc232e72194c787a6ed531e93bd4902e9b746718dbdb6c7ffd664acd58` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/campaign_result_f77b5d3481413d062fd8b7f4218e641cb2d71656ddcdcf2d7edcd29c8cdc5ef6.json` | `f77b5d3481413d062fd8b7f4218e641cb2d71656ddcdcf2d7edcd29c8cdc5ef6` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/phase_one_reference_81794fd23c71d6cab4f212f0b5d671872433ec247ba23c6c9ed3672f7e3fa4bf.json` | `81794fd23c71d6cab4f212f0b5d671872433ec247ba23c6c9ed3672f7e3fa4bf` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/phase_one_workers_11579f281201c42ecebc9bd5d8153c04f09e5e768a78c737214c4cde1c88fda9.json` | `11579f281201c42ecebc9bd5d8153c04f09e5e768a78c737214c4cde1c88fda9` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/phase_two_reference_da72b7fa2080ed26dd676bf378ddab2461ccf350d7f378ac7911d3172c4261b4.json` | `da72b7fa2080ed26dd676bf378ddab2461ccf350d7f378ac7911d3172c4261b4` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/phase_two_workers_7de34f3a0a3558d25810812b2405d3f8c0df93e9c51d5a677bbef6211bdb1e6d.json` | `7de34f3a0a3558d25810812b2405d3f8c0df93e9c51d5a677bbef6211bdb1e6d` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/preregistration_9ee7608393fe2cc963abb8910faa804060b610eb0f1f4b37eb18b09418badd68.yaml` | `9ee7608393fe2cc963abb8910faa804060b610eb0f1f4b37eb18b09418badd68` |
| `artifacts/validation/campaigns/BTC-TX-ACTIVITY-SPOT-G1-G11-V1/selection_affb5b1f22b75c73cbd4edbfba46064d63cebe99eed9efc10c0f9862d5844e17.json` | `affb5b1f22b75c73cbd4edbfba46064d63cebe99eed9efc10c0f9862d5844e17` |

## Bitcoin MVRV family and data freeze (added v8.66)

| Path | SHA-256 |
|---|---|
| `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V5.md` | `228c57fab6ba75910588211d5bbc059ef9f4e4630b206b4d7ae3d40f94feab13` |
| `research/BTC_MVRV_DATA_PACKAGE_V1.json` | `e8155e56dec7a1c05b3f7c289aa9f3320d939ee6160b23b0606af40aef1cd214` |
| `data/raw/onchain/coinmetrics_btc_capmvrvcur_2020-07-01_2026-06-28_2026-07-13.json` | `88f68a10c52dd822cd6b564f33fb75b5470e1e6fc84783a02ce9a39edf5f8c49` |
| `data/raw/onchain/coinmetrics_capmvrvcur_catalog_entry_2026-07-13.json` | `32088d26671362024dfe8e721da2891d0f161244542df8ff15b46b7893eaae53` |
| `scripts/verify_btc_mvrv_data.py` | `fd82034dc9fcc958b647248b01efefbc251f053cbebefca3ba436a5eb37fdd43` |
| `tests/test_btc_mvrv_data.py` | `dfd5513c6f1151e209baea435d5e9bb0fc64b7a1c779b5dcc03903ac26b8f1ab` |

## Bitcoin MVRV campaign freeze (added v8.67)

| Path | SHA-256 |
|---|---|
| `strategies/research/btc-mvrv-dislocation/canonical_strategy_spec.yaml` | `6c3d92e832213ae4e0debeee5ec9a7a7a7140fcf65a1a9b2fe05b25e7035dfa6` |
| `src/tios/strategy/mvrv_dislocation.py` | `efc36caa3fcc0af9b8ed5d283f134bbaa7fcb587e00e6a8cfe2f3b5041842ca6` |
| `engines/mvrv_data.py` | `121a4a49132b3e3cc570a232f940b0f95b3422335bf7e962d9e20c80e9747dd7` |
| `engines/reference/mvrv_dislocation.py` | `387f5f0fd8017c8e095277919b06a0c9ed98b40efe81840af6199f53f51a25fc` |
| `engines/vectorbt/mvrv_dislocation_returns.py` | `bf74e6069ce2f8ccd4cfc7fb26f38d28558d00471e5ada72b525e1de46a794bf` |
| `engines/freqtrade/mvrv_dislocation_signals.py` | `b8a3f24e5f90a5ae987f5e3cc0e3b615b80606588dbef463c642d1208940da49` |
| `engines/nautilus/mvrv_dislocation_events.py` | `d3de055693883be0a50a4ab296d951abc6b05b2e2d3665ffd7b59dd1d9bc78cd` |
| `research/BTC_MVRV_SPOT_G1_G11_CAMPAIGN_V1.yaml` | `838767c48f9c4ae095e0ed9be8d5e6ec10b0fbcadc6533c61e2d59397c0b2867` |
| `scripts/run_mvrv_campaign.py` | `45c85c59f1d54ecdb80f50978c1a84ffc8e420cb06f46cdc3d103f6168efad53` |
| `tests/test_mvrv_dislocation_strategy.py` | `ded93ed2f1cb10df93b85f22effe69437ed47548590843e9a34fe7b62f43b987` |
| `tests/test_mvrv_dislocation_reference.py` | `e33ab03ea7c9ac76fec6eac0ba3df8f08ea6a54044efc3ee5f0ca4b0d9e3f20c` |
| `tests/test_mvrv_campaign.py` | `cf1cec970875e1417dac7ae4570fa1a99a826dcf26ea5c181ec3ac9744144c7d` |

## Bitcoin MVRV campaign rejection (added v8.68)

| Path | SHA-256 |
|---|---|
| `artifacts/reports/BTC_MVRV_SPOT_VALIDATION_AND_SUPERVISOR_REVIEW_2026_07_13.md` | `85612066a98524df3a9cd720448e0461079034087c44739ca93a49fffe7c676c` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/campaign_result_a815461f8a8c049dc9ac85eab97f8e2ff9c2d52c52d1861e3c4f8802aa7a398c.json` | `a815461f8a8c049dc9ac85eab97f8e2ff9c2d52c52d1861e3c4f8802aa7a398c` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/phase_one_reference_0512f417f6bde10f5017a04eaf5f7583c6931370c3c1af886e60f37e8a2281ef.json` | `0512f417f6bde10f5017a04eaf5f7583c6931370c3c1af886e60f37e8a2281ef` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/phase_one_workers_c1e063a6d44d5756f79c2ad65b303c020ce6d0b175a9e4cbc2ef4d1d0f584000.json` | `c1e063a6d44d5756f79c2ad65b303c020ce6d0b175a9e4cbc2ef4d1d0f584000` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/phase_two_reference_27b3a02a380545b133a545ef2ff7eab93932df56a5bb3a61d690515826e21a42.json` | `27b3a02a380545b133a545ef2ff7eab93932df56a5bb3a61d690515826e21a42` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/phase_two_workers_ed5e469f5d1fad0cfabea96dccf410535d744cba24e43ee7701334c2cae8446d.json` | `ed5e469f5d1fad0cfabea96dccf410535d744cba24e43ee7701334c2cae8446d` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/preregistration_838767c48f9c4ae095e0ed9be8d5e6ec10b0fbcadc6533c61e2d59397c0b2867.yaml` | `838767c48f9c4ae095e0ed9be8d5e6ec10b0fbcadc6533c61e2d59397c0b2867` |
| `artifacts/validation/campaigns/BTC-MVRV-SPOT-G1-G11-V1/selection_e23c47178700c81b3a2a636741957f4ba0504ca3768e1a3b837e02a336f3b748.json` | `e23c47178700c81b3a2a636741957f4ba0504ca3768e1a3b837e02a336f3b748` |

## CFTC positioning family admission (added v8.69)

| Path | SHA-256 |
|---|---|
| `research/STRATEGY_FAMILY_SELECTION_AND_PREREGISTRATION_V6.md` | `da6487a4011707164f5db5dc45e625d6669f12b74ef537fb170df11ef4ac2937` |

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
