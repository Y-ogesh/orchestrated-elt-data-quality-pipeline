"""Deploy minimal Power BI operational views and validate Snowflake reporting metrics."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from .snowflake_sql import quote_identifier, render_template
from .warehouse import SnowflakeSettings, connect_snowflake

BUSINESS_VIEWS = (
    "REPORT_DIM_CATEGORY",
    "REPORT_DIM_CUSTOMER",
    "REPORT_DIM_DATE",
    "REPORT_DIM_GEOGRAPHY",
    "REPORT_DIM_ORDER_CUSTOMER",
    "REPORT_DIM_PRODUCT",
    "REPORT_DIM_SELLER",
    "REPORT_FCT_ORDER_ITEMS",
    "REPORT_FCT_ORDER_PAYMENTS",
    "REPORT_FCT_ORDER_REVIEWS",
    "REPORT_FCT_ORDERS",
)
OPERATIONAL_VIEWS = ("PBI_SOURCE_FRESHNESS", "PBI_PIPELINE_RUNS", "PBI_PIPELINE_HEALTH")


def render_power_bi_sql(path, names):
    names.validate()
    return render_template(
        path.read_text(encoding="utf-8"),
        {
            "DATABASE": quote_identifier(names.database),
            "RAW_SCHEMA": quote_identifier(names.raw_schema),
            "MARTS_SCHEMA": quote_identifier(names.marts_schema),
            "AUDIT_SCHEMA": quote_identifier(names.audit_schema),
        },
    )


def deploy_views(connection, settings, sql_path):
    sql = render_power_bi_sql(sql_path, settings.names)
    cursors = connection.execute_string(sql)
    for cursor in cursors:
        cursor.close()
    connection.commit()


def query_one(cursor, sql):
    cursor.execute(sql)
    columns = [item[0].lower() for item in cursor.description]
    return dict(zip(columns, cursor.fetchone()))


def collect_validation(connection, settings):
    names = settings.names
    marts = f'"{names.database.upper()}"."{names.marts_schema.upper()}"'
    audit = f'"{names.database.upper()}"."{names.audit_schema.upper()}"'
    cursor = connection.cursor()
    try:
        execution = query_one(cursor, "SELECT CURRENT_TIMESTAMP() AS validated_at")
        kpis = query_one(
            cursor,
            f"""SELECT
                COUNT(DISTINCT order_id) AS total_orders,
                ROUND(SUM(payment_total_value),2) AS total_payment_value,
                ROUND(SUM(payment_total_value)/COUNT(DISTINCT order_id),2)
                    AS average_order_value,
                ROUND(SUM(item_merchandise_value),2) AS merchandise_value,
                ROUND(SUM(freight_value),2) AS freight_value,
                COUNT(DISTINCT customer_key) AS customer_count,
                COUNT_IF(order_status='delivered') AS delivered_orders,
                COUNT_IF(order_status='delivered' AND is_late_delivery) AS late_deliveries,
                COUNT_IF(order_status='delivered' AND NOT is_late_delivery)
                    AS on_time_delivered_orders,
                COUNT_IF(order_status='delivered' AND is_late_delivery IS NULL)
                    AS unknown_timeliness_delivered_orders,
                ROUND(COUNT_IF(order_status='delivered')/COUNT(*)::FLOAT,6)
                    AS delivery_success_rate,
                ROUND(COUNT_IF(order_status='delivered' AND NOT is_late_delivery)
                    /NULLIF(COUNT_IF(order_status='delivered'),0)::FLOAT,6)
                    AS on_time_delivery_rate,
                ROUND(COUNT_IF(order_status='delivered' AND is_late_delivery)
                    /NULLIF(COUNT_IF(order_status='delivered'),0)::FLOAT,6)
                    AS late_delivery_rate
            FROM {marts}.REPORT_FCT_ORDERS""",
        )
        inventory = query_one(
            cursor,
            f"""SELECT COUNT(DISTINCT product_key) AS product_count,
                       COUNT(DISTINCT seller_key) AS seller_count
                FROM {marts}.REPORT_FCT_ORDER_ITEMS""",
        )
        cursor.execute(
            f"""SELECT d.year_number,d.month_number,COUNT(DISTINCT o.order_id),
                        ROUND(SUM(o.payment_total_value),2)
                FROM {marts}.REPORT_FCT_ORDERS o
                INNER JOIN {marts}.REPORT_DIM_DATE d ON o.purchase_date_key=d.date_key
                GROUP BY d.year_number,d.month_number ORDER BY 1,2"""
        )
        monthly = [
            {
                "year": int(year),
                "month": int(month),
                "total_orders": int(orders),
                "total_payment_value": str(payment),
            }
            for year, month, orders, payment in cursor.fetchall()
        ]
        cursor.execute(
            f"""SELECT order_status,COUNT(*),ROUND(SUM(payment_total_value),2)
                FROM {marts}.REPORT_FCT_ORDERS GROUP BY order_status ORDER BY order_status"""
        )
        statuses = {
            status: {"total_orders": int(count), "total_payment_value": str(payment)}
            for status, count, payment in cursor.fetchall()
        }
        health = query_one(cursor, f"SELECT * FROM {audit}.PBI_PIPELINE_HEALTH")
        cursor.execute(f"SELECT * FROM {audit}.PBI_SOURCE_FRESHNESS ORDER BY source_name")
        freshness_columns = [item[0].lower() for item in cursor.description]
        freshness = [dict(zip(freshness_columns, row)) for row in cursor.fetchall()]
        cursor.execute(
            f"""SELECT table_schema,table_name FROM
                \"{names.database.upper()}\".INFORMATION_SCHEMA.VIEWS
                WHERE (table_schema=%s AND table_name IN
                    ({','.join(['%s'] * len(BUSINESS_VIEWS))}))
                   OR (table_schema=%s AND table_name IN
                    ({','.join(['%s'] * len(OPERATIONAL_VIEWS))}))""",
            (
                names.marts_schema.upper(),
                *BUSINESS_VIEWS,
                names.audit_schema.upper(),
                *OPERATIONAL_VIEWS,
            ),
        )
        views = sorted(f"{schema}.{view}" for schema, view in cursor.fetchall())
        monetary = query_one(
            cursor,
            f"""SELECT
                (SELECT ROUND(SUM(item_price),2) FROM {marts}.REPORT_FCT_ORDER_ITEMS)
                    AS item_detail_merchandise,
                (SELECT ROUND(SUM(item_merchandise_value),2)
                    FROM {marts}.REPORT_FCT_ORDERS) AS order_merchandise,
                (SELECT ROUND(SUM(freight_value),2) FROM {marts}.REPORT_FCT_ORDER_ITEMS)
                    AS item_detail_freight,
                (SELECT ROUND(SUM(freight_value),2) FROM {marts}.REPORT_FCT_ORDERS)
                    AS order_freight,
                (SELECT ROUND(SUM(payment_value),2) FROM {marts}.REPORT_FCT_ORDER_PAYMENTS)
                    AS payment_detail,
                (SELECT ROUND(SUM(payment_total_value),2) FROM {marts}.REPORT_FCT_ORDERS)
                    AS order_payment""",
        )
        orphan_counts = query_one(
            cursor,
            f"""SELECT
                (SELECT COUNT(*) FROM {marts}.REPORT_FCT_ORDERS f LEFT JOIN
                    {marts}.REPORT_DIM_DATE d ON f.purchase_date_key=d.date_key
                    WHERE d.date_key IS NULL) AS order_date_orphans,
                (SELECT COUNT(*) FROM {marts}.REPORT_FCT_ORDER_ITEMS f LEFT JOIN
                    {marts}.REPORT_DIM_PRODUCT d ON f.product_key=d.product_key
                    WHERE d.product_key IS NULL) AS item_product_orphans,
                (SELECT COUNT(*) FROM {marts}.REPORT_FCT_ORDER_ITEMS f LEFT JOIN
                    {marts}.REPORT_DIM_SELLER d ON f.seller_key=d.seller_key
                    WHERE d.seller_key IS NULL) AS item_seller_orphans""",
        )
    finally:
        cursor.close()

    expected_views = sorted(
        [f"{names.marts_schema.upper()}.{name}" for name in BUSINESS_VIEWS]
        + [f"{names.audit_schema.upper()}.{name}" for name in OPERATIONAL_VIEWS]
    )
    if views != expected_views:
        raise RuntimeError("Power BI reporting-view inventory does not match the contract")
    if not (
        monetary["item_detail_merchandise"] == monetary["order_merchandise"]
        and monetary["item_detail_freight"] == monetary["order_freight"]
        and monetary["payment_detail"] == monetary["order_payment"]
    ):
        raise RuntimeError("Power BI monetary totals do not reconcile across safe grains")
    if any(orphan_counts.values()):
        raise RuntimeError("Power BI star-schema relationships contain orphan keys")
    if kpis["total_orders"] != sum(row["total_orders"] for row in monthly):
        raise RuntimeError("Monthly order totals do not reconcile")
    monthly_payment_total = sum(
        (Decimal(row["total_payment_value"]) for row in monthly), Decimal("0")
    )
    if Decimal(str(kpis["total_payment_value"])) != monthly_payment_total:
        raise RuntimeError("Monthly payment totals do not reconcile")
    return {
        "status": "backend_validated_power_bi_ui_not_built",
        "backend_validated_at": execution["validated_at"].isoformat(),
        "latest_publication_validated_at": health["latest_validated_at"].isoformat(),
        "kpis": {key: str(value) for key, value in {**kpis, **inventory}.items()},
        "order_status": statuses,
        "monthly": monthly,
        "pipeline_health": {key: str(value) for key, value in health.items()},
        "source_freshness": [
            {
                key: value.isoformat() if hasattr(value, "isoformat") else value
                for key, value in row.items()
            }
            for row in freshness
        ],
        "monetary_reconciliation": {key: str(value) for key, value in monetary.items()},
        "relationship_orphans": orphan_counts,
        "reporting_views": views,
        "power_bi_ui_validation": "not_performed",
        "screenshots": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sql",
        type=Path,
        default=Path("sql/power_bi/001_operational_reporting_views.sql"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/power_bi_backend_validation.json"),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    settings = SnowflakeSettings.from_env()
    connection = connect_snowflake(settings)
    try:
        if args.apply:
            deploy_views(connection, settings, args.sql)
        result = collect_validation(connection, settings)
    finally:
        connection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps({"status": result["status"], "kpis": result["kpis"]}))


if __name__ == "__main__":
    main()
