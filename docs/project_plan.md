# Project plan

Status definitions: **Completed and validated**, **Implemented but unverified**, **Partially implemented**, **Blocked**, **Not started**.

| Milestone | Scope | Status | Exit evidence |
|---|---|---|---|
| 1. Foundation and profiling | Project scaffold, official data acquisition, source contracts, profiling, architecture, dimensional design, replay design, tests, documentation | **Completed and validated** | Four unit tests pass; nine sources and six FKs validate; aggregate profile committed |
| 2. Cloud ingestion | Package files and manifests; upload immutable batches to S3; encryption and retry behavior | **Implemented but unverified** | Local full-data replay and rerun passed; real AWS test awaits an approved bucket/credentials |
| 3. Snowflake RAW | Least-privilege SQL, stage/file format, transactional COPY, load audit and reconciliation | **Implemented but unverified** | Five SQL modules and all 26 batches validate locally; real Snowflake load awaits approved resources/credentials |
| 4. dbt transformation | Staging, intermediate, dimensional marts, incremental models, tests and reconciliation | **Not started** | `dbt build` output and warehouse reconciliation |
| 5. Airflow orchestration | Ingest/load/build/validate/publish/audit DAG, retries, backfill and failure recovery | **Not started** | Successful local/cloud DAG runs and recovery test |
| 6. Observability and release safety | SLIs, alerts, runbooks, reporting publication gate, last-known-good preservation | **Not started** | Injected-failure evidence and audit history |
| 7. Power BI and portfolio release | Semantic model, business measures, dashboards, screenshots, final runbook | **Not started** | Reconciled dashboard and reproducible end-to-end run |

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

## Milestone 3 acceptance criteria

- [x] Version-controlled SQL defines five schemas, file format, external stage, nine RAW tables, audit tables, and validation views.
- [x] Source columns remain text while every RAW row receives traceable batch/file/load metadata.
- [x] Manifest-driven COPY planning covers all 26 batches, 129 files, and 1,550,922 expected rows.
- [x] Mock validation proves clean load, rerun skip, rollback, rejected-record capture, and reconciliation behavior.
- [x] Secrets remain external; real execution requires explicit opt-in and a pre-approved storage integration.
- [ ] Real schemas, stage access, row totals, keys, relationships, and rerun behavior verified in Snowflake. Blocked only by unavailable approved resources/credentials.

## Delivery conventions

- Work one approved milestone at a time; do not represent roadmap items as complete.
- Use feature branches prefixed `codex/` for future multi-change work; protect `main` when hosted.
- Use Conventional Commits, focused diffs, and local validation before commit.
- Keep unit tests offline and fast. Mark credentialed cloud tests as integration tests. Reserve end-to-end tests for a deployed disposable environment.
- Store no secrets, raw customer-level data, generated credentials, or Power BI exports containing row-level identifiers in Git.
- Record actual commands, results, limitations, and manual steps in the validation report and journal.
