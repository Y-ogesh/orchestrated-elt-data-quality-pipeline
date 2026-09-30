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

**Implemented and validated locally on 2026-09-30; real AWS execution unverified.** No approved bucket, AWS credential environment, AWS CLI, boto3, or moto was available, so the opt-in AWS integration test was correctly skipped.

| Command/check | Result |
|---|---|
| `make test` | PASS — 8 discovered: 7 passed, 1 real-AWS test skipped |
| First `make ingest-local` | PASS — 26 batches, 1,550,922 records, 155/155 objects uploaded and verified |
| Repeated `make ingest-local` | PASS — identical 26 batch IDs, 0 uploaded, 155/155 validated and skipped |
| Batch reconciliation | PASS — 129 data files reconcile exactly to all nine source row counts |
| Local payload | 124,509,854 bytes in 129 data files and 26 manifests |
| Conflict test | PASS — mismatched immutable checksum rejected |
| Retry test | PASS — transient failures retried with 0.25s then 0.5s test backoff |
| AWS integration | SKIPPED — requires explicit flag, approved existing bucket, and credentials |

No AWS resources were provisioned, no IAM policy was changed, and no remote mutation was performed.

## Milestone 3 result

**Implemented and validated locally on 2026-09-30; real Snowflake execution unverified.** No Snowflake connector, account configuration, key pair, approved warehouse, approved storage integration, or confirmed S3 objects were available.

| Command/check | Result |
|---|---|
| `make test` | PASS — 16 discovered: 14 passed, AWS and Snowflake integration tests skipped |
| `make warehouse-validate` | PASS — 5 SQL modules, 26 batches, 129 data files, 1,550,922 expected rows |
| SQL rendering safety | PASS — invalid identifiers and S3 URL injection rejected |
| Mock first load | PASS — COPY count reconciled to manifest and audit state committed |
| Mock rerun | PASS — completed batch validated and skipped without duplicate rows |
| Mock count mismatch | PASS — batch rolled back and failure recorded |
| Mock rejected record | PASS — error audited and COPY prevented |
| Real Snowflake bootstrap/load | SKIPPED — explicit opt-in and approved resources unavailable |

Actual Snowflake objects created: **0**. Actual warehouse rows loaded: **0**. No schema existence, warehouse count, key uniqueness, or relationship result is claimed from a real Snowflake account. Those checks are implemented as SQL views and must be recorded after authorized execution.

## Milestone 4 result

**Implemented and validated structurally on 2026-09-30; Snowflake compilation/build unverified.** dbt was installed into the ignored Python 3.11 virtual environment. No approved Snowflake account, private key, populated RAW relations, or warehouse was available.

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
| `dbt build` / warehouse tests | NOT RUN — approved Snowflake resources unavailable |
| `dbt docs generate --empty-catalog --no-compile` | PASS — ignored documentation artifacts generated without warehouse metadata |
| Warehouse catalog introspection | NOT RUN — approved Snowflake access unavailable |

Expected mart acceptance counts are 251,987 dimension rows and 415,201 fact rows. These values come from the committed source profile and declared grains; they are not actual warehouse output. Actual dbt-created relations: **0**. Actual mart rows: **0**. No model SQL execution, incremental rerun, relationship result, monetary SQL reconciliation, or generated warehouse catalog is claimed.
