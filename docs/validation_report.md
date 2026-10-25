# Validation report

## Milestone 1 result

**Completed and validated locally on 2026-09-29.** Cloud integration is out of scope and unverified.

Environment: macOS local shell, Python 3.9.6. Dataset: official Olist Kaggle version 2 snapshot downloaded on the validation date.

## Executed checks

| Command/check | Result |
|---|---|
| `make test` | PASS — 4 unit tests in 0.002s |
| `make profile` | PASS — 9 tables profiled to `reports/data_profile.json` |
| `make validate` | PASS — all 9 files non-empty; declared schemas and natural keys valid; all 6 declared FKs have zero orphans |
| Raw-data Git exclusion | PASS — `data/raw/*.csv` ignored; only `.gitkeep` tracked |
| Secret/config review | PASS — `.env` ignored; `.env.example` contains names/placeholders only |
| Documentation link check | PASS — all 10 required documents present; all repository-relative Markdown link targets exist |
| Python bytecode compilation | PASS — package, scripts, and tests compile with an isolated cache |
| Git diff/status review | PASS — intended foundation files only; raw CSVs remain ignored; no whitespace errors |

Unit coverage includes the nine-file registry, null/duplicate detection, UTF-8 BOM handling, and validation error reporting. Source validation additionally reads every row and validates required columns, natural keys, and relationships.

## Verified profile totals

- 1,550,922 parsed data records across nine files. Physical lines are not a valid proxy because review text can contain embedded newlines.
- 99,441 orders and customers; 112,650 item rows; 103,886 payment rows; 99,224 review rows.
- Zero natural-key duplicates for every source with a declared key.
- Zero orphans across orders/customers, items/orders, items/products, items/sellers, payments/orders, and reviews/orders.
- Full counts, hashes, ranges, and issue metrics are in `reports/data_profile.json` and `docs/dataset_profiling.md`.

## Limitations

- No AWS, Snowflake, dbt, Airflow, Docker, or Power BI execution occurred.
- The Kaggle endpoint and future cloud integrations require network access; this environment required explicit network permission for the download.
- Coordinate bounding-box checks are broad anomaly signals, not authoritative geocoding.
- Monetary reconciliation differences are identified but not causally classified in Milestone 1.

## Milestone 2 result

**Completed and validated against real AWS S3 on 2026-10-02.** Authentication used the configured least-privilege profile through the standard AWS credential chain; no credentials or identity values were recorded.

| Command/check | Result |
|---|---|
| Original local suite | PASS — deterministic batches, local idempotency, conflict handling, and retry behavior |
| First `make ingest-local` | PASS — 26 batches, 1,550,922 records, 155/155 objects uploaded and verified |
| Repeated `make ingest-local` | PASS — identical 26 batch IDs, 0 uploaded, 155/155 validated and skipped |
| Batch reconciliation | PASS — 129 data files reconcile exactly to all nine source row counts |
| Local payload | 124,509,854 bytes in 129 data files and 26 manifests |
| Conflict test | PASS — mismatched immutable checksum rejected |
| Retry test | PASS — transient failures retried with 0.25s then 0.5s test backoff |
| AWS authentication | PASS — STS call succeeded without displaying identity fields |
| Scoped S3 access | PASS — prefix listing and required object operations succeeded |
| AWS integration | PASS — synthetic upload, metadata validation, zero-upload rerun, and scoped cleanup |
| Full repository suite with AWS enabled | PASS — 22 discovered; 21 passed; only the Snowflake integration test skipped |
| First full S3 ingestion | PASS — 26 batches; 155 uploaded; 0 skipped; 1,550,922 rows |
| Independent remote audit | PASS — 155 keys, sizes, streamed checksums, metadata, and AES-256 settings; zero missing/unexpected |
| Remote manifests | PASS — 26 canonical manifests representing 129 files and 1,550,922 rows |
| Remote payload | PASS — 124,509,854 bytes measured from S3 |
| Full S3 rerun | PASS — 0 uploaded; all 155 objects validated and skipped |
| Integration cleanup | PASS — zero objects remained under the raw-prefix integration-test path |

Bucket-level `HeadBucket` returned 403 because the least-privilege role does not grant that broad operation; this did not block scoped listing, upload, `HeadObject`/read, or authorized test cleanup. No bucket, IAM resource, policy, ACL, or remote branch was created or changed. Production ingestion objects remain in the approved raw prefix for Milestone 3.

## Milestone 3 result

**Completed and validated against real Snowflake on 2026-10-11.** Key-pair authentication succeeded with the expected service-user context. The X-Small warehouse retained a 60-second auto-suspend. No credentials, account identifiers, private-key material, or row-level source values were recorded.

