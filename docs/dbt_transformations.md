# dbt transformations

## Status

Milestone 4 is **completed and validated against real Snowflake** as of 2026-10-11 using dbt Core 1.12.5 and `dbt-snowflake` 1.12.1. `dbt debug`, compilation, two complete builds, standalone testing, and live catalog generation succeeded. The manifest contains 9 sources, 24 models, and 155 tests; the 11 marts contain 667,188 rows.

## Project inventory

| Layer | Materialization | Models | Purpose |
|---|---|---:|---|
| STAGING | view | 9 | Rename, normalize, safely cast, and retain RAW lineage |
| INTERMEDIATE | view | 4 | Aggregate monetary children, enrich orders, reduce geography deterministically |
| MARTS dimensions | table | 7 | Customer, order-customer, product, seller, category, geography, and date dimensions |
| MARTS facts | incremental merge | 4 | Order, order-item, payment-component, and review-record facts |

The 24-model inventory intentionally excludes helper tables that do not establish a reusable grain. Model and column descriptions live beside the SQL in YAML and the live `dbt docs generate` catalog contains all 24 models and 9 sources.

## Secure configuration

`dbt/profiles.yml.example` contains environment-variable references only. It defines:

- a `dev` target that builds into isolated `DBT_DEV_<layer>` schemas;
- a `prod` target that resolves to the governed `STAGING`, `INTERMEDIATE`, and `MARTS` schemas;
- Snowflake key-pair authentication, a least-privilege role, warehouse, and query tags;
- no passwords, account values, private keys, or passphrases.

Keep the rendered profile in ignored `dbt/profiles.yml`, `~/.dbt/profiles.yml`, or another ignored profiles directory. dbt documents environment variables as the supported way to keep credentials outside project files; secrets should use the `DBT_ENV_SECRET_` prefix so log output is scrubbed. See the official [profiles guide](https://docs.getdbt.com/docs/local/profiles.yml) and [`env_var` reference](https://docs.getdbt.com/reference/dbt-jinja-functions/env_var).

## Staging behavior

Each staging view references exactly one RAW source. Identifiers and postal prefixes remain strings, whitespace-only values become null, state codes are uppercased, city/status/type labels are normalized, and numeric/timestamp fields use Snowflake `TRY_` conversions. A malformed required value therefore becomes visible to a `not_null` data test instead of aborting the view.

Every staged model retains source batch, file checksum, logical ingestion date, staged row number, load run, and load timestamp. Review rows receive a SHA-256 key over all normalized source fields because neither `review_id` nor `order_id` is unique.

## Intermediate logic

The reusable intermediate layer contains:

- `int_order_item_totals`: one row per order, with merchandise, freight, item total, product count, and seller count;
- `int_order_payment_totals`: one row per order, with payment component/type counts, installments, and payment total;
- `int_orders_enriched`: one order joined only to the two already-aggregated child models;
- `int_geography_deduplicated`: one postal prefix using median valid Brazil-bounded coordinates and a deterministic modal city/state.

This is the monetary fanout boundary. Item-detail and payment-detail relations never join each other.

## Incremental facts

The four facts use Snowflake `merge`, a non-null single-column surrogate `unique_key`, and `on_schema_change='fail'`. On an incremental run they reprocess rows at or after the maximum stored `source_loaded_at`, allowing a safe overlap at the high-water mark. A late child file advances the enriched order timestamp and refreshes the affected order fact. Full refresh remains deterministic from immutable RAW batches.

Dimensions rebuild as tables because the source snapshot is small and deterministic. This avoids incremental complexity where it would not reduce meaningful cost. dbt's [incremental model guidance](https://docs.getdbt.com/docs/build/incremental-models) recommends explicit non-null keys for merge behavior.

## Tests and reconciliation

Milestone 4 established 155 tests. Milestone 5 retains that coverage and adds two focused reconciliation tests, producing 157 tests:

- source/staging/mart uniqueness and non-null checks;
- composite-key checks for items and payments;
- accepted order statuses, payment types, scores, and translation states;
- nonnegative item, freight, payment, and installment values;
- lifecycle/review date consistency, with one deliberately non-blocking source-anomaly warning;
- source-to-staging and fact-to-dimension relationships;
- exact order-grain preservation;
- exact dimension/fact grain counts;
- independent item and payment totals reconciled from detail facts back to `fct_orders`.
- ingestion batch/file/row reconciliation from `AUDIT.BATCH_RECONCILIATION`;
- exact row preservation from all nine RAW sources to their staging views.

The real build flags 1,076 payment-versus-item differences above R$0.01; 775 orders have no items and one has no payment. These source/business conditions are not treated as transformation failures. A separate warning preserves the 166 source rows whose carrier timestamp precedes purchase. Blocking tests still prove that each independently modeled total agrees with its source child fact. See dbt's [data-test documentation](https://docs.getdbt.com/docs/build/data-tests).

## Commands

Use Python 3.10 or newer for the current dbt dependency group:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[transform]'
cp dbt/profiles.yml.example dbt/profiles.yml

dbt parse --project-dir dbt --no-partial-parse
dbt ls --project-dir dbt --resource-type model
make dbt-expectations
```

After approved Snowflake configuration and a reconciled RAW load:

```bash
dbt debug --project-dir dbt
dbt compile --project-dir dbt
dbt build --project-dir dbt --selector source_to_marts
dbt docs generate --project-dir dbt
dbt docs serve --project-dir dbt
```

`dbt docs serve` binds a local web server; do not expose generated artifacts containing warehouse metadata publicly.

## Current measured outcome

| Check | Result |
|---|---|
| `dbt debug` / RAW access | PASS — production target authenticated; RAW orders returned 99,441 rows |
| Full dbt compile | PASS — source-to-marts selector compiled against Snowflake |
| Full dbt build | PASS — 179 total: 178 pass, 1 warning, 0 errors/skips in 22.72 seconds |
| Standalone `dbt test` | PASS — 154 pass, 1 documented warning, 0 errors/skips in 6.37 seconds |
| Live `dbt docs generate` | PASS — catalog contains 24 models and 9 sources |
| Development schema routing | PASS — `DBT_DEV_STAGING`, `DBT_DEV_INTERMEDIATE`, `DBT_DEV_MARTS` |
| Source-to-mart grain reconciliation | PASS — all 11 marts matched; 667,188 actual rows |
| Monetary reconciliation | PASS — RAW, detail facts, and order facts matched exactly |
| Incremental rerun | PASS — merge rerun retained all fact counts with no duplicate keys |

Milestone 5's latest standalone run completed 157 tests in 17.40 seconds: 156 passed, the same 166-row source anomaly warned, and zero failed or skipped. Nine RAW freshness checks also passed. See [automated data quality and lineage](data_quality.md) for the extended control catalog and synthetic recovery evidence.

Generated `target/` and `logs/` artifacts are intentionally ignored because the live catalog contains warehouse metadata. Aggregate, non-secret validation evidence is committed in [`reports/dbt_validation.json`](../reports/dbt_validation.json).
