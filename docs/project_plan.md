# Project plan

Status definitions: **Completed and validated**, **Implemented but unverified**, **Partially implemented**, **Blocked**, **Not started**.

| Milestone | Scope | Status | Exit evidence |
|---|---|---|---|
| 1. Foundation and profiling | Project scaffold, official data acquisition, source contracts, profiling, architecture, dimensional design, replay design, tests, documentation | **Completed and validated** | Four unit tests pass; nine sources and six FKs validate; aggregate profile committed |
| 2. Cloud ingestion | Package files and manifests; upload immutable batches to S3; encryption and retry behavior | **Completed and validated** | Real AWS run verified 26 batches, 155 objects, 26 manifests, 1,550,922 rows, 155 streamed checksums, and a zero-upload rerun |
| 3. Snowflake RAW | Least-privilege SQL, stage/file format, transactional COPY, load audit and reconciliation | **Completed and validated** | Real Snowflake load reconciled 26 batches, 129 files, and 1,550,922 rows; identical rerun skipped all 26 batches |
| 4. dbt transformation | Staging, intermediate, dimensional marts, incremental models, tests and reconciliation | **Completed and validated** | Real dbt build created 24 models and 667,188 mart rows; 154 tests passed and one documented source-anomaly test warned |
| 5. Automated quality and lineage | Cross-layer tests, ingestion freshness, reconciliation, isolated failure injection, lineage and reporting | **Completed and validated** | 156 pass, 1 documented warning, 0 errors across 157 dbt tests; 9 freshness checks pass; all 7 synthetic defects detected and recovered |
| 6. Incremental ELT and idempotency | Sequential historical replay, duplicates, corrections, late arrivals, recovery, full-refresh equivalence | **Completed and validated** | 26 real replay batches; zero differences across 9 RAW datasets and 24 models; duplicate/correction/late-arrival/recovery checks pass; production unchanged |
| 7. Airflow orchestration | Ingest/load/build/validate/publish/audit DAG, retries, backfill and failure recovery | **Not started** | Successful local/cloud DAG runs and recovery test |
| 8. Observability and release safety | SLIs, alerts, runbooks, reporting publication gate, last-known-good preservation | **Not started** | Operational alert and audit-history evidence |
| 9. Power BI and portfolio release | Semantic model, business measures, dashboards, screenshots, final runbook | **Not started** | Reconciled dashboard and reproducible end-to-end run |

## Milestone 1 acceptance criteria

- [x] Repository and Python environment inspected.
- [x] Python package, scripts, tests, data directories, and configuration template initialized.
- [x] Official Olist Kaggle source, ownership, update date, size, and license verified.
- [x] All nine CSVs downloaded locally and profiled; raw data excluded from Git.
- [x] Schemas, counts, nulls, duplicates, ranges, keys, and six core relationships measured.
- [x] Actual source issues separated from future synthetic resilience scenarios.
- [x] Dimensional model, metrics, and anti-double-counting rule documented.
- [x] End-to-end architecture, Snowflake schemas, deterministic replay, and conventions documented.
- [x] Automated tests and source validation executed.
- [x] Required documentation created and cross-linked.
- [x] No cloud resources provisioned.

## Milestone 2 acceptance criteria

- [x] Deterministic batches and canonical manifests cover all nine source tables.
- [x] Real AWS authentication and scoped access validated through the configured credential chain.
- [x] Full ingestion uploaded 129 data objects and 26 manifests under the approved raw prefix.
- [x] Remote keys, sizes, streamed SHA-256 values, metadata, manifest content, and AES-256 encryption validated for all 155 objects.
- [x] Remote manifests reconcile to 1,550,922 source rows and 124,509,854 bytes.
- [x] Identical rerun validated and skipped all 155 objects with zero uploads.
- [x] Synthetic integration objects were created and deleted only below the approved raw-prefix test path.

## Milestone 3 acceptance criteria

