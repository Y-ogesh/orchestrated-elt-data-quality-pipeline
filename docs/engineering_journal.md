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

## 2026-10-02 — Milestone 2 AWS validation

- Reused the existing ingestion implementation and configured the approved AWS profile, `us-east-1`, and raw prefix without reading or recording credentials or identity details.
- AWS STS authentication succeeded. Bucket-level `HeadBucket` was denied by the least-privilege policy, while scoped prefix listing and the required object operations succeeded; no policy expansion was requested.
- Moved the synthetic integration-test path beneath `<S3_RAW_PREFIX>/integration-tests/<process-id>` so its write/read/delete lifecycle remains inside the authorized raw prefix. All four ingestion tests passed against AWS, and cleanup left zero integration-test objects.
- The first full S3 run uploaded 26 deterministic batches: 129 data objects plus 26 manifests, representing 1,550,922 source rows and 124,509,854 bytes.
- An independent S3 audit matched all 155 keys, streamed and verified all 155 SHA-256 values, verified all metadata and SSE-S3 settings, parsed all 26 remote manifests, and found zero missing or unexpected objects.
- The repeated full pipeline run uploaded zero objects and validated/skipped all 155 existing objects. The latest object modification time remained before the rerun began, confirming no unnecessary rewrite.
- No bucket, IAM principal, policy, ACL, or remote branch was created or modified.

## 2026-09-30 — Milestone 4

- Inspected the clean Milestone 3 baseline, nine RAW contracts, committed aggregate profile, and dimensional design. dbt was not initially installed; Python 3.9.6 and Python 3.11.14 were both available.
- The first dependency attempt correctly exposed that current Snowflake adapters require Python 3.10+. Recreated the ignored virtual environment with Python 3.11 and installed dbt Core 1.12.5 plus `dbt-snowflake` 1.12.1, matching the active v1 support line.
- Implemented secure environment-only dev/prod profiles, development schema isolation, nine source/staging models, four intermediate models, seven dimensions, four incremental facts, deterministic surrogate keys, and 143 parsed data tests.
- Preserved independent item and payment grains: their detail models aggregate separately to order before meeting in `int_orders_enriched`. Added detail-to-order fact reconciliations rather than incorrectly requiring the genuine source totals to equal one another.
- A clean `dbt parse --no-partial-parse` succeeded and `dbt ls` reported 24 models, 9 sources, and 143 tests. Generated `manifest.json` lineage remained in ignored `dbt/target/`.
- Source-derived acceptance logic produced expected counts for all 24 models and 667,188 mart rows, including a 1,314-row date spine that preserves the 2020 shipping-limit outlier.
- Offline `dbt compile --no-introspect` reached profile authentication and stopped because no private key/approved account was available. `dbt docs generate --empty-catalog --no-compile` succeeded and produced ignored local documentation/lineage artifacts without warehouse metadata. No SQL build, data tests, or catalog introspection was claimed.
- Real dbt outcome: **not run**. Actual dbt-created relations: **0**; actual mart rows: **0**. No cloud resources or permissions were changed.

## 2026-10-11 — Milestone 3 Snowflake validation

- Loaded the ignored repository `.env` without printing values; confirmed the private key exists with mode `0600`. Key-pair authentication matched the expected service user, role, X-Small warehouse, database, and a non-empty Snowflake region.
- Confirmed the warehouse auto-suspends after 60 seconds and the existing external stage lists 155 Milestone 2 objects through `OLIST_S3_INTEGRATION`.
- The first two bootstrap attempts failed safely before object creation because `CREATE DATABASE IF NOT EXISTS` and `CREATE SCHEMA IF NOT EXISTS` still require elevated privileges. Removed those control-plane statements, added explicit schema/stage/integration/URL/access preflight checks, and retained the least-privilege service role.
- Successful bootstrap reused the database, five schemas, storage integration, and stage, then created/reused one CSV file format, nine RAW tables, four audit tables, and four validation/reconciliation views.
- The first real load completed in 400,364 ms: 26 batches, 129 files, and 1,550,922 rows. Batch and file audit totals reconcile exactly; 129 distinct COPY query IDs were recorded and no production load errors occurred.
- Remote validation confirmed exact counts for all nine RAW tables, zero violations across seven key checks, and zero orphans across six relationships.
- The identical rerun completed in 24,042 ms, loaded zero batches/files/rows, and reconciled/skipped all 26 batches. A temporary malformed-schema probe detected four rejected records and loaded zero rows without touching governed RAW.
- Full validation discovered 23 tests: 22 passed and only the already-completed AWS integration test was intentionally skipped. Targeted lint, docs links, and whitespace checks passed. No dbt commands, S3 deletions, account-level DDL, IAM changes, or remote Git operations were performed.