| Command/check | Result |
|---|---|
| Authentication/context | PASS — expected user, role, warehouse, database, and non-empty region |
| Stage prerequisite | PASS — configured integration and URL; exactly 155 readable objects |
| Least-privilege bootstrap | PASS — reused database/schemas/stage; five SQL modules executed without account-level DDL |
| `make warehouse-validate` | PASS — 5 SQL modules, 26 batches, 129 data files, 1,550,922 expected rows |
| SQL rendering safety | PASS — invalid identifiers and S3 URL injection rejected |
| Mock first load | PASS — COPY count reconciled to manifest and audit state committed |
| Mock rerun | PASS — completed batch validated and skipped without duplicate rows |
| Mock count mismatch | PASS — batch rolled back and failure recorded |
| Mock rejected record | PASS — error audited and COPY prevented |
| Real first load | PASS — 26 batches, 129 files, 1,550,922 rows in 400,364 ms |
| Batch/file reconciliation | PASS — zero row/file differences; 129 distinct COPY query IDs |
| RAW contracts | PASS — 9 table/column contracts and exact per-table row counts |
| Source keys/relationships | PASS — zero violations across 7 key and 6 relationship checks |
| Real rerun | PASS — 0 loaded, 26 skipped, 0 duplicate rows in 24,042 ms |
| Safe failure probe | PASS — 4 rejected-record errors detected; 0 temporary rows loaded |
| Full repository suite | PASS — 23 discovered, 22 passed, only the AWS integration test skipped |
| Targeted Ruff / docs / whitespace | PASS |

The deployed loader-owned inventory is one CSV file format, nine RAW tables, four audit tables, and four audit views. The database, five schemas, warehouse, storage integration, and external stage were pre-provisioned and reused. Production `LOAD_ERRORS` contains zero rows. Aggregate evidence is in [`reports/snowflake_validation.json`](../reports/snowflake_validation.json).

## Milestone 4 result

**Completed and validated against real Snowflake on 2026-10-11.** dbt authenticated with the approved key-pair service context and built the complete source-to-marts graph from the reconciled RAW layer.

| Command/check | Result |
|---|---|
| dbt dependency install | PASS — dbt Core 1.12.5, `dbt-snowflake` 1.12.1 |
| `dbt debug` | PASS — connection and production target valid |
| RAW source access | PASS — orders source returned 99,441 rows |
| `dbt compile` | PASS — complete source-to-marts graph compiled against Snowflake |
| `dbt ls --resource-type model` | PASS — 24 models: 9 staging, 4 intermediate, 7 dimensions, 4 facts |
| Manifest inventory | PASS — 24 models, 155 data tests, and 9 RAW sources |
| First real build | PASS — 167/167 nodes successful in 20.16 seconds |
| Refined incremental build | PASS — 178 pass, 1 warning, 0 errors/skips across 179 nodes in 22.72 seconds |
| Standalone `dbt test` | PASS — 154 pass, 1 warning, 0 errors/skips across 155 tests in 6.37 seconds |
| Live docs/catalog | PASS — catalog includes all 24 models and 9 sources |
| Grain reconciliation | PASS — all dimension/fact counts match source-derived expectations |
| Monetary reconciliation | PASS — merchandise R$13,591,643.70; freight R$2,251,909.54; payments R$16,008,872.12 at RAW, detail, and order grains |
| Relationship/uniqueness tests | PASS — no orphan dimension keys or duplicate fact/dimension keys |
| Source anomaly warning | WARN — 166 carrier timestamps precede purchase; values preserved and documented |

Actual mart counts are 251,987 dimension rows and 415,201 fact rows, totaling 667,188. The identical-source incremental rerun retained all fact counts with no duplicate keys. A naive direct detail join would inflate merchandise by R$617,471.64 and payments by R$4,299,262.59; the production order fact instead reconciles exactly through independent aggregates. Aggregate evidence is in [`reports/dbt_validation.json`](../reports/dbt_validation.json).

## Milestone 5 result

**Completed and validated against real Snowflake on 2026-10-14.** The framework extends the existing tests with ingestion reconciliation, RAW load-time freshness, and an isolated failure/recovery harness. It does not rewrite source anomalies or production records.