- [x] Version-controlled SQL and preflight validation reuse the provisioned database, five schemas, storage integration, and external stage without account-level DDL.
- [x] Source columns remain text while every RAW row receives traceable batch/file/load metadata.
- [x] Manifest-driven COPY planning covers all 26 batches, 129 files, and 1,550,922 expected rows.
- [x] Mock validation proves clean load, rerun skip, rollback, rejected-record capture, and reconciliation behavior.
- [x] Secrets remain external; real execution requires explicit opt-in and a pre-approved storage integration.
- [x] Real stage access verified against 155 objects; bootstrap created/reused one file format, nine RAW tables, four audit tables, and four audit views.
- [x] Real load reconciled 26 batches, 129 files, and 1,550,922 rows with zero file/row differences.
- [x] Seven key checks and six relationship checks returned zero violations.
- [x] Identical rerun loaded zero rows and reconciled/skipped all 26 completed batches.
- [x] Validation-only malformed-record probe detected four errors and loaded zero temporary rows.

## Milestone 4 acceptance criteria

- [x] Current dbt Core and Snowflake adapter dependencies are declared for Python 3.10+.
- [x] Secure environment-driven dev/prod profiles and isolated development schemas are defined.
- [x] Nine staging, four intermediate, seven dimension, and four fact models are implemented and documented.
- [x] Item and payment totals are independently aggregated before the order-grain join.
- [x] Four transaction facts use merge-based incremental materializations and deterministic unique keys.
- [x] Source, grain, key, relationship, accepted-value, and monetary reconciliation tests are defined.
- [x] Full dbt parsing and live catalog generation cover 24 models, 9 sources, and 155 tests.
- [x] Source-derived acceptance counts cover every model and 667,188 expected mart rows.
- [x] `dbt debug`, `compile`, `build`, `test`, and `docs generate` completed against real Snowflake.
- [x] Actual mart counts equal all source-derived expectations: 251,987 dimension rows and 415,201 fact rows.
- [x] Incremental rerun retained fact grains and totals with no duplicates or relationship failures.
- [x] RAW, detail-fact, and order-fact monetary totals reconcile exactly; naive item/payment joining was measured and documented as inflated.

## Milestone 5 acceptance criteria

- [x] Existing 155-test coverage audited; no equivalent generic controls duplicated.
- [x] Batch/file/row audit and all nine RAW-to-staging row counts enforced by two focused singular tests.
- [x] Freshness uses RAW `_loaded_at`, with documented 7-day warning and 30-day error thresholds; all nine sources passed.
- [x] Final real-Snowflake suite: 156 pass, one documented 166-row source warning, zero errors/skips across 157 tests.
- [x] Seven isolated deterministic synthetic defect types demonstrated pass → fail/detect → correct → pass.
- [x] Production RAW/MARTS fingerprints remained unchanged and contain zero reserved synthetic rows.
- [x] 26 batches, 129 files, 1,550,922 RAW rows, all staging/detail grains, and three monetary totals reconcile exactly.
- [x] Live dbt documentation/catalog regenerated and graph dependencies verified; generated metadata remains ignored.

## Milestone 6 acceptance criteria

- [x] Reused the existing manifests, loader, audit definitions, dbt graph, and 157 quality tests.
- [x] Defined immutable RAW append, stable-key merge, duplicate handling, serialized execution, and correction/deletion limitations.
- [x] Replayed 26 batches / 129 files / 1,550,922 rows, including out-of-order historical delivery; every batch reconciled.
- [x] Identical batch, file COPY, and dbt reruns produced zero inserts/updates; unexpected business-key overlap was rejected.
- [x] Isolated price correction updated exactly two fact rows once; late item inserted one and updated one; both matched full-refresh business fingerprints.
- [x] Interruption after the first real COPY rolled back all batch progress; retry committed 1,674 rows once and preserved FAILED → SUCCEEDED audit history.
- [x] Exact full-refresh comparison returned zero differences for all 24 models; nine RAW datasets matched complete production business records.
- [x] Final 157 dbt tests returned 156 pass / 1 documented warning; nine freshness checks passed; production fingerprints remained unchanged.
- [x] Repository suite returned 29 pass / 1 separately validated AWS skip; aggregate evidence and cleanup results preserved.

## Delivery conventions

- Work one approved milestone at a time; do not represent roadmap items as complete.
- Use feature branches prefixed `codex/` for future multi-change work; protect `main` when hosted.
- Use Conventional Commits, focused diffs, and local validation before commit.
- Keep unit tests offline and fast. Mark credentialed cloud tests as integration tests. Reserve end-to-end tests for a deployed disposable environment.
- Store no secrets, raw customer-level data, generated credentials, or Power BI exports containing row-level identifiers in Git.
- Record actual commands, results, limitations, and manual steps in the validation report and journal.
