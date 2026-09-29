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