| Command/check | Result |
|---|---|
| Existing coverage audit | PASS — retained 148 generic and 7 existing singular controls; no equivalent tests duplicated |
| New production controls | PASS — batch/file/row audit and all nine RAW-to-staging row counts |
| `dbt source freshness` | PASS — final run 9/9 sources, 0 warnings/errors in 2.48 seconds; maximum age 72 hours |
| Full `dbt test` | PASS — 156 pass, 1 expected warning, 0 errors/skips across 157 tests in 17.40 seconds |
| Genuine source anomaly | WARN — 166 carrier-before-purchase records remain unchanged and distinguishable from synthetic data |
| Synthetic baseline | PASS — 0 failures across seven checks |
| Synthetic injection | PASS — exactly 1 duplicate, null key, orphan, invalid value, negative monetary value, invalid chronology, and reconciliation mismatch detected |
| Synthetic correction/recovery | PASS — all seven returned to 0; one valid temporary baseline row remained |
| Production integrity | PASS — all RAW/MARTS row-count fingerprints unchanged; 0 reserved-prefix rows before/after |
| Batch/file/row reconciliation | PASS — 26 batches, 129 files, 1,550,922 rows; zero differences or unsuccessful loads |
| RAW/staging/detail reconciliation | PASS — zero count differences for all nine staging models and four detail/order facts |
| Monetary reconciliation | PASS — merchandise R$13,591,643.70; freight R$2,251,909.54; payments R$16,008,872.12 at every declared grain |
| Lineage artifacts | PASS — live manifest/catalog regenerated; generated warehouse metadata remains ignored |
| Full repository suite | PASS — 26 discovered, 25 passed, only the separately completed AWS integration skipped |

The final inventory is 24 models, 10 declared source relations (nine business RAW sources plus one governed audit view), and 157 tests. Aggregate, non-secret evidence is in [`reports/data_quality_validation.json`](../reports/data_quality_validation.json); the methodology and catalog are in [the data-quality guide](data_quality.md).

## Milestone 6 result

**Completed and validated against real Snowflake on 2026-10-15.** The existing loader, manifest/audit contract, and dbt graph executed against isolated prefixed copies. Production RAW/MARTS and validated S3 objects were not changed.

| Check | Actual result |
|---|---|
| Historical replay | 26 batches, 129 files, 1,550,922 rows inserted; 0 updated/rejected; every batch reconciled |
| Out-of-order arrival | January 2017 preceded December 2016; deferred December records still loaded and reached facts |
| Duplicate batch | 0 inserted/updated; 5 files and 16 represented rows skipped |
| Duplicate file COPY | 0 inserted; actual file row-count difference 0 |
| Repeated dbt execution | 0 fact inserts, updates, or deletes |
| Changed record | One isolated price correction, retaining older ingestion metadata, updated 2 facts and inserted 0; rerun wrote 0 |
| Late arrival | One old-event item inserted 1 fact and updated 1 order; rerun wrote 0; freshness passed |
| Scenario full refresh | All 24 business fingerprints equal incremental results for both correction and late-arrival states |
| Unexpected duplicate business key | Rejected; transaction rolled back with 0 committed rows |
| Partial execution | Failure after first COPY/audit insert left 0 committed rows/files; FAILED recorded |
| Recovery | Same manifest committed 5 files / 1,674 rows once; audit retained FAILED → SUCCEEDED |
| Historical convergence | Zero row-count/business-record differences across 9 RAW datasets and all 24 dbt models |
| Mart counts | 415,201 fact rows + 251,987 dimension rows = 667,188 |
| Business metrics | 99,441 orders; merchandise R$13,591,643.70; freight R$2,251,909.54; payments R$16,008,872.12; differences 0 |
| Final isolated dbt tests | 156 pass, 1 deliberate warning, 0 failures/skips; 9.486 seconds |
| Production dbt tests | 156 pass, 1 deliberate warning, 0 failures/skips; 16.876 seconds |
| Freshness | Isolated 9/9 pass (3.880 seconds); production 9/9 pass (2.708 seconds), maximum age 104 hours |
| Production integrity | All 9 RAW and 11 MARTS content/count fingerprints unchanged; 0 synthetic-prefix records |
| Repository suite | 30 discovered, 29 passed, 1 previously validated AWS integration skipped; 14.646 seconds |
| Live catalog | 24 models, 10 source relations, no catalog errors; generated artifacts ignored |
| Scoped cleanup | 63 test-only relations removed; 0 relations remain under the run prefix; production/S3 preserved |

Successful RAW replay load time summed to 528.900 seconds. Duplicate batch: 3.145 seconds; failed attempt: 13.090 seconds; recovery: 17.072 seconds; historical full-refresh dbt build: 21.814 seconds. These are measured operations with different scopes, not a comparative throughput benchmark.

Per-batch IDs, inserted/updated/skipped/rejected counts, elapsed times, all 33 exact comparisons, scenario DML, production reconciliation, and scoped cleanup results are preserved in [`reports/incremental_validation.json`](../reports/incremental_validation.json). The [incremental guide](incremental_loading.md) states the immutable-source correction, deletion, serialized-writer, and recovery-test limitations. No streaming/CDC, process-kill recovery, or concurrency guarantee is claimed.

