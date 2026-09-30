# Engineering journal

## 2026-09-29 — Milestone 1

- Inspected the repository: only a minimal README and initial Git commit existed on `main`; worktree was clean.
- Inspected the runtime: Python 3.9.6, pip 21.2.4, Make, and Git were available. pandas 2.3.1 was present, but the implementation intentionally does not require it. pytest, boto3, Snowflake connector, dbt, Airflow, Docker, uv, Poetry, and Kaggle CLI were absent.
- Verified the official Olist Kaggle listing and API metadata: nine CSV files, dataset ID 55151, version 2, CC BY-NC-SA 4.0, last updated 2021-10-01.
- Downloaded the public archive and extracted nine CSVs to ignored local storage. Captured full SHA-256 hashes in the generated aggregate profile.
- Implemented source contracts, profiler, relationship checks, business reconciliation, safe downloader, unit tests, Make targets, dependency metadata, and secret-safe environment template.
- First profile run correctly failed because the official translation CSV has a UTF-8 BOM. Updated every CSV reader to `utf-8-sig` and added a regression test; the subsequent full profile and validation passed.
- Recorded observed quality issues without modifying source data. Designed fact/dimension grains, Snowflake schemas, publication gates, and deterministic monthly replay.
- No cloud resources, IAM permissions, remote branches, or paid services were created or changed.

## 2026-09-30 — Milestone 2

- Confirmed Milestone 1 was amended and pushed as `e8635f1`; the starting worktree was clean.
- Found no configured AWS environment variables, AWS CLI, boto3, moto, or approved bucket. Kept real AWS execution opt-in and did not install tools or provision resources.
- Implemented deterministic batch manifests, monthly transaction partitioning, a reference snapshot, local and S3 object-store adapters, AES256 upload requests, standard AWS credential-chain support, integrity validation, immutable conflict handling, exponential transient retry, and JSON event logging.
- Added mock/local tests plus an integration test gated by both `OLIST_RUN_AWS_INTEGRATION=1` and `S3_BUCKET`. The test deletes its own prefixed objects in `finally` when explicitly run.
- Full local run emitted 25 monthly batches and one reference batch: 129 data files plus 26 manifests, 1,550,922 reconciled records, and 124,509,854 payload bytes.
- First local object-store run uploaded and validated 155 objects. A repeated full execution generated the same batch IDs, uploaded zero objects, and validated/skipped all 155.
- Real AWS result: **not run** because no approved bucket or credentials were available. No cloud resources or IAM settings were changed.

### Git history reconciliation

The first local Milestone 2 commit directly parented the initial repository commit and contained both milestone trees, consistent with amending Milestone 1 while Milestone 2 changes were staged. The remote Milestone 1 commit remained valid. Reconciliation retained `origin/main` as the baseline, computed the exact remote-to-local tree delta, and reapplied only those 20 Milestone 2 files as a new child commit. Unchanged Milestone 1 files were verified byte-identical before reconstruction.

## 2026-09-30 — Milestone 3

- Inspected the clean Milestone 2 baseline and 26 generated manifests: 129 files and 1,550,922 expected RAW rows.
- Found no Snowflake connector, key-pair configuration, account variables, approved warehouse, storage integration, or AWS configuration. No cloud connection or DDL/COPY execution was attempted.
- Verified current Snowflake guidance for external stages, storage integrations, COPY transformations/metadata, validation-mode limitations, and key-pair connector authentication.
- Added five ordered SQL modules defining the database boundaries, five schemas, CSV format, S3 stage, nine source-shaped RAW tables, four audit tables, and four reconciliation/validation views.
- Implemented safe identifier/literal rendering, environment-only key-pair configuration, infrastructure bootstrap, pre-load rejected-record capture, transactional COPY, manifest/audit duplicate prevention, row reconciliation, rollback, and opt-in connection testing.
- Local warehouse-plan validation rendered every SQL module and both COPY phases for all 129 files across 26 batches, reconciling 1,550,922 expected rows.
- Real Snowflake outcome: **not run** because approved resources and credentials were unavailable. Actual loaded rows: **0**; this is an environment limitation, not a successful cloud-load claim.

## 2026-09-30 — Milestone 4

- Inspected the clean Milestone 3 baseline, nine RAW contracts, committed aggregate profile, and dimensional design. dbt was not initially installed; Python 3.9.6 and Python 3.11.14 were both available.
- The first dependency attempt correctly exposed that current Snowflake adapters require Python 3.10+. Recreated the ignored virtual environment with Python 3.11 and installed dbt Core 1.12.5 plus `dbt-snowflake` 1.12.1, matching the active v1 support line.
- Implemented secure environment-only dev/prod profiles, development schema isolation, nine source/staging models, four intermediate models, seven dimensions, four incremental facts, deterministic surrogate keys, and 143 parsed data tests.
- Preserved independent item and payment grains: their detail models aggregate separately to order before meeting in `int_orders_enriched`. Added detail-to-order fact reconciliations rather than incorrectly requiring the genuine source totals to equal one another.
- A clean `dbt parse --no-partial-parse` succeeded and `dbt ls` reported 24 models, 9 sources, and 143 tests. Generated `manifest.json` lineage remained in ignored `dbt/target/`.
- Source-derived acceptance logic produced expected counts for all 24 models and 667,188 mart rows, including a 1,314-row date spine that preserves the 2020 shipping-limit outlier.
- Offline `dbt compile --no-introspect` reached profile authentication and stopped because no private key/approved account was available. `dbt docs generate --empty-catalog --no-compile` succeeded and produced ignored local documentation/lineage artifacts without warehouse metadata. No SQL build, data tests, or catalog introspection was claimed.
- Real dbt outcome: **not run**. Actual dbt-created relations: **0**; actual mart rows: **0**. No cloud resources or permissions were changed.
