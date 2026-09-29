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
