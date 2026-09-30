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
