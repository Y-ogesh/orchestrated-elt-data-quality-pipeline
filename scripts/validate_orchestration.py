"""Capture aggregate live reporting and production integrity evidence; no source records."""

import argparse
import json
from pathlib import Path

from olist_pipeline.dataset import TABLES
from olist_pipeline.orchestration import MARTS
from olist_pipeline.snowflake_sql import quote_fqn
from olist_pipeline.warehouse import SnowflakeSettings, connect_snowflake


def snapshot():
    settings = SnowflakeSettings.from_env()
    names = settings.names
    connection = connect_snowflake(settings)
    try:
        with connection.cursor() as cursor:

            def query(sql):
                cursor.execute(sql)
                return cursor.fetchall()

            pointer = quote_fqn(names.database, names.audit_schema, "REPORTING_CURRENT")
            version = query(f"SELECT version FROM {pointer} WHERE singleton=1")
            if len(version) != 1:
                raise RuntimeError("Expected exactly one published reporting version")
            reporting, production = {}, {}
            for model in MARTS:
                view = quote_fqn(names.database, names.marts_schema, "REPORT_" + model)
                reporting[model] = list(query(f"SELECT COUNT(*),HASH_AGG(*) FROM {view}")[0])
            for schema, table in [(names.raw_schema, t) for t in TABLES] + [
                (names.marts_schema, m) for m in MARTS
            ]:
                relation = quote_fqn(names.database, schema, table)
                production[schema + "." + table] = list(
                    query(f"SELECT COUNT(*),HASH_AGG(*) FROM {relation}")[0]
                )
            orders = quote_fqn(names.database, names.marts_schema, "REPORT_FCT_ORDERS")
            metrics = query(
                f"SELECT COUNT(*),SUM(item_merchandise_value),SUM(freight_value),"
                f"SUM(payment_total_value) FROM {orders}"
            )[0]
            history = quote_fqn(names.database, names.audit_schema, "REPORTING_VERSIONS")
            publications = query(f"SELECT version,run_id FROM {history} ORDER BY published_at")
            audit = quote_fqn(names.database, names.audit_schema, "PIPELINE_TASK_ATTEMPTS")
            attempts = query(
                f"SELECT run_id,task_name,attempt,state,duration_seconds FROM {audit} "
                "WHERE state <> 'running' ORDER BY started_at"
            )
            return {
                "version": version[0][0],
                "reporting": reporting,
                "production": production,
                "metrics": dict(
                    zip(("orders", "merchandise", "freight", "payments"), map(str, metrics))
                ),
                "publications": [list(row) for row in publications],
                "audit_attempts": attempts,
            }
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", choices=("before_failure", "after_failure", "after_recovery"))
    args = parser.parse_args()
    result = snapshot()
    root = Path("data/processed/orchestration/snapshots")
    root.mkdir(exist_ok=True)
    (root / (args.label + ".json")).write_text(json.dumps(result, indent=2, default=str))
    if args.label == "after_failure":
        before = json.loads((root / "before_failure.json").read_text())
        for key in ("version", "reporting", "production", "metrics", "publications"):
            if before[key] != result[key]:
                raise RuntimeError(f"Failed run changed {key}")
    elif args.label == "after_recovery":
        before = json.loads((root / "before_failure.json").read_text())
        for key in ("reporting", "production", "metrics"):
            if before[key] != result[key]:
                raise RuntimeError(f"Recovery changed business state: {key}")
        if before["version"] == result["version"]:
            raise RuntimeError("Recovery did not publish a new validated version")
    print(
        json.dumps(
            {
                "snapshot": args.label,
                "reporting_models": len(result["reporting"]),
                "metrics": result["metrics"],
                "publications": len(result["publications"]),
            }
        )
    )


if __name__ == "__main__":
    main()