## Milestone 7 result

**Completed and validated against real AWS/Snowflake through Dockerized Airflow on 2026-10-16.** Detailed task runtimes and contracts are in [orchestration](orchestration.md); actual API/task/cloud captures are summarized in [the evidence report](../reports/orchestration_validation.json).

| Check | Actual result |
|---|---|
| Docker configuration/runtime | Configuration validates; pinned image built; PostgreSQL, API server, scheduler and DAG processor healthy |
| DAG structure | Eight boundaries; zero import errors; all publication ancestors all-success; final audit all-done but fails closed |
| Scheduled run | All eight tasks successful; 178.902 seconds |
| Manual run | All eight tasks successful; 130.439 seconds |
| Real ingestion/load | 26 batches, 155 S3 objects, 129 CSV files, 1,550,922 RAW rows verified; zero additional uploads or RAW rows |
| dbt build | 24 successful models, 156 pass, one genuine source warning, zero errors |
| Final quality suite | 156 pass / one warning / zero failures or skips; 10.108 seconds |
| Final freshness | Nine passes, zero errors/warnings; 3.534 seconds; maximum age 118 hours |
| Reconciliation | Zero file/row, RAW/staging/fact, and monetary differences; 667,188 reporting rows |
| Persistent controlled failure | Quality failed on two attempts; publication upstream-failed with zero attempts; DAG and final audit failed; 152.506 seconds |
| Last-known-good preservation | Pointer/history, eleven reporting fingerprints, twenty production fingerprints and all business metrics identical before/after failure |
| Recovery | First quality attempt failed deliberately; automatic retry succeeded; validated new version published; 206.577 seconds |
| Overlap | Manual run queued with zero attempts until scheduled run ended; execution intervals do not overlap |
| Timeout | Isolated no-cloud probe raised AirflowTaskTimeout on both attempts; final attempt 2.075 seconds |
| Audit | 33 terminal cloud task-attempt records; three successful publications; failed run published none |
| Final pipeline tests | 38 discovered, 33 passed, five expected skips; 15.112 seconds; real Snowflake integration included |
| Airflow-specific tests | Eight passed, zero skips/failures; 1.253 seconds |
| Offline tests | 38 discovered, 31 passed, seven expected skips; 0.059 seconds |
| Final integrity | Production and reporting fingerprints unchanged; zero synthetic-prefix records; genuine 166-record source anomaly preserved |
| Final operation | Failure probes disabled; DAGs paused; local services retained for inspection |

Five pipeline-suite skips comprise four tests requiring Airflow's separate environment and the previously validated AWS upload/delete integration. The four Airflow tests passed in the eight-test Airflow suite; real S3 was exercised through all DAG runs. No new AWS upload/delete claim is made. Screenshots were not captured; the optional authenticated UI capture task is documented. Candidate and three immutable publication versions are retained intentionally. Guarantees cover one serialized Airflow deployment and catchable failures, not independent concurrent writers or host-loss disaster recovery.

## Milestone 8 result

**Completed and validated on 2026-10-16.** The [monitoring/recovery guide](monitoring_recovery.md), [lightweight summary](../reports/monitoring_summary.json), and [detailed evidence](../reports/monitoring_validation.json) distinguish actual source truth, synthetic scenarios, historical events, and current publication.

| Check | Actual result |
|---|---|
| Audit model | Existing event details extended; failed attempts and quality metrics retained; no competing ledger |
| Source rejection | Two failed attempts, each 3 source = 1 valid-but-held + 2 rejected; three diagnostics; zero inserts |
| Rejection publication gate | Failed DAG, publication upstream-failed with zero attempts; pointer/history unchanged |
| Corrected source | Three accepted rows inserted once in temporary target; rerun inserted zero; zero rejected/open quarantine |
| Reconciliation retry | Deliberate expected/actual difference of one failed once; corrected retry passed |
| Quality retry | One negative synthetic candidate detected by SQL; correction returned zero violations; real dbt tests remained intact |
| Publication interruption | 74 uncommitted rows rolled back; zero residual candidate rows in eleven stores; previous pointer preserved |
| Publication retry | Second attempt succeeded; one history row/version per successful run; no duplicate version copies |
| Timeout monitoring | Two actual AirflowTaskTimeout log records from the verified M7 probe; reused, not newly injected |
| Run-level monitoring | Nine runs, seven successful/two deliberately failed, four within-run recoveries and one cross-run correction |
| Attempt-level monitoring | 73 terminal events, six retries, zero duplicate terminal keys, zero unmatched running events |
| State reconciliation | Actual Airflow and cloud-derived states agree for all nine runs; no missing cloud audits |
| Publication history | Seven unique validated publications; current version M7_30F3580F9026_; all eleven stores have correct per-version counts |
| Source inventory | 26 batches / 129 files / 1,550,922 rows verified; zero new RAW inserts; production LOAD_ERRORS diagnostics zero |
| Final production dbt | 156 pass / one genuine warning / zero errors; 13.927 seconds |
| Final freshness | Nine pass / zero errors or warnings; 4.234 seconds |
| Final reconciliation/integrity | Zero differences; twenty production and eleven reporting fingerprints unchanged; no synthetic rows |
| Fixture cleanup | Zero remaining fixture relations; temporary tables dropped and sessions closed |
| Pipeline tests | 46 discovered, 41 pass, five expected skips; 12.890 seconds |
| Airflow tests | Eight pass / zero skips; 1.126 seconds |
| Offline tests | 46 discovered, 39 pass, seven expected skips; 0.055 seconds |

