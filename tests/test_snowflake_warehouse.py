import csv
import os
import tempfile
import unittest
from pathlib import Path

from olist_pipeline.dataset import TABLES
from olist_pipeline.manifest import BatchManifest, ManifestFile, sha256_file
from olist_pipeline.snowflake_sql import (
    SnowflakeNames,
    build_copy_sql,
    expected_raw_columns,
    quote_identifier,
    render_infrastructure,
    validate_s3_url,
)
from olist_pipeline.warehouse import (
    CompletedBatch,
    CopyResult,
    WarehouseLoadError,
    WarehouseLoader,
    validate_remote_warehouse,
)


def _batch(root: Path, row_count: int = 2) -> Path:
    temporary = root / "build"
    data = temporary / "table=orders" / "olist_orders_dataset.csv"
    data.parent.mkdir(parents=True)
    header = (
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    )
    with data.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        for index in range(row_count):
            writer.writerow(
                [
                    f"o{index}",
                    f"c{index}",
                    "delivered",
                    "2018-01-01 00:00:00",
                    "2018-01-01 00:01:00",
                    "2018-01-02 00:00:00",
                    "2018-01-03 00:00:00",
                    "2018-01-10 00:00:00",
                ]
            )
    item = ManifestFile(
        table="orders",
        filename=data.name,
        relative_path="table=orders/olist_orders_dataset.csv",
        sha256=sha256_file(data),
        byte_count=data.stat().st_size,
        row_count=row_count,
        source_filename=data.name,
        source_sha256="a" * 64,
        source_row_count=row_count,
    )
    manifest = BatchManifest.create(
        source="olist",
        source_version="test-v1",
        contract_version="1",
        batch_kind="transaction_month",
        logical_ingestion_date="2018-02-01",
        logical_ingestion_timestamp_utc="2018-02-01T00:00:00Z",
        window_start_utc="2018-01-01T00:00:00Z",
        window_end_utc="2018-02-01T00:00:00Z",
        files=(item,),
    )
    batch_dir = root / manifest.batch_id
    temporary.replace(batch_dir)
    (batch_dir / "manifest.json").write_bytes(manifest.to_bytes())
    return batch_dir


class FakeBackend:
    def __init__(self):
        self.completed = {}
        self.rows = {}
        self.pending = None
        self.validation_errors = []
        self.reported_row_adjustment = 0
        self.events = []

    def start_run(self, run_id, batches, expected_rows):
        self.events.append(("start_run", run_id, batches, expected_rows))

    def completed_batch(self, batch_id):
        return self.completed.get(batch_id)

    def count_batch_rows(self, manifest):
        return sum(self.rows.get((manifest.batch_id, item.sha256), 0) for item in manifest.files)

    def validate_file(self, run_id, manifest, item):
        return list(self.validation_errors)

    def record_validation_errors(self, run_id, manifest, item, errors):
        self.events.append(("validation_errors", len(errors)))

    def begin_batch(self, run_id, manifest):
        self.pending = (run_id, manifest)

    def copy_file(self, run_id, manifest, item):
        self.rows[(manifest.batch_id, item.sha256)] = item.row_count
        return CopyResult(item.row_count + self.reported_row_adjustment, "query-1")

    def count_file_rows(self, manifest, item):
        return self.rows.get((manifest.batch_id, item.sha256), 0)

    def record_file_success(self, run_id, manifest, item, result):
        self.events.append(("file", item.table, result.rows_loaded))

    def complete_batch(self, run_id, manifest):
        rows = sum(item.row_count for item in manifest.files)
        self.completed[manifest.batch_id] = CompletedBatch(
            len(manifest.files), len(manifest.files), rows, rows
        )

    def commit(self):
        self.events.append(("commit",))
        self.pending = None

    def rollback(self):
        if self.pending:
            _, manifest = self.pending
            for item in manifest.files:
                self.rows.pop((manifest.batch_id, item.sha256), None)
            self.completed.pop(manifest.batch_id, None)
        self.pending = None
        self.events.append(("rollback",))

    def record_batch_failure(self, run_id, manifest, message):
        self.events.append(("batch_failed", message))

    def finish_run(self, run_id, **values):
        self.events.append(("finish_run", values["status"]))


