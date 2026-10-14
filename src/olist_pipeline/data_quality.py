"""Real reconciliation and isolated synthetic data-quality validation."""

import argparse
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .dataset import TABLES
from .snowflake_sql import SnowflakeNames, quote_fqn
from .warehouse import SnowflakeSettings, connect_snowflake

FRESHNESS_WARN_AFTER_HOURS = 7 * 24
FRESHNESS_ERROR_AFTER_HOURS = 30 * 24
SYNTHETIC_PREFIX = "__dq_synthetic_"


class DataQualityError(RuntimeError):
    """Raised when a quality validation does not produce its expected result."""


@dataclass(frozen=True)
class SyntheticCheck:
    name: str
    sql: str
    expected_failures: int = 1


@dataclass(frozen=True)
class SyntheticCycleSummary:
    baseline_failures: Mapping[str, int]
    injected_failures: Mapping[str, int]
    recovered_failures: Mapping[str, int]
    production_fingerprint_unchanged: bool
    production_synthetic_rows_before: int
    production_synthetic_rows_after: int
    temporary_rows_after_recovery: int


SYNTHETIC_CHECKS: tuple[SyntheticCheck, ...] = (
    SyntheticCheck(
        "duplicate_key",
        "SELECT COUNT(*) FROM ("
        "SELECT order_id FROM {orders} WHERE order_id IS NOT NULL "
        "GROUP BY order_id HAVING COUNT(*) > 1)",
    ),
    SyntheticCheck(
        "null_required_key",
        "SELECT COUNT(*) FROM {orders} WHERE order_id IS NULL",
    ),
    SyntheticCheck(
        "orphan_foreign_key",
        "SELECT COUNT(*) FROM {orders} o LEFT JOIN {customers} c "
        "ON o.customer_id = c.customer_id WHERE c.customer_id IS NULL",
    ),
    SyntheticCheck(
        "invalid_accepted_value",
        "SELECT COUNT(*) FROM {orders} WHERE order_status NOT IN "
        "('approved','canceled','created','delivered','invoiced','processing','shipped','unavailable')",
    ),
    SyntheticCheck(
        "negative_monetary_value",
        "SELECT COUNT(*) FROM {orders} WHERE payment_value < 0",
    ),
    SyntheticCheck(
        "invalid_date_relationship",
        "SELECT COUNT(*) FROM {orders} WHERE carrier_timestamp < purchase_timestamp",
    ),
    SyntheticCheck(
        "reconciliation_mismatch",
        "SELECT COUNT(*) FROM {orders} WHERE expected_rows <> actual_rows",
    ),
)


def load_synthetic_fixture(path: Path) -> Mapping[str, object]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    required = {check.name for check in SYNTHETIC_CHECKS}
    actual = {row["defect_type"] for row in fixture["defect_orders"]}
    if actual != required:
        raise DataQualityError(
            f"Synthetic fixture defect types do not match checks: {sorted(actual ^ required)}"
        )
    if any(row.get("defect_type") is not None for row in fixture["baseline_orders"]):
        raise DataQualityError("Baseline synthetic rows must not contain defects")
    return fixture


def _fixture_row(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        row["fixture_id"],
        row.get("order_id"),
        row["customer_id"],
        row["order_status"],
        Decimal(str(row["payment_value"])),
        datetime.fromisoformat(str(row["purchase_timestamp"])),
        datetime.fromisoformat(str(row["carrier_timestamp"])),
        int(row["expected_rows"]),
        int(row["actual_rows"]),
        row.get("defect_type"),
    )


def _run_synthetic_checks(cursor: object, orders: str, customers: str) -> dict[str, int]:
    results = {}
    for check in SYNTHETIC_CHECKS:
        cursor.execute(check.sql.format(orders=orders, customers=customers))
        results[check.name] = int(cursor.fetchone()[0])
    return results


def _production_fingerprint(cursor: object, names: SnowflakeNames) -> tuple[int, ...]:
    raw = names.raw_schema
    marts = names.marts_schema
    relations = [
        *(quote_fqn(names.database, raw, table.upper()) for table in TABLES),
        *(quote_fqn(names.database, marts, table) for table in (
            "DIM_CATEGORY",
            "DIM_CUSTOMER",
            "DIM_DATE",
            "DIM_GEOGRAPHY",
            "DIM_ORDER_CUSTOMER",
            "DIM_PRODUCT",
            "DIM_SELLER",
            "FCT_ORDER_ITEMS",
            "FCT_ORDER_PAYMENTS",
            "FCT_ORDER_REVIEWS",
            "FCT_ORDERS",
        )),
    ]
    counts = []
    for relation in relations:
        cursor.execute(f"SELECT COUNT(*) FROM {relation}")
        counts.append(int(cursor.fetchone()[0]))
    return tuple(counts)