New DAG durations: source rejection 66.140 seconds; corrected source 140.551; reconciliation retry 148.483; quality retry 161.749; publication retry 144.275. Combined nine-run average Airflow runtime is 147.736 seconds. The 77.78% success rate includes intentional validation failures and must not be represented as a production SLO. Two rejected lines evaluated twice produce four rejection evaluations, not four distinct bad source records.

The five pipeline skips are four Airflow-runtime tests (passed separately) and the previously completed AWS upload/delete integration. Real S3 was exercised by the five new DAG runs. Genuine source anomalies remain unchanged. No screenshots or external notification delivery are claimed; optional capture instructions and operational limitations are documented. Final DAGs are paused with probes disabled; no Milestone 9 work was started.

## Milestone 9 partial result

**Partially implemented on 2026-10-24.** Real Snowflake backend validation succeeded. A source-controlled PBIP/TMDL artifact now exists, and Microsoft schema/TMDL parsers accept its structure. No supported Power BI Desktop authoring surface exists in this macOS environment, so no refresh, rendered visual, UI filter/relationship test, screenshot, or completion commit is claimed.

| Check | Actual result |
|---|---|
| Existing business layer | Reused 11 atomic-publication `MARTS.REPORT_*` views; no business mart/view duplication |
| New operational layer | Deployed 3 `AUDIT.PBI_*` views for source freshness, DAG runs, and current pipeline health |
| Reporting inventory | 14/14 expected views present |
| Orders / customers / products / sellers | 99,441 / 96,096 / 32,951 / 3,095 |
| Payment / merchandise / freight | R$16,008,872.12 / R$13,591,643.70 / R$2,251,909.54 |
| Average order value | R$160.99 tendered payment per order; not accounting revenue |
| Delivery outcomes | 96,478 delivered; 7,826 late; 88,644 on-time; 8 with unknown timeliness |
| Delivery rates | 97.0203% delivered; 91.8800% on-time among delivered; 8.1117% late among delivered |
| Monthly reconciliation | 25 purchase month rows; monthly order/payment totals equal all-order totals |
| Monetary fanout guard | Item/order merchandise, item/order freight, and payment/order totals match exactly |
| Relationship checks | 0 order-date, item-product, or item-seller orphans |
| Production accounting | 1,550,922 source = 1,550,922 accepted + 0 rejected/missing; 0 traceable production rejected lines |
| Latest quality result | 156 pass / 1 warning / 0 failures; nine sources passed at the validated publication |
| Current freshness at query | Warning: all nine sources at 199 hours; below 720-hour error threshold |
| Current publication | Version `M7_30F3580F9026_`; validated run `m8_publication_retry_20261016` |
| Reproducible assets | Semantic YAML, exact DAX, two-page report YAML, deterministic PBIP/TMDL generator and project, deployment/validation Python, SQL, JSON evidence, build guide |
| PBIP/TMDL validation | 14 imported tables + one measure table; 41 measures; 12 relationships; two blank named pages; eight PBIP/PBIR JSON files accepted by Microsoft schemas; semantic model accepted by Microsoft's TMDL serializer |
| Power BI/UI state | Page shells only; refresh, visuals and interactions not tested; zero screenshots |

`reports/power_bi_backend_validation.json` is the measured aggregate evidence. `sql/power_bi/002_validation_queries.sql` provides independent validation queries. Seven focused Power BI repository tests pass. UI completion requires the exact remaining steps in [dashboard](dashboard.md). Milestone 9 therefore does not meet its completion rule.
