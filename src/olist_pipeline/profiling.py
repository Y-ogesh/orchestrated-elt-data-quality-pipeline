"""Deterministic, dependency-free profiler for the Olist CSV snapshot."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

from .dataset import DATE_COLUMNS, FOREIGN_KEYS, NUMERIC_COLUMNS, TABLES


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _key(row: Mapping[str, str], columns: Sequence[str]) -> Tuple[str, ...]:
    return tuple(row[column] for column in columns)


def profile_table(path: Path, table_name: str) -> Dict[str, object]:
    contract = TABLES[table_name]
    null_counts: Counter = Counter()
    distinct_values: MutableMapping[str, Set[str]] = {}
    exact_rows: Set[Tuple[str, ...]] = set()
    natural_keys: Set[Tuple[str, ...]] = set()
    date_ranges: Dict[str, List[Optional[str]]] = {
        column: [None, None] for column in DATE_COLUMNS.get(table_name, ())
    }
    numeric_ranges: Dict[str, List[Optional[float]]] = {
        column: [None, None] for column in NUMERIC_COLUMNS.get(table_name, ())
    }
    row_count = 0
    exact_duplicate_count = 0
    natural_key_duplicate_count = 0

    # utf-8-sig transparently removes the BOM present in the official
    # product_category_name_translation.csv and behaves like UTF-8 otherwise.
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        columns = tuple(reader.fieldnames or ())
        missing = sorted(set(contract.required_columns) - set(columns))
        if missing:
            raise ValueError(f"{path.name} missing required columns: {', '.join(missing)}")
        distinct_values = {column: set() for column in columns}

        for row in reader:
            row_count += 1
            row_tuple = tuple(row[column] for column in columns)
            if row_tuple in exact_rows:
                exact_duplicate_count += 1
            else:
                exact_rows.add(row_tuple)

            if contract.natural_key:
                key = _key(row, contract.natural_key)
                if key in natural_keys:
                    natural_key_duplicate_count += 1
                else:
                    natural_keys.add(key)

            for column, value in row.items():
                if value == "":
                    null_counts[column] += 1
                else:
                    distinct_values[column].add(value)

            for column, limits in date_ranges.items():
                value = row[column]
                if value:
                    limits[0] = value if limits[0] is None or value < limits[0] else limits[0]
                    limits[1] = value if limits[1] is None or value > limits[1] else limits[1]

            for column, limits in numeric_ranges.items():
                value = row[column]
                if value:
                    number = float(value)
                    limits[0] = number if limits[0] is None or number < limits[0] else limits[0]
                    limits[1] = number if limits[1] is None or number > limits[1] else limits[1]

    return {
        "file": path.name,
        "sha256": _sha256(path),
        "rows": row_count,
        "columns": list(columns),
        "null_counts": {column: null_counts[column] for column in columns},
        "distinct_counts": {column: len(distinct_values[column]) for column in columns},
        "exact_duplicate_rows": exact_duplicate_count,
        "natural_key": list(contract.natural_key),
        "natural_key_duplicate_rows": natural_key_duplicate_count,
        "date_ranges": {
            column: {"min": limits[0], "max": limits[1]}
            for column, limits in date_ranges.items()
        },
        "numeric_ranges": {
            column: {"min": limits[0], "max": limits[1]}
            for column, limits in numeric_ranges.items()
        },
    }


def _read_key_set(path: Path, columns: Sequence[str]) -> Set[Tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return {_key(row, columns) for row in csv.DictReader(stream)}


def profile_relationships(data_dir: Path) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for child, child_columns, parent, parent_columns in FOREIGN_KEYS:
        parent_keys = _read_key_set(data_dir / TABLES[parent].filename, parent_columns)
        child_path = data_dir / TABLES[child].filename
        orphan_rows = 0
        orphan_keys: Set[Tuple[str, ...]] = set()
        with child_path.open(newline="", encoding="utf-8-sig") as stream:
            for row in csv.DictReader(stream):
                key = _key(row, child_columns)
                if key not in parent_keys:
                    orphan_rows += 1
                    orphan_keys.add(key)
        results.append(
            {
                "child": child,
                "child_columns": list(child_columns),
                "parent": parent,
                "parent_columns": list(parent_columns),
                "orphan_rows": orphan_rows,
                "orphan_keys": len(orphan_keys),
            }
        )
    return results


def profile_business_rules(data_dir: Path) -> Dict[str, object]:
    item_totals: Counter = Counter()
    payment_totals: Counter = Counter()
    item_orders: Set[str] = set()
    payment_orders: Set[str] = set()

    with (data_dir / TABLES["order_items"].filename).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            item_orders.add(row["order_id"])
            item_totals[row["order_id"]] += round(float(row["price"]) + float(row["freight_value"]), 2)

    with (data_dir / TABLES["order_payments"].filename).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            payment_orders.add(row["order_id"])
            payment_totals[row["order_id"]] += round(float(row["payment_value"]), 2)

    shared_orders = item_orders & payment_orders
    differences = {
        order_id: round(payment_totals[order_id] - item_totals[order_id], 2)
        for order_id in shared_orders
    }
    mismatches = {key: value for key, value in differences.items() if abs(value) > 0.01}

    order_dates: Dict[str, Dict[str, str]] = {}
    with (data_dir / TABLES["orders"].filename).open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            order_dates[row["order_id"]] = row
    delivered_before_purchase = sum(
        bool(row["order_delivered_customer_date"])
        and row["order_delivered_customer_date"] < row["order_purchase_timestamp"]
        for row in order_dates.values()
    )
    delivered_after_estimate = sum(
        bool(row["order_delivered_customer_date"])
        and row["order_delivered_customer_date"] > row["order_estimated_delivery_date"]
        for row in order_dates.values()
    )

    return {
        "orders_with_items": len(item_orders),
        "orders_with_payments": len(payment_orders),
        "orders_with_items_without_payments": len(item_orders - payment_orders),
        "orders_with_payments_without_items": len(payment_orders - item_orders),
        "shared_orders_item_payment_difference_gt_0_01": len(mismatches),
        "max_absolute_item_payment_difference": max((abs(v) for v in differences.values()), default=0),
        "delivered_before_purchase": delivered_before_purchase,
        "delivered_after_estimated_date": delivered_after_estimate,
    }


def profile_dataset(data_dir: Path) -> Dict[str, object]:
    missing_files = [contract.filename for contract in TABLES.values() if not (data_dir / contract.filename).is_file()]
    if missing_files:
        raise FileNotFoundError("Missing dataset files: " + ", ".join(missing_files))
    return {
        "profile_schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "tables": {
            name: profile_table(data_dir / contract.filename, name)
            for name, contract in TABLES.items()
        },
        "relationships": profile_relationships(data_dir),
        "business_rules": profile_business_rules(data_dir),
    }


def write_profile(profile: Mapping[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output", type=Path, default=Path("reports/data_profile.json"))
    args = parser.parse_args(argv)
    profile = profile_dataset(args.data_dir)
    write_profile(profile, args.output)
    print(f"Profiled {len(profile['tables'])} tables -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