def _production_synthetic_rows(cursor: object, names: SnowflakeNames) -> int:
    raw_orders = quote_fqn(names.database, names.raw_schema, "ORDERS")
    fact_orders = quote_fqn(names.database, names.marts_schema, "FCT_ORDERS")
    cursor.execute(
        f"SELECT (SELECT COUNT(*) FROM {raw_orders} WHERE order_id LIKE %s) + "
        f"(SELECT COUNT(*) FROM {fact_orders} WHERE order_id LIKE %s)",
        (f"{SYNTHETIC_PREFIX}%", f"{SYNTHETIC_PREFIX}%"),
    )
    return int(cursor.fetchone()[0])


def run_synthetic_failure_cycle(
    connection: object, names: SnowflakeNames, fixture_path: Path
) -> SyntheticCycleSummary:
    fixture = load_synthetic_fixture(fixture_path)
    orders = quote_fqn(names.database, names.audit_schema, "DQ_SYNTHETIC_ORDERS")
    customers = quote_fqn(names.database, names.audit_schema, "DQ_SYNTHETIC_CUSTOMERS")
    cursor = connection.cursor()
    fingerprint_before = _production_fingerprint(cursor, names)
    production_synthetic_before = _production_synthetic_rows(cursor, names)
    if production_synthetic_before:
        raise DataQualityError("Synthetic identifiers already exist in production data")
    try:
        cursor.execute(f"CREATE OR REPLACE TEMPORARY TABLE {customers} (customer_id VARCHAR)")
        cursor.execute(
            f"CREATE OR REPLACE TEMPORARY TABLE {orders} ("
            "fixture_id VARCHAR NOT NULL, order_id VARCHAR, customer_id VARCHAR, "
            "order_status VARCHAR, payment_value NUMBER(18,2), "
            "purchase_timestamp TIMESTAMP_NTZ, carrier_timestamp TIMESTAMP_NTZ, "
            "expected_rows NUMBER, actual_rows NUMBER, defect_type VARCHAR)"
        )
        cursor.executemany(
            f"INSERT INTO {customers} (customer_id) VALUES (%s)",
            [(value,) for value in fixture["customers"]],
        )
        insert_sql = (
            f"INSERT INTO {orders} (fixture_id,order_id,customer_id,order_status,"
            "payment_value,purchase_timestamp,carrier_timestamp,expected_rows,actual_rows,"
            "defect_type) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        cursor.executemany(
            insert_sql,
            [_fixture_row(row) for row in fixture["baseline_orders"]],
        )
        baseline = _run_synthetic_checks(cursor, orders, customers)
        if any(baseline.values()):
            raise DataQualityError(f"Synthetic baseline is not clean: {baseline}")

        cursor.executemany(
            insert_sql,
            [_fixture_row(row) for row in fixture["defect_orders"]],
        )
        injected = _run_synthetic_checks(cursor, orders, customers)
        expected = {check.name: check.expected_failures for check in SYNTHETIC_CHECKS}
        if injected != expected:
            raise DataQualityError(
                f"Synthetic defects were not detected as expected: {injected} != {expected}"
            )

        cursor.execute(f"DELETE FROM {orders} WHERE defect_type IS NOT NULL")
        recovered = _run_synthetic_checks(cursor, orders, customers)
        if any(recovered.values()):
            raise DataQualityError(f"Synthetic recovery did not return to clean state: {recovered}")
        cursor.execute(f"SELECT COUNT(*) FROM {orders}")
        temporary_rows_after_recovery = int(cursor.fetchone()[0])

        fingerprint_after = _production_fingerprint(cursor, names)
        production_synthetic_after = _production_synthetic_rows(cursor, names)
        if fingerprint_after != fingerprint_before or production_synthetic_after:
            raise DataQualityError("Production data changed during synthetic validation")
        return SyntheticCycleSummary(
            baseline_failures=baseline,
            injected_failures=injected,
            recovered_failures=recovered,
            production_fingerprint_unchanged=True,
            production_synthetic_rows_before=production_synthetic_before,
            production_synthetic_rows_after=production_synthetic_after,
            temporary_rows_after_recovery=temporary_rows_after_recovery,
        )
    finally:
        cursor.execute(f"DROP TABLE IF EXISTS {orders}")
        cursor.execute(f"DROP TABLE IF EXISTS {customers}")
        cursor.close()


