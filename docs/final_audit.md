# Final validation and portfolio audit

## Status

**Milestone 10: Completed on 2026-10-27.** This audit reconciles the committed milestone evidence and runs lightweight local/static verification. It does not relabel earlier executions or rerun validated AWS, Snowflake, Docker/Airflow, dbt warehouse, or Power BI Desktop workflows merely to reproduce evidence.

## End-to-end evidence map

| Boundary | Preserved evidence | Verified outcome |
|---|---|---|
| Olist source → deterministic batches → S3 | [`s3_validation.json`](../reports/s3_validation.json), [ingestion](ingestion.md) | 9 datasets; 26 batches; 129 CSVs + 26 manifests; 155 objects; 1,550,922 represented rows; duplicate rerun uploaded 0 |
| S3 → Snowflake RAW/AUDIT | [`snowflake_validation.json`](../reports/snowflake_validation.json), [warehouse guide](snowflake_warehouse.md) | 26 batches, 129 files, and 1,550,922 rows loaded; row/file differences 0; identical rerun loaded 0 |
| RAW → staging/intermediate/marts | [`dbt_validation.json`](../reports/dbt_validation.json), [dbt guide](dbt_transformations.md) | 24 models; 9 staging, 4 intermediate, 7 dimensions, 4 facts; 667,188 MARTS rows |
| Quality and lineage | [`data_quality_validation.json`](../reports/data_quality_validation.json), [quality guide](data_quality.md) | 156 pass / 1 documented warning / 0 failures; 9 freshness sources passed at validation; 7/7 synthetic defects detected and recovered |
| Incremental replay and convergence | [`incremental_validation.json`](../reports/incremental_validation.json), [incremental guide](incremental_loading.md) | Sequential replay, duplicates, corrections, late arrival, rollback/recovery, and all 24-model full-refresh comparisons passed |
| Airflow orchestration/publication | [`orchestration_validation.json`](../reports/orchestration_validation.json), [orchestration guide](orchestration.md) | 8-task DAG; scheduled/manual runs passed; failed quality gate published nothing; retry recovery and queued overlap protection passed |
| Monitoring and recovery | [`monitoring_validation.json`](../reports/monitoring_validation.json), [`monitoring_summary.json`](../reports/monitoring_summary.json) | 3 = 1 held + 2 rejected quarantine accounting; corrected merge wrote once; 74 publication rows rolled back; 73 terminal events and 7 publications reconciled |
| Published marts → Power BI | [`power_bi_backend_validation.json`](../reports/power_bi_backend_validation.json), [dashboard guide](dashboard.md), [screenshots](screenshots/) | 14 Import tables + Measures; 41 measures; 12 relationships; 2 pages; 33 visuals; Desktop refresh and interactions validated |

The Power BI JSON is the original 2026-10-19 backend capture, so its historical `power_bi_ui_validation` field remains a point-in-time statement. The later Desktop execution is recorded in the dashboard guide, validation report, engineering journal, PBIR source, and three runtime screenshots dated 2026-10-26.

## Final audit classification

| Component | Classification | Evidence basis |
|---|---|---|
| Python ingestion | Completed | Deterministic batches/manifests, local tests, and real S3 execution |
| AWS S3 | Completed | 155 objects and complete metadata/checksum verification |
| Snowflake RAW loading | Completed | Real COPY/audit execution and exact batch/file/row reconciliation |
| dbt warehouse | Completed | Real build/compile/test/docs execution across 24 models |
| Dimensional modeling | Completed | 7 dimensions, 4 facts, documented grains/keys, zero tested orphans |
| Data quality | Completed | 157 tests with 156 pass, 1 genuine warning, 0 failures; synthetic cycle passed |
| Incremental processing | Completed | 26-batch replay, change and late-arrival scenarios, full-refresh convergence |
| Idempotency | Completed | Duplicate S3/RAW/dbt executions produced no duplicate writes |
| Airflow orchestration | Completed | Real 8-task scheduled/manual/failure/recovery runs |
| Docker | Completed | Pinned Airflow/PostgreSQL environment built and runtime-validated |
| Monitoring | Completed | Reproducible summaries from actual audit/Airflow/publication data |
| Failure recovery | Completed | Retry, correction, rollback, timeout, and recovery evidence preserved |
| Reporting-state preservation | Completed | Failed runs did not advance the pointer; previous reporting stayed queryable |
| Power BI semantic model | Completed | 15 tables, 41 measures, 12 relationships; parser and Desktop validated |
| Power BI dashboards | Completed | 2 rendered pages, 33 visuals, interaction tests, and screenshots |
| Documentation | Completed | Architecture, contracts, runbooks, decisions, evidence, and links verified |
| Reproducibility | Completed | Deterministic generators, pinned dependencies, local commands, and cloud runbooks |
| Security/secrets hygiene | Completed | External credentials; ignored keys/profiles/caches/logs; tracked-source scan passed |
| GitHub portfolio readiness | Completed | Recruiter-facing README, screenshots, license, CI, final evidence reconciliation |

