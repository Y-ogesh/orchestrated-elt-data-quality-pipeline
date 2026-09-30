# Snowflake warehouse and RAW loading

## Status

The Snowflake infrastructure and manifest-driven loader are implemented and locally validated. No Snowflake account connection was available, so no database, schema, stage, table, or warehouse was created and no rows were loaded remotely. Real integration remains **implemented but unverified**.

## Warehouse organization

The ordered SQL modules under `sql/snowflake/` define:

| Schema | Milestone 3 contents |
|---|---|
| `RAW` | CSV file format, external S3 stage, and nine source-shaped tables |
| `STAGING` | Empty namespace reserved for typed/renamed dbt models |
| `INTERMEDIATE` | Empty namespace reserved for reusable transformations |
| `MARTS` | Empty namespace reserved for reporting facts and dimensions |
| `AUDIT` | Load runs, batch/file loads, rejected records, reconciliation and source-contract views |

The scripts are ordered as database/schemas, file format/stage, RAW tables, audit tables, and validation views. They use validated placeholders rather than hardcoded account, bucket, role, or integration names.

## RAW preservation and lineage

Every source field lands as `VARCHAR`. RAW therefore retains source text—including malformed values for later diagnosis—without implicit type conversion. The loader adds:

- deterministic batch ID;
- `METADATA$FILENAME` and `METADATA$FILE_ROW_NUMBER`;
- generated artifact SHA-256 and source version;
- logical ingestion date, load-run UUID, and Snowflake load timestamp.

RAW tables are append-oriented. Transformations, corrected names, types, deduplication, and business rules are deferred to STAGING and later layers.

## External stage security

The stage references an existing S3 location and existing Snowflake storage integration. No AWS keys are embedded in SQL. Snowflake recommends storage integrations because they delegate access without placing cloud credentials in stage definitions. Stage creation itself does not prove that its URL or credentials work, so successful creation must not be reported as an S3 integration success. See Snowflake's [CREATE STAGE documentation](https://docs.snowflake.com/en/sql-reference/sql/create-stage) and [S3 stage guide](https://docs.snowflake.com/en/user-guide/data-load-s3-create-stage).

The project does not create storage integrations or alter IAM. An administrator must separately approve and configure a least-privilege integration whose allowed location matches the exact project prefix.

## Two-phase file loading

Snowflake documents that `VALIDATION_MODE` cannot be combined with a transformed COPY. Because the production COPY adds manifest constants and staged-file metadata, each file uses two phases:

1. Create a session-temporary table containing only the source columns as `VARCHAR`.
2. Run direct `COPY ... VALIDATION_MODE='RETURN_ALL_ERRORS'` against that table. No rows load; returned parse/column errors are saved to `AUDIT.LOAD_ERRORS`.
3. If validation is clean, begin a batch transaction.
4. Run transformed `COPY INTO RAW.<table>` with source fields plus lineage metadata, `ON_ERROR='ABORT_STATEMENT'`, and `FORCE=FALSE`.
5. Compare COPY-reported rows and warehouse rows for the batch/file checksum to the manifest count.
6. Insert file audit records, reconcile the batch, and commit atomically.
7. On any error or count mismatch, roll back the whole batch and commit a separate failure audit record.

This follows Snowflake's documented [COPY validation behavior](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table). `VALIDATE()` is not used because Snowflake returns no validation results for `ABORT_STATEMENT`, and validation of transformed COPY statements is unsupported.

## Idempotency and duplicate prevention

- A successful batch is skipped only when its latest audit record has matching expected/loaded file and row totals and RAW rows still match the manifest.
- Rows are counted by both `_batch_id` and `_file_sha256` after COPY.
- A batch without successful audit state must have zero RAW rows before loading; otherwise the loader fails closed.
- `FORCE=FALSE` retains Snowflake's file-load-history protection.
- Each non-completed batch loads in one transaction, so partial file success cannot become a published batch.
- A concurrent duplicate attempt should either encounter load-history skipping/count mismatch or find the completed audit state; it cannot be accepted as reconciled twice.

Snowflake standard-table uniqueness constraints are not relied upon because they are informational. Audit checks and post-COPY reconciliation are the enforcement mechanism.

## Audit and validation objects

