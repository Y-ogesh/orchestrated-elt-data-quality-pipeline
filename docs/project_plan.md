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
| 7. Airflow orchestration | Ingest/load/build/validate/publish/audit DAG, retries, historical batch orchestration and failure recovery | **Completed and validated** | Scheduled/manual/recovery runs passed; failed quality gate blocked publication; reporting/production fingerprints unchanged; overlap and timeout enforcement verified |
| 8. Failure handling, recovery and monitoring | Typed audit observations, rejected-row accounting, isolated quarantine, recovery, monitoring summaries | **Completed and validated** | Five new real DAG scenarios; 3 = 1 accepted + 2 rejected rows; corrected merge adds zero on rerun; 74 publication rows rolled back; 73 terminal events and seven publications reconcile |
| 9. Power BI and portfolio release | Semantic model, business measures, dashboards, screenshots, final runbook | **Completed and validated** | PBIP opened and refreshed in Desktop; 15 tables, 41 measures, 12 relationships, 33 visuals, slicer/cross-filter tests, KPI reconciliation, and genuine screenshots passed |
| 10. Final validation and portfolio readiness | Cross-milestone evidence reconciliation, local/static regression, README, security hygiene, CI and final audit | **Completed and validated** | All headline metrics reconcile to committed evidence; 46 local tests pass; Ruff, dbt parse, deterministic PBIP generation, docs/links, secret and artifact checks pass |

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

## Milestone 7 acceptance criteria

- [x] Pinned Docker/Airflow environment validates, starts healthy, and imports the eight-task DAG without errors.
- [x] Existing ingestion, RAW loading, dbt, freshness, and reconciliation mechanisms are reused.
- [x] Real scheduled and manual runs succeeded; 26 batches / 129 files / 1,550,922 rows reconciled with zero additional S3 uploads or RAW rows.
- [x] All 24 models built; 156 tests passed with one genuine source warning; nine freshness checks passed.
- [x] Persistent injected failure exhausted its retry and blocked publication with zero publication attempts.
- [x] Reporting pointer/history, eleven reporting fingerprints, and twenty production fingerprints survived failure unchanged.
- [x] Recovery succeeded after one controlled transient retry and published only validated reporting data.
- [x] Queued overlapping run had zero attempts until the active run completed; actual timeout probe failed twice with AirflowTaskTimeout.
- [x] Final pipeline suite: 33 pass / 5 expected skips; Airflow suite: 8 pass. Aggregate audit and execution evidence preserved.
- [x] Probes disabled and DAGs paused; secrets and generated runtime artifacts remain untracked. Optional UI screenshot capture is documented, not claimed.

## Milestone 8 acceptance criteria

- [x] Existing load/task/publication records reused; no competing audit ledger created.
- [x] Structured failure classification and stage/count/status observations recorded; failed quality metrics retained.
- [x] Real temporary quarantine: three source rows, one valid-but-held row, two rejected rows, three diagnostics; zero target inserts on rejection.
- [x] Corrected three-row fixture inserted once; repeat merge inserted zero; no open quarantine or remaining fixture tables.
- [x] Real source-rejection run failed twice and never published; source correction succeeded in a new run.
- [x] Reconciliation and quality defects failed on attempt one and passed on attempt two with complete audit history.
- [x] Publication interruption rolled back 74 uncommitted rows, retained the prior pointer, and published exactly once after retry.
- [x] Existing timeout logs re-read: both attempts record AirflowTaskTimeout; no new outage claimed.
- [x] Actual Airflow/cloud run states agree; 73 terminal events, zero duplicate attempt keys or unmatched running events, seven unique publications.
- [x] Final production dbt suite: 156 pass / one genuine warning; nine freshness checks pass; reconciliation and fingerprints unchanged.
- [x] Final repository suite: 41 pass / five expected skips; Airflow tests: eight pass. Sanitized summary and detailed evidence preserved.
- [x] DAGs paused, probes disabled, secrets/runtime artifacts untracked; no Milestone 9 work or external alert service provisioned.

## Milestone 9 acceptance criteria

- [x] Existing eleven published reporting views and dimensional grains audited and reused.
- [x] Three nonredundant operational Power BI views deployed and validated in real Snowflake.
- [x] Metric definitions, safe grains, currency, filters, and limitations documented.
- [x] Exact semantic-model, relationship, DAX, page, visual, filter, and interaction specifications created.
- [x] Total orders, payment value, AOV, customers, products, sellers, delivery outcomes, monthly totals, quality, accepted/rejected rows, freshness, and current publication reconciled against Snowflake.
- [x] Merchandise, freight, and payment totals match detail and order grains; tested relationship orphans are zero.
- [x] Reproducible PBIP/TMDL source created, accepted by Microsoft's TMDL serializer, and opened/refreshed in Desktop.
- [x] Executive Overview and Operations & Data Quality pages built and polished in Power BI Desktop.
- [x] Refresh, slicers, relationships, interactions, and filtered totals validated in Power BI.
- [x] Genuine redacted screenshots captured under `docs/screenshots/`.
- [x] Final Milestone 9 completion commit created only after the preceding UI evidence exists.

## Milestone 10 acceptance criteria

- [x] End-to-end architecture and every component runbook reviewed against committed evidence.
- [x] Source, S3, RAW, dbt, MARTS, audit/publication, and Power BI counts reconciled without rerunning cloud workloads.
- [x] Initial load, incremental replay, duplicate handling, idempotency, quarantine, failure/retry, rollback, corrected-source recovery, and reporting preservation evidence verified.
- [x] README finalized with business context, stack, scale, verified outcomes, reproducibility, screenshots, limitations, and documentation links.
- [x] Architecture, decision, setup, and troubleshooting statements updated to the completed Power BI state.
- [x] Local tests, repository-wide Ruff, dbt static parse, Power BI deterministic generation, docs/links, and whitespace checks pass.
- [x] Secrets, private keys, local profiles, caches, logs, generated data, and runtime artifacts remain ignored/untracked.
- [x] Cost-awareness and scoped cleanup guidance confirmed for S3, Snowflake, Docker/Airflow, and Power BI local state.
- [x] Final audit classification and evidence map preserved in `docs/final_audit.md`.
- [x] GitHub CI and MIT project license added for portfolio handoff.

## Delivery conventions

- Work one approved milestone at a time; do not represent roadmap items as complete.
- Use feature branches prefixed `codex/` for future multi-change work; protect `main` when hosted.
- Use Conventional Commits, focused diffs, and local validation before commit.
- Keep unit tests offline and fast. Mark credentialed cloud tests as integration tests. Reserve end-to-end tests for a deployed disposable environment.
- Store no secrets, raw customer-level data, generated credentials, or Power BI exports containing row-level identifiers in Git.
- Record actual commands, results, limitations, and manual steps in the validation report and journal.