## Reconciled metrics

| Metric | Verified value |
|---|---:|
| Source datasets / batches / CSV files / S3 objects | 9 / 26 / 129 / 155 |
| Source and RAW rows | 1,550,922 |
| dbt models | 24 |
| Staging / intermediate / dimensions / facts | 9 / 4 / 7 / 4 |
| MARTS rows | 667,188 |
| dbt tests | 156 pass / 1 expected warning / 0 failures |
| Power BI tables / measures / relationships / pages / visuals | 15 / 41 / 12 / 2 / 33 |
| Orders / customers / products / sellers | 99,441 / 96,096 / 32,951 / 3,095 |
| Tendered payment / merchandise / freight | R$16,008,872.12 / R$13,591,643.70 / R$2,251,909.54 |
| Delivered / late / on-time / unknown timeliness | 96,478 / 7,826 / 88,644 / 8 |
| Accepted / rejected production rows | 1,550,922 / 0 |

## Recorded runtime evidence

These are observed operations with different scopes, not comparative performance claims:

- Snowflake initial RAW load: 400.364 seconds; reconciled no-op rerun: 24.042 seconds.
- Incremental historical replay load time: 528.900 seconds; duplicate batch: 3.145 seconds; recovery: 17.072 seconds; full-refresh dbt build: 21.814 seconds.
- Airflow scheduled/manual runs: 178.902 / 130.439 seconds; controlled failure: 152.506 seconds; recovery: 206.577 seconds.
- Monitoring validation's nine Airflow runs averaged 147.736 seconds; the 77.78% success rate includes deliberate failures and is not an SLO.

## Final lightweight verification

- Repository tests: 46 passed, 7 expected integration/environment skips.
- Targeted dbt/Power BI/orchestration tests: 17 passed, 4 Airflow-container skips.
- dbt 1.12.5 / `dbt-snowflake` 1.12.1 static parse: passed without warehouse execution.
- Ruff repository lint: passed after Python 3.9-compatible annotation/import formatting cleanup.
- PBIP deterministic regeneration: 64 files, 0 hash changes; 14 imports, 41 measures, 12 relationships, 2 pages, 33 visuals.
- Required-document and repository-relative link validation: passed.
- Whitespace, ignored-artifact, tracked-secret-pattern, and staged-content reviews: passed.

## Cost, cleanup, and operating limits

The validated Snowflake warehouse was X-Small with 60-second auto-suspend; actual credit consumption was not queried. S3 stores approximately 124.5 MB under the approved project prefix. Cleanup is deliberately scoped and manual: retain evidence first, then delete only approved project objects, account for bucket versioning, and never drop shared IAM, integration, user, or warehouse resources. Airflow cleanup distinguishes stopped containers from destructive named-volume removal.

The implementation is a fixed-snapshot, single-host portfolio system. It does not claim production deployment, enterprise scale, HA, distributed-writer safety, real-time streaming/CDC, business impact, or reliability guarantees. External alert delivery and a separately provisioned read-only BI role remain optional extensions, not blockers to the validated project scope.
