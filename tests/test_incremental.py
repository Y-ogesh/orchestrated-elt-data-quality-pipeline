import json
import tempfile
import unittest
from pathlib import Path

from olist_pipeline.incremental import replay_sequence, validate_prefix
from olist_pipeline.ingestion import load_manifest
from olist_pipeline.manifest import BatchManifest, ManifestFile
from olist_pipeline.snowflake_sql import SnowflakeNames


class IncrementalContractTests(unittest.TestCase):
    def test_isolation_prefix_rejects_production_and_unsafe_names(self):
        for value in ("", "RAW", "M6_bad_", "M6_;DROP TABLE ORDERS"):
            with self.assertRaises(ValueError):
                validate_prefix(value)
        prefix = validate_prefix("M6_0123456789AB_")
        names = SnowflakeNames(relation_prefix=prefix)
        self.assertIn(prefix + "ORDERS", names.table("RAW", "orders"))
        self.assertNotIn(prefix, names.stage_fqn)

    def test_replay_sorts_reference_then_business_windows_not_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for kind, window in [
                ("transaction_month", "2018-02-01"),
                ("reference_snapshot", None),
                ("transaction_month", "2018-01-01"),
            ]:
                manifest = BatchManifest.create(
                    source="olist",
                    source_version="test",
                    contract_version="1",
                    batch_kind=kind,
                    logical_ingestion_date="2021-10-01",
                    logical_ingestion_timestamp_utc="2021-10-01T00:00:00Z",
                    window_start_utc=window,
                    window_end_utc=None,
                    files=(),
                )
                target = root / manifest.batch_id
                target.mkdir()
                (target / "manifest.json").write_bytes(manifest.to_bytes())
            result = [load_manifest(p) for p in replay_sequence(root)]
        self.assertEqual("reference_snapshot", result[0].batch_kind)
        self.assertEqual(["2018-01-01", "2018-02-01"], [m.window_start_utc for m in result[1:]])

    def test_duplicate_file_manifest_is_rejected_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            file = ManifestFile(
                "orders", "orders.csv", "orders.csv", "a" * 64, 100, 1, "orders.csv", "a" * 64, 1
            )
            (path / "manifest.json").write_text(json.dumps({"files": [file.to_dict()] * 2}))
            with self.assertRaisesRegex(ValueError, "duplicate file paths"):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