## 2026-10-11 — Milestone 4 real dbt validation

- Reused the existing 24-model project rather than recreating it. Added the ignored runtime profile from the environment-only template and made an empty private-key passphrase optional; no credentials entered version control.
- `dbt debug` and compilation succeeded with dbt Core 1.12.5 and `dbt-snowflake` 1.12.1. RAW access returned the expected 99,441 orders.
- The first real build completed all 167 then-defined nodes in 20.16 seconds and created 9 staging views, 4 intermediate views, 7 dimension tables, and 4 incremental facts.
- Added 12 tests for monetary nonnegativity, required typed fields, payment domains, model-grain reconciliation, and date consistency. The source has 166 carrier timestamps before purchase; retained them under a deliberate warning while keeping the zero-defect chronology rules blocking.
- The refined incremental build completed 179 nodes in 22.72 seconds: 178 passed, one warned, none failed or skipped. The standalone suite completed 155 tests in 6.37 seconds: 154 passed and the same source-anomaly test warned.
- All 11 marts matched expected grains: 251,987 dimension rows plus 415,201 fact rows. Merchandise, freight, and payment totals reconciled exactly across RAW, detail facts, and `fct_orders`.
- Demonstrated the fanout risk: a naive item/payment detail join inflated merchandise by R$617,471.64 and payments by R$4,299,262.59. The production model avoids this by joining independent order-grain aggregates.
- `dbt docs generate` produced an ignored live catalog for all 24 models and 9 sources. Only aggregate validation evidence is committed; generated warehouse metadata remains ignored.

## 2026-10-14 — Milestone 5 real quality and lineage validation

- Audited the existing 155 dbt tests and retained all nonredundant generic, relationship, grain, chronology, and monetary controls. Added only batch-audit reconciliation and nine-table RAW-to-staging row preservation.
- Configured all nine RAW business sources to measure freshness from `_loaded_at`, warning after 7 days and failing after 30. The live freshness run passed 9/9 sources at a maximum age of 72 hours in 3.18 seconds.
- The complete real-Snowflake dbt suite ran 157 tests in 17.40 seconds: 156 passed, the known 166-row carrier anomaly warned, and zero failed or skipped.
- Real reconciliation measured 26 successful batches, 129 successful/distinct files, and 1,550,922 rows with zero file/row differences. All RAW/staging and RAW/detail-fact counts matched.
- Merchandise R$13,591,643.70, freight R$2,251,909.54, and payments R$16,008,872.12 reconciled exactly across RAW, detail, and order fact grains.
- Executed seven deterministic defects in Snowflake session temporary tables. The baseline returned zero, injection returned exactly one result per rule, and correction returned zero; production fingerprints were unchanged and contained zero reserved synthetic rows.
- Regenerated the ignored live dbt manifest/catalog and committed only aggregate non-secret evidence. No production row, raw S3 object, cloud permission, or remote Git branch was changed.
- Served the generated docs on localhost and visually verified the rendered lineage graph. Browser tooling could display but not safely persist the capture into the repository, so no screenshot is claimed; an optional manual capture task remains documented.
- Final repository validation discovered 26 tests: 25 passed, including the real Snowflake failure cycle and connection check; only the separately completed AWS integration was skipped. The reconciliation command now fails closed when any release condition is violated.
