import json
import unittest
from pathlib import Path

from olist_pipeline.power_bi import BUSINESS_VIEWS, OPERATIONAL_VIEWS, render_power_bi_sql
from olist_pipeline.snowflake_sql import SnowflakeNames


class PowerBiAssetTests(unittest.TestCase):
    def setUp(self):
        self.path = Path("sql/power_bi/001_operational_reporting_views.sql")

    def test_operational_sql_renders_without_unresolved_tokens(self):
        sql = render_power_bi_sql(self.path, SnowflakeNames(database="REPORT_DB"))
        self.assertNotIn("{{", sql)
        self.assertIn('"REPORT_DB"."AUDIT".PBI_PIPELINE_HEALTH', sql)
        self.assertEqual(3, sql.count("CREATE OR REPLACE VIEW"))

    def test_business_views_are_reused_not_recreated(self):
        sql = render_power_bi_sql(self.path, SnowflakeNames())
        for view in BUSINESS_VIEWS:
            self.assertNotIn("CREATE OR REPLACE VIEW " + view, sql)
        self.assertEqual(11, len(BUSINESS_VIEWS))
        self.assertEqual(3, len(OPERATIONAL_VIEWS))

    def test_specifications_do_not_embed_credentials(self):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in Path("power_bi").rglob("*")
            if path.is_file()
        )
        for marker in (
            "PRIVATE KEY",
            "SNOWFLAKE_PRIVATE_KEY",
            "AWS_SECRET",
            "PASSWORD=",
            "BEGIN RSA",
            "BEGIN ENCRYPTED PRIVATE KEY",
        ):
            self.assertNotIn(marker, text.upper())

    def test_dax_quotes_table_names_with_spaces(self):
        dax = Path("power_bi/measures.dax").read_text(encoding="utf-8")
        for table in (
            "Report Orders",
            "Report Order Items",
            "Report Order Reviews",
            "Pipeline Health",
            "Pipeline Runs",
        ):
            self.assertNotIn(f" {table}[", dax)
            self.assertIn(f"'{table}'[", dax)

    def test_pbip_project_inventory_and_linkage(self):
        root = Path("power_bi/OlistELTReporting")
        project = json.loads((root / "OlistELTReporting.pbip").read_text(encoding="utf-8"))
        report = json.loads(
            (root / "OlistELTReporting.Report/definition.pbir").read_text(encoding="utf-8")
        )
        self.assertEqual("OlistELTReporting.Report", project["artifacts"][0]["report"]["path"])
        self.assertEqual(
            "../OlistELTReporting.SemanticModel", report["datasetReference"]["byPath"]["path"]
        )
        tables = list((root / "OlistELTReporting.SemanticModel/definition/tables").glob("*.tmdl"))
        self.assertEqual(15, len(tables))  # 14 imports plus the dedicated Measures table.

    def test_tmdl_contains_expected_model_contract(self):
        definition = Path("power_bi/OlistELTReporting/OlistELTReporting.SemanticModel/definition")
        table_text = "\n".join(
            path.read_text(encoding="utf-8") for path in (definition / "tables").glob("*.tmdl")
        )
        relationships = (definition / "relationships.tmdl").read_text(encoding="utf-8")
        expressions = (definition / "expressions.tmdl").read_text(encoding="utf-8")
        self.assertEqual(14, table_text.count("\tmode: import") - 1)  # Exclude measure table.
        self.assertEqual(41, table_text.count("\n\tmeasure "))
        relationship_count = relationships.count("\nrelationship ") + relationships.startswith(
            "relationship "
        )
        self.assertEqual(12, relationship_count)
        self.assertEqual(2, relationships.count("\tisActive: false"))
        self.assertIn("column 'Year Month' =", table_text)
        self.assertIn("column 'Year Month Sort' =", table_text)
        self.assertIn("\tdataCategory: Time", table_text)
        self.assertIn("SET_IN_POWER_BI_DESKTOP", expressions)
        self.assertNotIn("snowflakecomputing.com", expressions.lower())

        order_customer_relationship = next(
            block
            for block in relationships.split("\n\n")
            if "'Report Orders'.'ORDER_CUSTOMER_KEY'" in block
            and "'Order Customers'.'ORDER_CUSTOMER_KEY'" in block
        )
        self.assertIn(
            "fromColumn: 'Report Orders'.'ORDER_CUSTOMER_KEY'", order_customer_relationship
        )
        self.assertIn(
            "toColumn: 'Order Customers'.'ORDER_CUSTOMER_KEY'", order_customer_relationship
        )
        self.assertIn("crossFilteringBehavior: oneDirection", order_customer_relationship)
        self.assertNotIn("fromCardinality: one", order_customer_relationship)
        self.assertNotIn("isActive: false", order_customer_relationship)

        semantic_spec = Path("power_bi/semantic_model.yaml").read_text(encoding="utf-8")
        self.assertIn(
            "from: Report Orders.ORDER_CUSTOMER_KEY, "
            "to: Order Customers.ORDER_CUSTOMER_KEY, cardinality: many-to-one",
            semantic_spec,
        )
        self.assertNotIn("cardinality: one-to-one", semantic_spec)

    def test_pbip_contains_two_blank_named_page_shells(self):
        pages_root = Path("power_bi/OlistELTReporting/OlistELTReporting.Report/definition/pages")
        pages = [
            json.loads(path.read_text(encoding="utf-8")) for path in pages_root.glob("*/page.json")
        ]
        self.assertEqual(
            {"Executive Overview", "Operations & Data Quality"},
            {page["displayName"] for page in pages},
        )
        visual_folders = [path.parent / "visuals" for path in pages_root.glob("*/page.json")]
        self.assertFalse(any(path.exists() for path in visual_folders))


if __name__ == "__main__":
    unittest.main()