def collect_reconciliation(connection: object, names: SnowflakeNames) -> Mapping[str, object]:
    cursor = connection.cursor()
    database = names.database
    audit = names.audit_schema
    raw = names.raw_schema
    staging = names.staging_schema
    marts = names.marts_schema
    try:
        batch_reconciliation = quote_fqn(database, audit, "BATCH_RECONCILIATION")
        cursor.execute(
            f"SELECT COUNT(*),SUM(expected_files),SUM(loaded_files),SUM(expected_rows),"
            f"SUM(loaded_rows),SUM(ABS(file_difference)),SUM(ABS(row_difference)),"
            f"COUNT_IF(UPPER(status) <> 'SUCCEEDED') FROM {batch_reconciliation}"
        )
        batch = cursor.fetchone()

        file_loads = quote_fqn(database, audit, "FILE_LOADS")
        cursor.execute(
            f"SELECT COUNT(*),COUNT(DISTINCT stage_path),SUM(expected_rows),SUM(loaded_rows),"
            f"COUNT_IF(UPPER(status) <> 'SUCCEEDED') FROM {file_loads}"
        )
        files = cursor.fetchone()

        raw_to_staging = {}
        for table in TABLES:
            raw_relation = quote_fqn(database, raw, table.upper())
            staging_relation = quote_fqn(database, staging, f"STG_{table.upper()}")
            cursor.execute(
                f"SELECT (SELECT COUNT(*) FROM {raw_relation}),"
                f"(SELECT COUNT(*) FROM {staging_relation})"
            )
            raw_rows, staging_rows = cursor.fetchone()
            raw_to_staging[table] = {
                "raw_rows": int(raw_rows),
                "staging_rows": int(staging_rows),
                "difference": int(raw_rows) - int(staging_rows),
            }

        detail_pairs = {
            "orders": "FCT_ORDERS",
            "order_items": "FCT_ORDER_ITEMS",
            "order_payments": "FCT_ORDER_PAYMENTS",
            "order_reviews": "FCT_ORDER_REVIEWS",
        }
        raw_to_facts = {}
        for table, fact in detail_pairs.items():
            raw_relation = quote_fqn(database, raw, table.upper())
            fact_relation = quote_fqn(database, marts, fact)
            cursor.execute(
                f"SELECT (SELECT COUNT(*) FROM {raw_relation}),"
                f"(SELECT COUNT(*) FROM {fact_relation})"
            )
            raw_rows, fact_rows = cursor.fetchone()
            raw_to_facts[table] = {
                "raw_rows": int(raw_rows),
                "fact_rows": int(fact_rows),
                "difference": int(raw_rows) - int(fact_rows),
            }

        raw_items = quote_fqn(database, raw, "ORDER_ITEMS")
        raw_payments = quote_fqn(database, raw, "ORDER_PAYMENTS")
        fact_items = quote_fqn(database, marts, "FCT_ORDER_ITEMS")
        fact_payments = quote_fqn(database, marts, "FCT_ORDER_PAYMENTS")
        fact_orders = quote_fqn(database, marts, "FCT_ORDERS")
        cursor.execute(
            f"SELECT "
            f"(SELECT ROUND(SUM(TRY_TO_DECIMAL(price,18,2)),2) FROM {raw_items}),"
            f"(SELECT ROUND(SUM(item_price),2) FROM {fact_items}),"
            f"(SELECT ROUND(SUM(item_merchandise_value),2) FROM {fact_orders}),"
            f"(SELECT ROUND(SUM(TRY_TO_DECIMAL(freight_value,18,2)),2) FROM {raw_items}),"
            f"(SELECT ROUND(SUM(freight_value),2) FROM {fact_items}),"
            f"(SELECT ROUND(SUM(freight_value),2) FROM {fact_orders}),"
            f"(SELECT ROUND(SUM(TRY_TO_DECIMAL(payment_value,18,2)),2) FROM {raw_payments}),"
            f"(SELECT ROUND(SUM(payment_value),2) FROM {fact_payments}),"
            f"(SELECT ROUND(SUM(payment_total_value),2) FROM {fact_orders})"
        )
        monetary_values = cursor.fetchone()

        raw_orders = quote_fqn(database, raw, "ORDERS")
        cursor.execute(
            f"SELECT COUNT_IF(TRY_TO_TIMESTAMP_NTZ(order_delivered_carrier_date) < "
            f"TRY_TO_TIMESTAMP_NTZ(order_purchase_timestamp)) FROM {raw_orders}"
        )
        carrier_anomalies = int(cursor.fetchone()[0])

        cursor.execute(
            f"SELECT (SELECT COUNT(*) FROM {raw_orders} WHERE order_id LIKE %s) + "
            f"(SELECT COUNT(*) FROM {fact_orders} WHERE order_id LIKE %s)",
            (f"{SYNTHETIC_PREFIX}%", f"{SYNTHETIC_PREFIX}%"),
        )
        production_synthetic_rows = int(cursor.fetchone()[0])

        freshness = {}
        for table in TABLES:
            raw_relation = quote_fqn(database, raw, table.upper())
            cursor.execute(
                f"SELECT MAX(_loaded_at),DATEDIFF('hour',MAX(_loaded_at),CURRENT_TIMESTAMP()) "
                f"FROM {raw_relation}"
            )
            loaded_at, age_hours = cursor.fetchone()
            age = int(age_hours)
            status = (
                "error"
                if age > FRESHNESS_ERROR_AFTER_HOURS
                else "warn" if age > FRESHNESS_WARN_AFTER_HOURS else "pass"
            )
            freshness[table] = {
                "max_loaded_at": loaded_at.isoformat(),
                "age_hours": age,
                "status": status,
            }

        return {
            "batches": {
                "count": int(batch[0]),
                "expected_files": int(batch[1]),
                "loaded_files": int(batch[2]),
                "expected_rows": int(batch[3]),
                "loaded_rows": int(batch[4]),
                "absolute_file_difference": int(batch[5]),
                "absolute_row_difference": int(batch[6]),
                "non_successful": int(batch[7]),
            },
            "files": {
                "audit_rows": int(files[0]),
                "distinct_files": int(files[1]),
                "expected_rows": int(files[2]),
                "loaded_rows": int(files[3]),
                "non_successful": int(files[4]),
            },
            "raw_to_staging": raw_to_staging,
            "raw_to_facts": raw_to_facts,
            "monetary": {
                "merchandise": [str(value) for value in monetary_values[0:3]],
                "freight": [str(value) for value in monetary_values[3:6]],
                "payments": [str(value) for value in monetary_values[6:9]],
            },
            "freshness": freshness,
            "genuine_source_anomalies": {
                "carrier_timestamp_before_purchase": carrier_anomalies,
            },
            "production_synthetic_rows": production_synthetic_rows,
        }
    finally:
        cursor.close()


