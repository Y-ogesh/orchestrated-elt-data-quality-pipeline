# Troubleshooting

## Power BI reporting

### PBIP opens but requests a server or credentials

This is intentional. Open the top-level `power_bi/OlistELTReporting/OlistELTReporting.pbip`, set the `SnowflakeServer` Power Query parameter in Desktop, then use **Close & Apply** (or the report-canvas **Apply changes** banner) before refreshing. Until the pending query change is applied, Desktop continues to resolve the connector scope as `SET_IN_POWER_BI_DESKTOP;OLIST_ELT_WH`. Authenticate through **Data source settings** only after the applied scope shows the approved host. The PBIP contains Import-mode query metadata but no server-specific account name or credentials. Do not replace the placeholder with a password, token, or key path in tracked source.

All 14 Import partitions call `Snowflake.Databases(SnowflakeServer, SnowflakeWarehouse, ...)`; none hardcodes the placeholder. There is exactly one `SnowflakeServer` definition, in `OlistELTReporting.SemanticModel/definition/expressions.tmdl`. Running the deterministic generator intentionally restores its tracked default, so finish regeneration before setting the local Desktop value and do not accept later external source changes during the same validation session.

### PBIP opens with blank or incomplete report pages

The tracked project contains 33 native visual definitions across two completed pages. Run `make power-bi-project` and confirm deterministic generation reports 33 visuals. If Desktop still opens blank pages, verify that the entire `OlistELTReporting.Report/definition/pages/` tree was cloned and that no merge, sync, or antivirus tool removed nested `visual.json` files. Do not recreate visuals until the tracked PBIR files and repository status have been checked.

### The backend validator reports missing `S3_BUCKET`

The Power BI command reuses the secure Snowflake settings object, whose preflight contract includes the project S3 bucket even though reporting validation performs no S3 operation. Load the ignored `.env`, then export the documented non-secret `S3_BUCKET` and `S3_RAW_PREFIX` values before rerunning. Do not add AWS credentials to `.env`.

### Power BI totals grow after selecting a seller or category

Do not use order-level Payment Value or Merchandise Value directly in seller/category visuals and do not enable bidirectional relationships. Use the item-safe measures in `power_bi/measures.dax`: `Item Orders`, `Item Merchandise Value`, and the distinct-order item-selection delivery measures. An order can contain multiple items/categories and no defensible category payment allocation exists.

### Delivered Orders does not equal On-time plus Late

Eight published delivered orders have null delivery timeliness. Keep `Delivered Orders with Unknown Timeliness` visible; do not classify null as on-time merely to force two-way reconciliation.

### Power BI current freshness differs from the latest validated run

`PBI_SOURCE_FRESHNESS` calculates age at query time from RAW `_loaded_at`, so a fixed snapshot becomes older. `freshness_sources_passed_at_validation` is the historical result stored with the last successful quality task. The dashboard must label current freshness separately from validation-time freshness.

### PBIP opens with local credentials or cache changes

Connection settings and imported cache are local artifacts. Confirm `**/.pbi/localSettings.json` and `**/.pbi/cache.abf` remain ignored and remove them from staging if Power BI Desktop created them. Never commit server tokens, passwords, private keys, or exported row-level data.

## Download cannot resolve or reach Kaggle

