import csv
import tempfile
import unittest
from pathlib import Path

from olist_pipeline.dataset import TABLES
from olist_pipeline.profiling import profile_table
from olist_pipeline.validation import validate_profile


class DatasetContractTests(unittest.TestCase):
    def test_registry_contains_all_nine_official_files(self):
        self.assertEqual(9, len(TABLES))
        self.assertEqual(9, len({contract.filename for contract in TABLES.values()}))

    def test_profile_detects_null_and_duplicate_natural_key(self):
        contract = TABLES["customers"]
        rows = [
            ["c1", "u1", "12345", "Sao Paulo", "SP"],
            ["c1", "u1", "", "Sao Paulo", "SP"],
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / contract.filename
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(contract.required_columns)
                writer.writerows(rows)
            profile = profile_table(path, "customers")

        self.assertEqual(2, profile["rows"])
        self.assertEqual(1, profile["null_counts"]["customer_zip_code_prefix"])
        self.assertEqual(1, profile["natural_key_duplicate_rows"])

    def test_profile_accepts_utf8_byte_order_mark(self):
        contract = TABLES["category_translation"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / contract.filename
            with path.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream)
                writer.writerow(contract.required_columns)
                writer.writerow(["beleza_saude", "health_beauty"])
            profile = profile_table(path, "category_translation")

        self.assertEqual(list(contract.required_columns), profile["columns"])
        self.assertEqual(1, profile["rows"])

    def test_validation_reports_contract_failures(self):
        tables = {
            name: {
                "rows": 1,
                "columns": list(contract.required_columns),
                "natural_key_duplicate_rows": 0,
            }
            for name, contract in TABLES.items()
        }
        tables["orders"]["rows"] = 0
        profile = {
            "tables": tables,
            "relationships": [
                {"child": "order_items", "parent": "orders", "orphan_rows": 2}
            ],
        }
        errors = validate_profile(profile)
        self.assertIn("orders: table is empty", errors)
        self.assertIn("order_items->orders: 2 orphan rows", errors)


if __name__ == "__main__":
    unittest.main()
