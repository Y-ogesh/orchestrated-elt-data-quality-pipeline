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

**Implemented and validated structurally on 2026-09-30; dbt warehouse execution remains unverified.** Milestone 3 has now populated Snowflake RAW, but no dbt compile, build, test, or live catalog generation was executed during this Milestone 3 validation.

| Command/check | Result |
|---|---|
| dbt dependency install | PASS — dbt Core 1.12.5, `dbt-snowflake` 1.12.1 |
| `dbt parse --no-partial-parse` | PASS — full parse with no warning/error |
| `dbt ls --resource-type model` | PASS — 24 models: 9 staging, 4 intermediate, 7 dimensions, 4 facts |
| Parsed tests and sources | PASS — 143 data tests and 9 RAW sources |
| Development schema routing | PASS — models resolve to three isolated `DBT_DEV_*` schemas |
| `make dbt-expectations` | PASS — all 24 source-derived model counts; 667,188 expected mart rows |
| `make test` | PASS — 22 discovered: 20 passed, AWS and Snowflake integration tests skipped |
| Ruff on new Milestone 4 Python | PASS — E/F/import checks clean |
| Repository-wide Ruff advisory | FAIL — 115 inherited formatting/typing-style findings remain outside Milestone 4 scope |
| `dbt compile --no-introspect` | BLOCKED — stopped at missing key file before warehouse connection/SQL compilation |
| `dbt build` / warehouse tests | NOT RUN — remains explicitly deferred to Milestone 4 |
| `dbt docs generate --empty-catalog --no-compile` | PASS — ignored documentation artifacts generated without warehouse metadata |
| Warehouse catalog introspection | NOT RUN — remains explicitly deferred to Milestone 4 |

Expected mart acceptance counts are 251,987 dimension rows and 415,201 fact rows. These values come from the committed source profile and declared grains; they are not actual warehouse output. Actual dbt-created relations: **0**. Actual mart rows: **0**. No model SQL execution, incremental rerun, relationship result, monetary SQL reconciliation, or generated warehouse catalog is claimed.
