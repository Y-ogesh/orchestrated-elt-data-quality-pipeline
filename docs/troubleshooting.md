# Troubleshooting

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

## Immutable object conflict

An object already exists at a deterministic key with a different checksum or byte count. Do not overwrite it. Verify the source version, manifest, prefix, and bucket; use a new reviewed source/contract version only when the content legitimately changed.

## A prior upload stopped before the manifest

Rerun the same batch. Matching data objects are validated and skipped, missing objects are uploaded, and the manifest is written last. If the manifest already exists, every referenced object is rechecked.

## Snowflake execution refuses to start

Real execution requires `OLIST_RUN_SNOWFLAKE_INTEGRATION=1` plus every required Snowflake/S3 variable. This guard prevents accidental resource creation or warehouse usage. Run `make warehouse-validate` for an offline plan check.

## Snowflake connector is missing

Activate a virtual environment and install `python -m pip install -e '.[cloud]'`. Do not install or configure it merely to run offline unit tests.

## Stage creation succeeds but files cannot be read

Snowflake does not verify stage credentials during `CREATE STAGE`. Confirm the pre-existing storage integration allows the exact `s3://bucket/prefix/`, the Snowflake IAM principal can read the objects, and the configured stage URL matches `S3_RAW_PREFIX`.

## Batch has uncommitted RAW rows

The loader fails closed when rows exist without a successful reconciled batch audit record. Do not delete them automatically. Inspect COPY query history and audit records, then perform any cleanup only with explicit approval.

## dbt is missing or refuses the Python version

The current transform dependency group requires Python 3.10 or newer. Create the dbt environment with an available newer interpreter such as `python3.11 -m venv .venv`, activate it, and install `python -m pip install -e '.[transform]'`. The dependency-free commands continue to support Python 3.9.

## dbt cannot find `profiles.yml`

Copy `dbt/profiles.yml.example` to ignored `dbt/profiles.yml` and set `DBT_PROFILES_DIR=dbt`, or place it at `~/.dbt/profiles.yml` and unset the override. Never add rendered credentials or private-key material to Git.

## dbt compile stops at a private key or connection error

`dbt parse` can validate project structure without connecting, but compilation and execution may initialize the adapter connection. Confirm that `SNOWFLAKE_PRIVATE_KEY_PATH` points to the approved key, the public key is assigned to the configured user, the passphrase secret is set, and the account/role/warehouse variables are correct. Do not substitute a production credential merely to make an offline check pass.

## dbt builds into an unexpected schema

The `dev` target intentionally prefixes custom layers as `<DBT_DEV_SCHEMA>_STAGING`, `_INTERMEDIATE`, and `_MARTS`. The `prod` target uses the unprefixed governed schemas. Check `target.name`, `DBT_DEV_SCHEMA`, and the custom `generate_schema_name` macro before running; do not bypass isolation by hardcoding schemas in model SQL.

## Order totals multiply after a model change

Never join item-detail and payment-detail models directly. Preserve `int_order_item_totals` and `int_order_payment_totals` as separate order-grain inputs to `int_orders_enriched`, then run the two singular monetary reconciliation tests. A genuine item/payment difference is an exception flag, not evidence of join fanout.