Confirm network/DNS access and open the [official dataset page](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Retry `make download`. In restricted environments, download the archive manually from the official page and extract exactly nine CSVs into `data/raw/`. Do not commit them.

## Kaggle requires authentication

Kaggle's public endpoint worked without credentials during Milestone 1. If policy changes, configure Kaggle credentials in its standard user-level location, never in this repository. Alternatively use an authenticated browser download from the official Olist listing.

## `Missing dataset files`

Run `make download` and verify filenames have not been renamed. The validator expects the exact nine names declared in `src/olist_pipeline/dataset.py`.

## Translation file reports a missing first column

The official translation CSV begins with a UTF-8 BOM. Repository readers already use `utf-8-sig`. Custom readers must do the same or strip the BOM before comparing the header.

## Profile hash differs

Stop and treat the files as a different source artifact. Check that the files came from the official Olist listing, record the new metadata, compare schema/count changes, and create new profile evidence. Do not edit hashes manually.

## Validation reports natural-key duplicates or orphans

Do not delete or rewrite RAW rows. Confirm the source version, inspect aggregate counts without publishing customer/order IDs, and classify the condition as either an upstream source change or a pipeline defect. Update the contract only after a reviewed modeling decision.

## Python import errors

Run Make targets from the repository root; they set `PYTHONPATH=src`. For direct commands use `PYTHONPATH=src python3 -m olist_pipeline.validation --data-dir data/raw`, or install the project in an activated virtual environment with `python -m pip install -e .`.

## Why payment and item totals differ

The source contains different child grains and 303 shared orders differ by more than R$0.01. Always aggregate each child to `order_id` separately. The difference is a quality/reconciliation output, not permission to fan out or force values equal.

## S3 mode says boto3 is missing

Install only the declared cloud extras in an activated environment: `python -m pip install -e '.[cloud]'`. Local ingestion and all default tests remain dependency-free.

## S3 mode says an approved bucket is required

Pass `--bucket` or export `S3_BUCKET`. The pipeline deliberately does not create a bucket or infer one. Confirm authorization and prefix ownership before running.

## `HeadBucket` returns 403 but prefix operations are authorized

A least-privilege policy may omit broad bucket-level `HeadBucket` access while allowing the exact project prefix operations. Do not broaden IAM only to make `HeadBucket` pass. Verify STS authentication without recording identity details, test scoped prefix listing if granted, and use the opt-in integration test to prove `PutObject`, metadata reads, idempotent reruns, and cleanup under `<S3_RAW_PREFIX>/integration-tests/`.

## Immutable object conflict

An object already exists at a deterministic key with a different checksum or byte count. Do not overwrite it. Verify the source version, manifest, prefix, and bucket; use a new reviewed source/contract version only when the content legitimately changed.

## A prior upload stopped before the manifest

Rerun the same batch. Matching data objects are validated and skipped, missing objects are uploaded, and the manifest is written last. If the manifest already exists, every referenced object is rechecked.

## Snowflake execution refuses to start

Real execution requires `OLIST_RUN_SNOWFLAKE_INTEGRATION=1` plus every required Snowflake/S3 variable. This guard prevents accidental resource creation or warehouse usage. Run `make warehouse-validate` for an offline plan check.

## Snowflake connector is missing

Activate a virtual environment and install `python -m pip install -e '.[cloud]'`. Do not install or configure it merely to run offline unit tests.

## Bootstrap reports `CREATE DATABASE` or `CREATE SCHEMA` privilege errors

Current bootstrap code never issues account-level database/schema DDL. If this error appears, update to the least-privilege implementation and confirm the database plus `RAW`, `STAGING`, `INTERMEDIATE`, `MARTS`, and `AUDIT` schemas were pre-provisioned. Do not grant `CREATE DATABASE` merely to run the application loader.

## Existing stage cannot be validated or files cannot be read

Confirm `SNOWFLAKE_STAGE` names the pre-provisioned stage, its storage integration allows the exact S3 prefix, and the Snowflake IAM principal can list/read the objects. Bootstrap compares the stage integration and normalized URL to configuration and requires at least one readable object before creating loader-owned objects.

## Batch has uncommitted RAW rows

The loader fails closed when rows exist without a successful reconciled batch audit record. Do not delete them automatically. Inspect COPY query history and audit records, then perform any cleanup only with explicit approval.

## dbt is missing or refuses the Python version

The current transform dependency group requires Python 3.10 or newer. Create the dbt environment with an available newer interpreter such as `python3.11 -m venv .venv`, activate it, and install `python -m pip install -e '.[transform]'`. The dependency-free commands continue to support Python 3.9.

## dbt cannot find `profiles.yml`

Copy `dbt/profiles.yml.example` to ignored `dbt/profiles.yml` and set `DBT_PROFILES_DIR=dbt`, or place it at `~/.dbt/profiles.yml` and unset the override. Never add rendered credentials or private-key material to Git.

## dbt compile stops at a private key or connection error

`dbt parse` can validate project structure without connecting, but compilation and execution may initialize the adapter connection. Confirm that `SNOWFLAKE_PRIVATE_KEY_PATH` points to the approved key, the public key is assigned to the configured user, an encrypted key has its secret passphrase configured, and the account/role/warehouse variables are correct. Do not substitute a production credential merely to make an offline check pass.

## dbt builds into an unexpected schema

The `dev` target intentionally prefixes custom layers as `<DBT_DEV_SCHEMA>_STAGING`, `_INTERMEDIATE`, and `_MARTS`. The `prod` target uses the unprefixed governed schemas. Check `target.name`, `DBT_DEV_SCHEMA`, and the custom `generate_schema_name` macro before running; do not bypass isolation by hardcoding schemas in model SQL.

## Order totals multiply after a model change

Never join item-detail and payment-detail models directly. Preserve `int_order_item_totals` and `int_order_payment_totals` as separate order-grain inputs to `int_orders_enriched`, then run the two singular monetary reconciliation tests. A genuine item/payment difference is an exception flag, not evidence of join fanout.

## dbt warns about carrier timestamps before purchase

The validated source contains 166 orders whose carrier timestamp precedes purchase. The dedicated test is intentionally warning-level because dbt preserves this source anomaly rather than rewriting timestamps. Approval, customer-delivery, estimated-delivery, and review-answer ordering rules remain blocking and currently pass.

## Freshness reports stale historical business dates

The repository freshness definition uses RAW `_loaded_at`, not purchase, delivery, review, or logical replay dates. Confirm the source YAML still declares `_loaded_at` and that dbt is reading the governed RAW schema. A valid historical Olist timestamp must not make pipeline freshness fail.

## Freshness warns after a fixed-snapshot validation pause

The 7-day warning is intentional for the weekly validation cadence; the 30-day threshold is blocking. A fixed public snapshot does not receive new business events, so refresh means a successful repeat of the warehouse load/validation process. Investigate the latest successful load rather than changing the threshold to silence the warning.

## Synthetic quality cycle refuses to run

Set `OLIST_RUN_SNOWFLAKE_INTEGRATION=1` only after loading the approved ignored configuration. The runner requires the real Snowflake connector and creates session temporary tables in `AUDIT`. Do not replace these with permanent tables or insert synthetic rows into RAW/MARTS.

## Synthetic leakage or production fingerprint mismatch

Stop and inspect the reported relation/count before any cleanup. The runner uses the reserved `__dq_synthetic_` prefix and drops its temporary tables in `finally`; a production match or changed fingerprint indicates an unexpected external mutation or implementation defect. Do not delete production records automatically.

## An incremental batch overlaps an existing business key

The historical loader is append-only. A new batch repeating a declared business key is rejected before commit, and the entire batch is rolled back. Verify the source/version/window instead of forcing the COPY or deduplicating silently. A legitimate correction needs an approved source correction process; downstream facts support keyed updates once that corrected source relation is available.

## Replay stops after a successful load or build

Resume `--phase replay` with the same run prefix. Batch audit state remains authoritative: successfully reconciled batches skip, and recorded successful dbt artifacts can recover a missing local evidence entry. Check the ignored per-step logs if a model/test actually failed. Scenario/convergence phases are intentionally not blindly replaceable after partial failure; inspect their owned relations before retrying.

## A late source change is missing behind a watermark

Current fact models use full projected-row comparison before merge. Ensure the deployed SQL no longer uses the earlier global `MAX(source_loaded_at)` cutoff. Check stable source keys and model dependencies; do not move historical business timestamps forward to manufacture freshness.

## Airflow startup or authentication fails

Use `docker compose config --quiet` and inspect only the relevant service logs. Set `AIRFLOW_UID=$(id -u)` so read-only private files remain readable without relaxing their host permissions. The metadata connection command must use `sys.stdout.write`, not `print`: a trailing newline can become part of the database name. The generated SimpleAuth password file must be writable because Airflow opens it with `a+`; AWS and Snowflake key mounts must remain read-only.

## Airflow publication is upstream-failed

This is intentional after a failed gate. Inspect the first failed task and `AUDIT.PIPELINE_TASK_ATTEMPTS`. The final `all_done` audit task also fails to preserve the correct failed DAG status. Remove the failure condition and submit a new run; never clear publication alone or bypass the six success gates. Reporting remains on the previous validated version.

## A second Airflow run remains queued

`max_active_runs=1` is the safety control, not a scheduling defect. Wait for the current run to reach its terminal state. Do not increase it or run external writers against the same RAW/reporting state. Unpausing can also schedule the latest eligible Monday interval before a manual run.

## Error diagnostics exceed rejected rows

One source line can violate several rules. Count distinct run/file/line identities and report unlocated diagnostics separately; never use `COUNT(*)` of error messages as a rejected-record count. The synthetic quarantine example deliberately has three diagnostics across two rejected rows. Accepted-but-held rows are not committed rows. See [monitoring and recovery](monitoring_recovery.md).

## Monitoring reports a missing terminal event or inconsistent run state

Inspect Airflow task state, attempt number and owned subprocess before retrying. Unmatched running audit events older than 35 minutes require investigation; do not mark them successful or force publication. If a committed publication survived a later audit failure, publication history/pointer remains authoritative even when the DAG is failed. Diagnose the audit issue without recopying that immutable version. Never delete failed-attempt records to improve success rate.

## Synthetic failure modes keep failing

Use a new corrected/normal run, not the same persistent `rejected_source` configuration. For ordinary operation pause the DAG, unset `OLIST_ENABLE_ORCHESTRATION_PROBES` or set it to zero, and recreate services with Compose. Existing scenario IDs and captured evidence are immutable experiments; do not reuse them with different source inputs.
