import os
import unittest
from pathlib import Path

from olist_pipeline.data_quality import (
    SYNTHETIC_CHECKS,
    DataQualityError,
    load_synthetic_fixture,
    run_synthetic_failure_cycle,
    validate_reconciliation,
)
from olist_pipeline.warehouse import SnowflakeSettings, connect_snowflake

FIXTURE = Path("tests/fixtures/data_quality_synthetic.json")


class DataQualityFixtureTests(unittest.TestCase):
    def test_fixture_covers_every_synthetic_check(self):
        fixture = load_synthetic_fixture(FIXTURE)
        check_names = {check.name for check in SYNTHETIC_CHECKS}
        defect_names = {row["defect_type"] for row in fixture["defect_orders"]}
        self.assertEqual(check_names, defect_names)
        self.assertEqual(7, len(check_names))
        self.assertEqual(1, len(fixture["baseline_orders"]))

    def test_reconciliation_validation_fails_closed(self):
        summary = {
            "batches": {
                "absolute_file_difference": 0,
                "absolute_row_difference": 1,
                "non_successful": 0,
            },
            "files": {
                "audit_rows": 1,
                "distinct_files": 1,
                "expected_rows": 1,
                "loaded_rows": 1,
                "non_successful": 0,
            },
            "raw_to_staging": {"orders": {"difference": 0}},
            "raw_to_facts": {"orders": {"difference": 0}},
            "monetary": {"payments": ["1.00", "1.00", "1.00"]},
            "freshness": {"orders": {"status": "pass"}},
            "production_synthetic_rows": 0,
        }
        with self.assertRaisesRegex(DataQualityError, "batch reconciliation"):
            validate_reconciliation(summary)


@unittest.skipUnless(
    os.environ.get("OLIST_RUN_SNOWFLAKE_INTEGRATION") == "1",
    "requires explicit OLIST_RUN_SNOWFLAKE_INTEGRATION=1",
)
class DataQualityIntegrationTests(unittest.TestCase):
    def test_real_snowflake_synthetic_fail_recover(self):
        settings = SnowflakeSettings.from_env()
        connection = connect_snowflake(settings)
        try:
            result = run_synthetic_failure_cycle(connection, settings.names, FIXTURE)
        finally:
            connection.close()

        self.assertTrue(result.production_fingerprint_unchanged)
        self.assertEqual(0, result.production_synthetic_rows_before)
        self.assertEqual(0, result.production_synthetic_rows_after)
        self.assertEqual(1, result.temporary_rows_after_recovery)
        self.assertTrue(all(value == 0 for value in result.baseline_failures.values()))
        self.assertTrue(all(value == 1 for value in result.injected_failures.values()))
        self.assertTrue(all(value == 0 for value in result.recovered_failures.values()))


if __name__ == "__main__":
    unittest.main()