class SnowflakeSqlTests(unittest.TestCase):
    def test_infrastructure_templates_render_all_schemas_and_raw_tables(self):
        rendered = render_infrastructure(
            Path("sql/snowflake"),
            SnowflakeNames(),
            s3_url="s3://approved-bucket/olist/raw/",
            storage_integration="OLIST_S3_INT",
        )
        sql = "\n".join(text for _, text in rendered)
        self.assertEqual(5, len(rendered))
        self.assertNotIn("{{", sql)
        for schema in ("RAW", "STAGING", "INTERMEDIATE", "MARTS", "AUDIT"):
            self.assertIn(f'"{schema}"', sql)
        for table in (
            "CUSTOMERS",
            "GEOLOCATION",
            "ORDER_ITEMS",
            "ORDER_PAYMENTS",
            "ORDER_REVIEWS",
            "ORDERS",
            "PRODUCTS",
            "SELLERS",
            "CATEGORY_TRANSLATION",
        ):
            self.assertIn(f'."RAW".{table}', sql)

    def test_copy_sql_has_manifest_lineage_and_safe_options(self):
        with tempfile.TemporaryDirectory() as directory:
            batch_dir = _batch(Path(directory))
            from olist_pipeline.ingestion import load_manifest

            manifest = load_manifest(batch_dir)
            sql = build_copy_sql(SnowflakeNames(), manifest, manifest.files[0], "run-1")
        self.assertIn("METADATA$FILENAME", sql)
        self.assertIn("METADATA$FILE_ROW_NUMBER", sql)
        self.assertIn("ON_ERROR = 'ABORT_STATEMENT'", sql)
        self.assertIn("FORCE = FALSE", sql)
        self.assertIn(manifest.batch_id, sql)
        self.assertIn(manifest.files[0].sha256, sql)

    def test_identifier_and_s3_url_validation_reject_injection(self):
        with self.assertRaises(ValueError):
            quote_identifier("RAW; DROP DATABASE PROD")
        with self.assertRaises(ValueError):
            validate_s3_url("s3://bucket/path'; DROP STAGE x")


class WarehouseLoaderTests(unittest.TestCase):
    def test_load_and_rerun_are_reconciled_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            batch_dir = _batch(Path(directory))
            backend = FakeBackend()
            loader = WarehouseLoader(backend)
            first = loader.load([batch_dir], run_id="run-1")
            second = loader.load([batch_dir], run_id="run-2")

        self.assertEqual(
            (1, 0, 1, 2),
            (
                first.batches_loaded,
                first.batches_skipped,
                first.files_loaded,
                first.rows_loaded,
            ),
        )
        self.assertEqual(
            (0, 1, 0, 0),
            (
                second.batches_loaded,
                second.batches_skipped,
                second.files_loaded,
                second.rows_loaded,
            ),
        )

    def test_row_mismatch_rolls_back_and_records_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            batch_dir = _batch(Path(directory))
            backend = FakeBackend()
            backend.reported_row_adjustment = -1
            with self.assertRaises(WarehouseLoadError):
                WarehouseLoader(backend).load([batch_dir], run_id="run-fail")
        self.assertIn(("rollback",), backend.events)
        self.assertIn(("finish_run", "FAILED"), backend.events)
        self.assertEqual({}, backend.rows)

    def test_rejected_records_stop_copy_and_are_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            batch_dir = _batch(Path(directory))
            backend = FakeBackend()
            backend.validation_errors = [{"error": "wrong number of columns"}]
            with self.assertRaises(WarehouseLoadError):
                WarehouseLoader(backend).load([batch_dir], run_id="run-reject")
        self.assertIn(("validation_errors", 1), backend.events)
        self.assertFalse(any(event[0] == "file" for event in backend.events))

    def test_remote_validation_checks_schemas_counts_keys_and_relationships(self):
        class Cursor:
            def execute(self, sql, params=()):
                if "INFORMATION_SCHEMA\".\"SCHEMATA" in sql:
                    self.rows = [(value,) for value in ("RAW", "STAGING", "INTERMEDIATE", "MARTS", "AUDIT")]
                elif "INFORMATION_SCHEMA\".\"COLUMNS" in sql:
                    self.rows = [
                        (table.upper(), column.upper())
                        for table in TABLES
                        for column in expected_raw_columns(table)
                    ]
                elif "RAW_TABLE_COUNTS" in sql:
                    self.rows = [(table, 2 if table == "orders" else 0) for table in TABLES]
                elif "BATCH_RECONCILIATION" in sql and "status <>" in sql:
                    self.rows = [(0,)]
                elif "BATCH_RECONCILIATION" in sql:
                    self.rows = [(1,)]
                elif "FILE_LOADS" in sql:
                    self.rows = [(1,)]
                elif "RAW_KEY_VIOLATIONS" in sql or "RAW_RELATIONSHIP_VIOLATIONS" in sql:
                    self.rows = [(0,)]
                else:
                    raise AssertionError(sql)
                return self

            def fetchall(self):
                return self.rows

            def fetchone(self):
                return self.rows[0]

        class Connection:
            def cursor(self):
                return Cursor()

        with tempfile.TemporaryDirectory() as directory:
            batch_dir = _batch(Path(directory))
            result = validate_remote_warehouse(Connection(), SnowflakeNames(), [batch_dir])
        self.assertEqual(
            {
                "schemas": 5,
                "raw_tables": 9,
                "batches": 1,
                "files": 1,
                "rows": 2,
                "key_violations": 0,
                "relationship_violations": 0,
            },
            result,
        )


@unittest.skipUnless(
    os.getenv("OLIST_RUN_SNOWFLAKE_INTEGRATION") == "1",
    "requires explicit OLIST_RUN_SNOWFLAKE_INTEGRATION=1 and approved Snowflake resources",
)
class SnowflakeIntegrationTests(unittest.TestCase):
    def test_real_connection_context(self):
        from olist_pipeline.warehouse import SnowflakeSettings, connect_snowflake

        settings = SnowflakeSettings.from_env()
        connection = connect_snowflake(settings)
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE()")
            row = cursor.fetchone()
            self.assertTrue(all(row))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
