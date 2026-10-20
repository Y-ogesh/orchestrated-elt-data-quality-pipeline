import subprocess
import unittest

from olist_pipeline.monitoring import ObservedFailure, classify, observation


class MonitoringTests(unittest.TestCase):
    def test_explicit_category_overrides_task(self):
        failure = ObservedFailure("freshness", "STALE_SOURCE")
        self.assertEqual("freshness", classify("validate_data_quality", failure))

    def test_timeout_is_not_quality_failure(self):
        self.assertEqual(
            "timeout_interruption",
            classify("validate_data_quality", subprocess.TimeoutExpired("dbt", 1)),
        )

    def test_secret_exception_text_is_not_recorded(self):
        result = observation("load_snowflake_raw", {}, RuntimeError("secret-value"))
        self.assertNotIn("secret-value", str(result))
        self.assertEqual("RuntimeError", result["failure_reason"])

    def test_unknown_counts_are_not_zero(self):
        result = observation("run_dbt_transformations", {})
        self.assertIsNone(result["accepted_rows"])
        self.assertIsNone(result["rejected_rows"])

    def test_diagnostic_count_is_not_rejected_rows(self):
        result = observation(
            "load_snowflake_raw",
            {
                "accounting": {
                    "source_rows": 3,
                    "accepted_rows": 1,
                    "rejected_rows": 2,
                    "diagnostics": 3,
                    "scope": "isolated_synthetic",
                }
            },
            mode="rejected_source",
        )
        self.assertEqual(2, result["rejected_rows"])
        self.assertTrue(result["synthetic"])

    def test_quality_failure_metrics_survive(self):
        metrics = {
            "tests": {"outcomes": {"pass": 156, "warn": 1}},
            "synthetic_quality": {"violations": 1},
        }
        result = observation(
            "validate_data_quality",
            metrics,
            ObservedFailure("data_quality", "SYNTHETIC_NEGATIVE_CANDIDATE"),
        )
        self.assertEqual(1, result["test_failures"])
        self.assertEqual(1, result["warning_count"])

    def test_failure_code_must_be_safe(self):
        with self.assertRaises(ValueError):
            ObservedFailure("data_quality", "password=secret")

    def test_failure_status_and_recovery_are_explicit(self):
        stale = observation("validate_data_quality", {}, ObservedFailure("freshness", "STALE"))
        self.assertEqual("failed", stale["freshness_status"])
        mismatch = observation("reconcile_raw", {}, ObservedFailure("reconciliation", "MISMATCH"))
        self.assertEqual("failed", mismatch["reconciliation_status"])
        retry = observation("reconcile_raw", {"rows": 3}, attempt=2)
        self.assertEqual("pass", retry["reconciliation_status"])
        self.assertEqual("retry_succeeded", retry["recovery_status"])


if __name__ == "__main__":
    unittest.main()
