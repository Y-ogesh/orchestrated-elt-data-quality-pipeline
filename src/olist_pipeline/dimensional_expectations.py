"""Derive expected dbt model row counts from the committed aggregate source profile."""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional


def _date(value: str) -> date:
    return date.fromisoformat(value[:10])


def expected_model_rows(profile: Mapping[str, object]) -> Dict[str, int]:
    tables = profile["tables"]
    business_rules = profile["business_rules"]
    expected = {
        f"stg_{name}": int(table["rows"])
        for name, table in tables.items()
    }
    expected.update(
        {
            "int_order_item_totals": int(business_rules["orders_with_items"]),
            "int_order_payment_totals": int(business_rules["orders_with_payments"]),
            "int_orders_enriched": int(tables["orders"]["rows"]),
            "int_geography_deduplicated": int(
                tables["geolocation"]["distinct_counts"]["geolocation_zip_code_prefix"]
            ),
            "dim_customer": int(tables["customers"]["distinct_counts"]["customer_unique_id"]),
            "dim_order_customer": int(tables["customers"]["rows"]),
            "dim_product": int(tables["products"]["rows"]),
            "dim_seller": int(tables["sellers"]["rows"]),
            "dim_category": int(
                tables["products"]["distinct_counts"]["product_category_name"]
            )
            + int(tables["products"]["null_counts"]["product_category_name"] > 0),
            "dim_geography": int(
                tables["geolocation"]["distinct_counts"]["geolocation_zip_code_prefix"]
            )
            + 1,
            "fct_orders": int(tables["orders"]["rows"]),
            "fct_order_items": int(tables["order_items"]["rows"]),
            "fct_order_payments": int(tables["order_payments"]["rows"]),
            "fct_order_reviews": int(tables["order_reviews"]["rows"]),
        }
    )
    date_ranges = [
        bounds
        for name in ("orders", "order_items", "order_reviews")
        for bounds in tables[name]["date_ranges"].values()
    ]
    minimum = min(_date(bounds["min"]) for bounds in date_ranges)
    maximum = max(_date(bounds["max"]) for bounds in date_ranges)
    expected["dim_date"] = (maximum - minimum).days + 1
    return dict(sorted(expected.items()))


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=Path("reports/data_profile.json"))
    args = parser.parse_args(argv)
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    rows = expected_model_rows(profile)
    result = {
        "expected_models": len(rows),
        "expected_mart_rows": sum(
            count for model, count in rows.items() if model.startswith(("dim_", "fct_"))
        ),
        "models": rows,
        "status": "source-derived expectations; not warehouse execution",
    }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