def validate_reconciliation(summary: Mapping[str, object]) -> None:
    """Fail closed when a collected production reconciliation is not releasable."""
    batches = summary["batches"]
    files = summary["files"]
    failures = []
    if (
        batches["absolute_file_difference"]
        or batches["absolute_row_difference"]
        or batches["non_successful"]
    ):
        failures.append("batch reconciliation")
    if (
        files["audit_rows"] != files["distinct_files"]
        or files["expected_rows"] != files["loaded_rows"]
        or files["non_successful"]
    ):
        failures.append("file reconciliation")
    if any(item["difference"] for item in summary["raw_to_staging"].values()):
        failures.append("RAW-to-staging row preservation")
    if any(item["difference"] for item in summary["raw_to_facts"].values()):
        failures.append("RAW-to-fact row preservation")
    if any(len(set(values)) != 1 for values in summary["monetary"].values()):
        failures.append("monetary reconciliation")
    if any(item["status"] == "error" for item in summary["freshness"].values()):
        failures.append("freshness")
    if summary["production_synthetic_rows"]:
        failures.append("synthetic leakage")
    if failures:
        raise DataQualityError("Production quality validation failed: " + ", ".join(failures))


def _require_integration_opt_in() -> None:
    if os.environ.get("OLIST_RUN_SNOWFLAKE_INTEGRATION") != "1":
        raise DataQualityError(
            "Real data-quality execution requires OLIST_RUN_SNOWFLAKE_INTEGRATION=1"
        )


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("reconcile", "synthetic"))
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("tests/fixtures/data_quality_synthetic.json"),
    )
    args = parser.parse_args(argv)
    _require_integration_opt_in()
    settings = SnowflakeSettings.from_env()
    connection = connect_snowflake(settings)
    try:
        if args.action == "reconcile":
            result = collect_reconciliation(connection, settings.names)
            validate_reconciliation(result)
        else:
            result = asdict(
                run_synthetic_failure_cycle(connection, settings.names, args.fixture)
            )
    finally:
        connection.close()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
