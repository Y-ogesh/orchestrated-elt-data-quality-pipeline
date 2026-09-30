import re
import unittest
from pathlib import Path

from olist_pipeline.dimensional_expectations import expected_model_rows

DBT_ROOT = Path("dbt")


class DbtProjectTests(unittest.TestCase):
    def test_expected_model_inventory(self):
        models = {
            path.stem
            for path in (DBT_ROOT / "models").rglob("*.sql")
        }
        expected = {
            "stg_customers",
            "stg_geolocation",
            "stg_order_items",
            "stg_order_payments",
            "stg_order_reviews",
            "stg_orders",
            "stg_products",
            "stg_sellers",
            "stg_category_translation",
            "int_order_item_totals",
            "int_order_payment_totals",
            "int_orders_enriched",
            "int_geography_deduplicated",
            "dim_customer",
            "dim_order_customer",
            "dim_product",
            "dim_seller",
            "dim_category",
            "dim_geography",
            "dim_date",
            "fct_orders",
            "fct_order_items",
            "fct_order_payments",
            "fct_order_reviews",
        }
        self.assertEqual(expected, models)

    def test_staging_models_reference_only_declared_sources(self):
        expected_sources = {
            "customers",
            "geolocation",
            "order_items",
            "order_payments",
            "order_reviews",
            "orders",
            "products",
            "sellers",
            "category_translation",
        }
        actual_sources = set()
        for path in (DBT_ROOT / "models" / "staging").glob("stg_*.sql"):
            sql = path.read_text(encoding="utf-8")
            matches = re.findall(r"source\('olist_raw', '([^']+)'\)", sql)
            self.assertEqual(1, len(matches), path)
            actual_sources.update(matches)
        self.assertEqual(expected_sources, actual_sources)

    def test_order_fact_never_joins_item_and_payment_detail(self):
        sql = (DBT_ROOT / "models/marts/facts/fct_orders.sql").read_text(encoding="utf-8")
        self.assertIn("ref('int_orders_enriched')", sql)
        self.assertNotIn("ref('stg_order_items')", sql)
        self.assertNotIn("ref('stg_order_payments')", sql)

        enriched = (DBT_ROOT / "models/intermediate/int_orders_enriched.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("ref('int_order_item_totals')", enriched)
        self.assertIn("ref('int_order_payment_totals')", enriched)

    def test_transaction_facts_are_keyed_incremental_merges(self):
        facts = DBT_ROOT / "models/marts/facts"
        for name in (
            "fct_orders",
            "fct_order_items",
            "fct_order_payments",
            "fct_order_reviews",
        ):
            sql = (facts / f"{name}.sql").read_text(encoding="utf-8")
            self.assertIn("materialized='incremental'", sql)
            self.assertIn("incremental_strategy='merge'", sql)
            self.assertIn("unique_key=", sql)
            self.assertIn("is_incremental()", sql)

    def test_profile_template_contains_no_credentials(self):
        profile = (DBT_ROOT / "profiles.yml.example").read_text(encoding="utf-8")
        self.assertIn("env_var('SNOWFLAKE_ACCOUNT')", profile)
        self.assertIn("private_key_path", profile)
        self.assertIn("DBT_ENV_SECRET_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", profile)
        self.assertNotRegex(profile, r"AKIA[0-9A-Z]{16}")
        self.assertNotIn("BEGIN PRIVATE KEY", profile)

    def test_source_profile_yields_expected_model_grains(self):
        import json

        profile = json.loads(Path("reports/data_profile.json").read_text(encoding="utf-8"))
        rows = expected_model_rows(profile)
        self.assertEqual(24, len(rows))
        self.assertEqual(99_441, rows["fct_orders"])
        self.assertEqual(112_650, rows["fct_order_items"])
        self.assertEqual(103_886, rows["fct_order_payments"])
        self.assertEqual(99_224, rows["fct_order_reviews"])
        self.assertEqual(1_314, rows["dim_date"])
        mart_rows = sum(
            value for key, value in rows.items() if key.startswith(("dim_", "fct_"))
        )
        self.assertEqual(667_188, mart_rows)


if __name__ == "__main__":
    unittest.main()