| Object | Purpose |
|---|---|
| `AUDIT.LOAD_RUNS` | Overall execution status and expected/loaded totals |
| `AUDIT.BATCH_LOADS` | Batch kind, version, logical date, file/row reconciliation and failures |
| `AUDIT.FILE_LOADS` | Stage path, artifact/source checksums, COPY query ID and file counts |
| `AUDIT.LOAD_ERRORS` | Pre-validation error details and rejected records; runtime batch failures are recorded in `BATCH_LOADS` and `LOAD_RUNS` |
| `AUDIT.BATCH_RECONCILIATION` | Latest expected-versus-loaded differences per batch |
| `AUDIT.RAW_TABLE_COUNTS` | Current row counts for all nine RAW tables |
| `AUDIT.RAW_KEY_VIOLATIONS` | Duplicate natural-key group counts for the seven keyed sources |
| `AUDIT.RAW_RELATIONSHIP_VIOLATIONS` | Orphan counts for the six declared source relationships |

Geolocation and reviews intentionally have no asserted natural key, consistent with the measured source profile.

## Local validation

No connector or cloud credentials are needed:

```bash
make test
make warehouse-validate
```

`warehouse-validate` renders all infrastructure templates and both COPY phases for every local manifest. Current measured plan:

| Measure | Local result | Actual Snowflake result |
|---|---:|---:|
| Infrastructure SQL modules | 5 | Not executed |
| Batches | 26 | Not loaded |
| Data files | 129 | Not loaded |
| Expected source rows | 1,550,922 | 0 loaded / unverified |

The mock suite proves clean load, no-op rerun, count-mismatch rollback, rejected-record capture, SQL injection rejection, and all schema/table rendering. It cannot prove account privileges, stage access, Snowflake SQL compilation, query cost, or actual warehouse counts.

## Approved real execution

Prerequisites:

- existing Snowflake account, user, role, and auto-suspending warehouse;
- key-pair authentication configured for that user;
- existing approved S3 bucket/prefix containing the Milestone 2 objects;
- existing storage integration restricted to that location;
- role privileges to use the warehouse/integration and create or use the configured database objects.

The Python connector supports `SNOWFLAKE_JWT` with `private_key_file`; see Snowflake's [Python connector authentication guide](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-connect). Keep the private key and optional passphrase outside Git.

After explicit approval:

```bash
python -m pip install -e '.[cloud]'
export OLIST_RUN_SNOWFLAKE_INTEGRATION=1
export SNOWFLAKE_ACCOUNT='<account-identifier>'
export SNOWFLAKE_USER='<service-user>'
export SNOWFLAKE_ROLE='<least-privilege-role>'
export SNOWFLAKE_WAREHOUSE='<auto-suspending-warehouse>'
export SNOWFLAKE_PRIVATE_KEY_PATH='<absolute-private-key-path>'
export SNOWFLAKE_STORAGE_INTEGRATION='<existing-integration>'
export S3_BUCKET='<approved-bucket>'
export S3_RAW_PREFIX='olist/raw'

PYTHONPATH=src python -m olist_pipeline.warehouse plan
PYTHONPATH=src python -m olist_pipeline.warehouse bootstrap
PYTHONPATH=src python -m olist_pipeline.warehouse load
PYTHONPATH=src python -m olist_pipeline.warehouse validate-remote
```

`bootstrap` can create the configured database and schemas. The opt-in flag is mandatory for bootstrap/load but does not itself grant permission. Never point it at an unapproved account.

## Expected post-load checks

After a real successful load, record—not assume—the following:

```sql
SELECT * FROM OLIST_ANALYTICS.AUDIT.BATCH_RECONCILIATION
WHERE row_difference <> 0 OR file_difference <> 0;

SELECT * FROM OLIST_ANALYTICS.AUDIT.RAW_TABLE_COUNTS ORDER BY table_name;
SELECT * FROM OLIST_ANALYTICS.AUDIT.RAW_KEY_VIOLATIONS WHERE violation_count <> 0;
SELECT * FROM OLIST_ANALYTICS.AUDIT.RAW_RELATIONSHIP_VIOLATIONS WHERE orphan_rows <> 0;
```

Expected values derive from Milestone 1, but remain unverified in Snowflake until these queries actually run.

## Resource usage and cleanup

The source payload is approximately 125 MB across 129 CSVs plus 26 manifests. A single X-Small warehouse with aggressive auto-suspend should be sufficient for a portfolio validation run, but duration and credits must be measured from query history rather than estimated as results.

No cleanup is automated. After evidence is retained and destructive cleanup is explicitly approved, an owner may drop only the dedicated project database and separately remove project S3 objects. Storage integrations, IAM roles, shared warehouses, and users must not be dropped by this project.
