import csv
import json
import os
import tempfile
import unittest
from pathlib import Path

from olist_pipeline.dataset import TABLES
from olist_pipeline.ingestion import (
    _object_key,
    build_batches,
    load_manifest,
    upload_batches,
    validate_built_batches,
)
from olist_pipeline.manifest import sha256_file
from olist_pipeline.storage import (
    LocalObjectStore,
    ObjectConflictError,
    S3ObjectStore,
    with_retry,
)


def _write(path, header, rows, *, bom=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _fixture(data_dir: Path) -> None:
    values = {
        "customers": [
            ["c1", "u1", "01000", "sao paulo", "SP"],
            ["c2", "u2", "20000", "rio de janeiro", "RJ"],
        ],
        "geolocation": [["01000", "-23.5", "-46.6", "sao paulo", "SP"]],
        "order_items": [
            ["o1", "1", "p1", "s1", "2018-01-15 00:00:00", "10.00", "2.00"],
            ["o2", "1", "p2", "s1", "2018-02-15 00:00:00", "20.00", "3.00"],
        ],
        "order_payments": [
            ["o1", "1", "credit_card", "1", "12.00"],
            ["o2", "1", "boleto", "1", "23.00"],
        ],
        "order_reviews": [
            [
                "r1",
                "o1",
                "5",
                "great",
                "message, with comma\nand newline",
                "2018-01-20 00:00:00",
                "2018-01-21 00:00:00",
            ]
        ],
        "orders": [
            [
                "o1",
                "c1",
                "delivered",
                "2018-01-01 10:00:00",
                "2018-01-01 11:00:00",
                "2018-01-02 00:00:00",
                "2018-01-05 00:00:00",
                "2018-01-10 00:00:00",
            ],
            [
                "o2",
                "c2",
                "canceled",
                "2018-02-01 10:00:00",
                "",
                "",
                "",
                "2018-02-10 00:00:00",
            ],
        ],
        "products": [
            ["p1", "cat", "3", "10", "1", "100", "10", "10", "10"],
            ["p2", "cat", "3", "10", "1", "200", "20", "20", "20"],
        ],
        "sellers": [["s1", "01000", "sao paulo", "SP"]],
        "category_translation": [["cat", "category"]],
    }
    for name, contract in TABLES.items():
        _write(
            data_dir / contract.filename,
            contract.required_columns,
            values[name],
            bom=name == "category_translation",
        )


class IngestionTests(unittest.TestCase):
    def test_batches_are_deterministic_and_preserve_source_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "raw"
            build_dir = root / "batches"
            _fixture(data_dir)
            original_hashes = {
                name: sha256_file(data_dir / contract.filename)
                for name, contract in TABLES.items()
            }

            first = build_batches(data_dir, build_dir)
            first_manifests = [load_manifest(path) for path in first]
            second = build_batches(data_dir, build_dir)
            validation = validate_built_batches(first)

            self.assertEqual(first, second)
            self.assertEqual(3, len(first))
            self.assertEqual(14, validation.file_count)
            self.assertEqual(17, validation.object_count)
            self.assertEqual(14, validation.row_count)
            self.assertEqual(
                original_hashes,
                {
                    name: sha256_file(data_dir / contract.filename)
                    for name, contract in TABLES.items()
                },
            )
            monthly = [item for item in first_manifests if item.batch_kind == "transaction_month"]
            self.assertEqual(
                ["2018-02-01", "2018-03-01"],
                sorted(m.logical_ingestion_date for m in monthly),
            )
            for table in ("orders", "customers", "order_items", "order_payments", "order_reviews"):
                with (data_dir / TABLES[table].filename).open(
                    newline="", encoding="utf-8-sig"
                ) as stream:
                    expected = sum(1 for _ in csv.DictReader(stream))
                actual = sum(
                    file.row_count
                    for manifest in monthly
                    for file in manifest.files
                    if file.table == table
                )
                self.assertEqual(expected, actual)

            review_file = next(
                path / file.relative_path
                for path in first
                for manifest in [load_manifest(path)]
                for file in manifest.files
                if file.table == "order_reviews" and file.row_count == 1
            )
            with review_file.open(newline="", encoding="utf-8") as stream:
                review = next(csv.DictReader(stream))
            self.assertEqual("message, with comma\nand newline", review["review_comment_message"])

    def test_local_upload_is_idempotent_and_detects_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "raw"
            _fixture(data_dir)
            batches = build_batches(data_dir, root / "batches")
            store = LocalObjectStore(root / "objects")

            first = upload_batches(batches, store, prefix="test/raw")
            second = upload_batches(batches, store, prefix="test/raw")

            self.assertEqual(17, sum(item.uploaded for item in first))
            self.assertEqual(0, sum(item.skipped for item in first))
            self.assertEqual(0, sum(item.uploaded for item in second))
            self.assertEqual(17, sum(item.skipped for item in second))

            manifest = load_manifest(batches[0])
            item = manifest.files[0]
            key = _object_key("test/raw", manifest, item.relative_path)
            metadata_path = root / "objects" / (key + ".olist-metadata.json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["sha256"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            manifest_key = _object_key("test/raw", manifest, "manifest.json")
            (root / "objects" / (manifest_key + ".olist-metadata.json")).unlink()

            with self.assertRaises(ObjectConflictError):
                upload_batches([batches[0]], store, prefix="test/raw")

    def test_retry_uses_exponential_backoff_for_transient_errors(self):
        calls = []
        delays = []

        class TransientError(Exception):
            response = {
                "Error": {"Code": "SlowDown"},
                "ResponseMetadata": {"HTTPStatusCode": 503},
            }

        def operation():
            calls.append(1)
            if len(calls) < 3:
                raise TransientError()

        with_retry(operation, attempts=4, base_delay_seconds=0.25, sleep=delays.append)
        self.assertEqual(3, len(calls))
        self.assertEqual([0.25, 0.5], delays)


@unittest.skipUnless(
    os.getenv("OLIST_RUN_AWS_INTEGRATION") == "1" and os.getenv("S3_BUCKET"),
    "requires explicit OLIST_RUN_AWS_INTEGRATION=1 and an approved S3_BUCKET",
)
class AwsIntegrationTests(unittest.TestCase):
    def test_real_s3_upload_rerun_and_cleanup(self):
        bucket = os.environ["S3_BUCKET"]
        region = os.getenv("AWS_REGION")
        profile = os.getenv("AWS_PROFILE") or None
        store = S3ObjectStore(bucket, region=region, profile=profile)
        prefix = f"olist/integration-tests/{os.getpid()}"
        keys = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _fixture(root / "raw")
            batches = build_batches(root / "raw", root / "batches")
            for batch in batches:
                manifest = load_manifest(batch)
                keys.extend(
                    [_object_key(prefix, manifest, item.relative_path) for item in manifest.files]
                )
                keys.append(_object_key(prefix, manifest, "manifest.json"))
            try:
                first = upload_batches(batches, store, prefix=prefix)
                second = upload_batches(batches, store, prefix=prefix)
                self.assertGreater(sum(item.uploaded for item in first), 0)
                self.assertEqual(0, sum(item.uploaded for item in second))
            finally:
                for key in keys:
                    store.client.delete_object(Bucket=bucket, Key=key)


if __name__ == "__main__":
    unittest.main()
