# Python ingestion and Amazon S3

## Scope and status

The ingestion package covers all nine Olist source tables. Deterministic batch construction, manifests, retries, immutable uploads, local object-store execution, and no-op reruns are validated. The boto3 path and opt-in integration test are implemented but have not run against AWS because no approved bucket or credentials are configured.

## Batch design

The snapshot produces 26 batches:

- 25 `transaction_month` batches for each nonempty purchase month from 2016-09 through 2018-10. Each contains orders, their order-specific customers, items, payments, and reviews.
- 1 `reference_snapshot` batch for products, sellers, geolocation, and category translations, logically dated to the dataset publication version.

Children inherit the month of their parent `order_id`. The source CSVs are never edited. Reference files are byte-for-byte copies; transaction subsets preserve every CSV field value and use deterministic UTF-8/LF serialization. Full-source checksums and counts in every file entry retain lineage to the untouched originals.

The batch ID is SHA-256 over canonical JSON containing the source/contract version, batch kind, logical window, logical ingestion timestamp, and sorted file metadata. Execution wall-clock time is excluded, so a replay on another day yields the same identity.

## Object structure

```text
olist/raw/
└── source=olist/
    └── ingestion_date=2018-02-01/
        └── batch_id=<64-character-sha256>/
            ├── table=orders/olist_orders_dataset.csv
            ├── table=customers/olist_customers_dataset.csv
            ├── table=order_items/olist_order_items_dataset.csv
            ├── table=order_payments/olist_order_payments_dataset.csv
            ├── table=order_reviews/olist_order_reviews_dataset.csv
            └── manifest.json
```

`ingestion_date` is the deterministic logical replay date, not the wall-clock upload date. Structured logs record real execution time.

## Manifest example

```json
{
  "manifest_schema_version": 1,
  "batch_id": "<sha256>",
  "batch_kind": "transaction_month",
  "contract_version": "1",
  "source": "olist",
  "source_version": "kaggle-v2-2021-10-01",
  "logical_ingestion_date": "2018-02-01",
  "logical_ingestion_timestamp_utc": "2018-02-01T00:00:00Z",
  "window_start_utc": "2018-01-01T00:00:00Z",
  "window_end_utc": "2018-02-01T00:00:00Z",
  "files": [
    {
      "table": "orders",
      "filename": "olist_orders_dataset.csv",
      "relative_path": "table=orders/olist_orders_dataset.csv",
      "sha256": "<artifact-sha256>",
      "byte_count": 0,
      "row_count": 0,
      "source_filename": "olist_orders_dataset.csv",
      "source_sha256": "<official-source-sha256>",
      "source_row_count": 99441
    }
  ]
}
```

The illustrative zero counts are placeholders; actual manifests contain measured batch values. Manifests reside in ignored local build storage and are uploaded with their batches, not committed.

## Execution

Local validation requires no third-party packages:

```bash
make download
make validate
make ingest-local
make ingest-local  # proves no-op rerun
```

Direct local command:

```bash
PYTHONPATH=src python3 -m olist_pipeline.ingestion \
  --backend local \
  --data-dir data/raw \
  --build-dir data/processed/ingestion_batches \
  --local-store data/processed/mock_s3 \
  --prefix olist/raw
```

Approved AWS execution requires `pip install -e '.[cloud]'`, an existing bucket, and credentials from the standard boto3 provider chain:

```bash
PYTHONPATH=src python3 -m olist_pipeline.ingestion \
  --backend s3 \
  --bucket "$S3_BUCKET" \
  --region "$AWS_REGION" \
  --prefix "$S3_RAW_PREFIX"
```

AWS access keys are never command arguments or application configuration fields. Prefer a short-lived SSO/profile or workload role.

## Idempotency and failure recovery

1. Validate every local artifact against manifest SHA-256 and size.
2. `HeadObject` the deterministic destination key.
3. Skip an object only when checksum metadata and size both match.
4. Fail closed on any immutable-key mismatch.
5. Upload missing data objects with `AES256` server-side encryption requested.
6. Re-read object metadata and size after each upload.
7. Upload and verify `manifest.json` last; it is the commit marker.
8. When a manifest already exists, validate every referenced object before reporting the batch as already committed.

A failure before the manifest leaves an uncommitted partial batch; rerunning validates existing files and resumes. Uploads and metadata calls retry transient throttling, timeout, internal-error, and HTTP 429/5xx responses up to four attempts with exponential delay. Permanent errors and checksum conflicts are not retried. Exceptions produce a traceback and nonzero process exit.

## Tests

Default tests use temporary directories and the filesystem-backed object store. They verify deterministic IDs, source immutability, embedded-newline/comma preservation, row reconciliation, first upload, complete no-op rerun, conflict rejection, and retry timing.

The real integration test runs only when both are present:

```bash
export OLIST_RUN_AWS_INTEGRATION=1
export S3_BUCKET='<approved-existing-bucket>'
```

It uploads tiny synthetic fixtures to `olist/integration-tests/<process-id>/`, verifies the rerun, and deletes those keys in `finally`. Do not enable it without permission to put, read metadata, and delete within that prefix.

## Minimum AWS permissions

Scope permissions to the selected bucket prefix. Runtime ingestion needs `s3:PutObject` and `s3:GetObject` (for `HeadObject`). The opt-in integration test additionally needs `s3:DeleteObject` only under its test prefix. Bucket creation, policy changes, ACL changes, IAM mutation, and unrestricted listing are not required. If the bucket mandates KMS rather than SSE-S3, add only the relevant key permissions and update the adapter in a reviewed change.

## Resource usage and cleanup

Measured locally: 124,509,854 bytes of payload across 155 objects (129 CSVs and 26 manifests). Local batch artifacts plus the mock store use about 239 MiB; raw source files use about 120 MiB. CSVs are streamed, although order/customer routing maps are held in memory.

Local cleanup is recoverable by deleting ignored `data/processed/ingestion_batches/` and `data/processed/mock_s3/`; rerunning reconstructs both.

For AWS, first retain manifests/validation evidence and obtain explicit deletion approval. Then remove only the exact project prefix, for example:

```bash
aws s3 rm "s3://$S3_BUCKET/$S3_RAW_PREFIX/source=olist/" --recursive
```

If bucket versioning is enabled, this creates delete markers rather than removing stored versions; a separately approved version cleanup is required. The pipeline never performs production-prefix deletion.
