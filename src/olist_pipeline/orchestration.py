"""Stable Airflow task boundaries around the validated pipeline implementations.

No Airflow dependency here. Run-specific dbt candidates never replace production
marts. Immutable reporting versions become visible through one transactional pointer.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .data_quality import DataQualityError, collect_reconciliation, validate_reconciliation
from .ingestion import build_batches, load_manifest, upload_batches, validate_built_batches
from .monitoring import ObservedFailure, observation, quarantine_probe
from .snowflake_sql import quote_fqn
from .storage import S3ObjectStore
from .warehouse import (
    SnowflakeBackend,
    SnowflakeSettings,
    WarehouseLoader,
    connect_snowflake,
    validate_remote_warehouse,
)

DAG_ID = "olist_elt_pipeline"
TASKS = (
    "prepare_source_batch",
    "ingest_to_s3",
    "load_snowflake_raw",
    "reconcile_raw",
    "run_dbt_transformations",
    "validate_data_quality",
    "publish_reporting",
    "record_pipeline_audit",
)
MARTS = (
    "dim_category",
    "dim_customer",
    "dim_date",
    "dim_geography",
    "dim_order_customer",
    "dim_product",
    "dim_seller",
    "fct_order_items",
    "fct_order_payments",
    "fct_order_reviews",
    "fct_orders",
)


def run_version(run_id):
    return "M7_" + hashlib.sha256(run_id.encode()).hexdigest()[:12].upper() + "_"


def require_gates(states):
    missing = [t for t in TASKS[:6] if states.get(t, {}).get("state") != "success"]
    if missing:
        raise RuntimeError("Required publication gates did not succeed: " + ",".join(missing))


class Workflow:
    def __init__(self, run_id, task, attempt=1, mode="normal"):
        if mode not in (
            "normal",
            "quality_failure",
            "transient_failure",
            "rejected_source",
            "recovered_source",
            "reconciliation_retry",
            "quality_retry",
            "publication_retry",
        ):
            raise ValueError("Unknown validation mode")
        if mode != "normal" and os.getenv("OLIST_ENABLE_ORCHESTRATION_PROBES") != "1":
            raise RuntimeError("Failure probes require explicit environment opt-in")
        if os.getenv("OLIST_RUN_SNOWFLAKE_INTEGRATION") != "1":
            raise RuntimeError("Cloud execution requires explicit opt-in")
        self.run_id, self.task, self.attempt, self.mode = run_id, task, attempt, mode
        self.version = run_version(run_id)
        self.root = Path("data/processed/orchestration") / self.version
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = SnowflakeSettings.from_env()
        self.names = self.settings.names
        self.connection = connect_snowflake(self.settings)
        self.batch_root = Path("data/processed/ingestion_batches")

    def sql(self, sql, params=()):
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def relation(self, schema, name):
        return quote_fqn(self.names.database, schema, name)

    def state(self, task):
        return json.loads((self.root / f"{task}.result.json").read_text())

    def batches(self):
        return [p.parent for p in sorted(self.batch_root.glob("*/manifest.json"))]

    def audit_table(self):
        table = self.relation(self.names.audit_schema, "PIPELINE_TASK_ATTEMPTS")
        self.sql(
            f"CREATE TABLE IF NOT EXISTS {table} ("
            "dag_id VARCHAR,run_id VARCHAR,version VARCHAR,task_name VARCHAR,"
            "attempt NUMBER,state VARCHAR,started_at TIMESTAMP_TZ,"
            "ended_at TIMESTAMP_TZ,duration_seconds FLOAT,details VARIANT)"
        )
        return table

    def audit(self, record):
        table = self.audit_table()
        self.sql(
            f"INSERT INTO {table} SELECT %s,%s,%s,%s,%s,%s,"
            "TO_TIMESTAMP_TZ(%s),TO_TIMESTAMP_TZ(%s),%s,PARSE_JSON(%s)",
            (
                DAG_ID,
                self.run_id,
                self.version,
                self.task,
                self.attempt,
                record["state"],
                record["started_at"],
                record.get("ended_at"),
                record.get("seconds"),
                json.dumps(record.get("result", {}), default=str),
            ),
        )
        self.connection.commit()

    def prepare_source_batch(self):
        paths = self.batches()
        if not paths:
            paths = build_batches(Path("data/raw"), self.batch_root)
        inventory = asdict(validate_built_batches(paths))
        inventory["batch_ids"] = [load_manifest(p).batch_id for p in paths]
        return inventory

    def ingest_to_s3(self):
        store = S3ObjectStore(
            self.settings.s3_bucket,
            region=os.getenv("AWS_REGION"),
            profile=os.getenv("AWS_PROFILE") or None,
        )
        results = upload_batches(self.batches(), store, prefix=self.settings.s3_raw_prefix)
        return {
            "batches": len(results),
            "uploaded": sum(r.uploaded for r in results),
            "skipped": sum(r.skipped for r in results),
            "objects": sum(r.object_count for r in results),
        }

    def load_snowflake_raw(self):
        probe = None
        if self.mode in ("rejected_source", "recovered_source"):
            probe = quarantine_probe(
                self.connection, self.names, corrected=self.mode == "recovered_source"
            )
            if probe["rejected_rows"]:
                raise ObservedFailure(
                    "snowflake_load", "SYNTHETIC_REJECTED_SOURCE", {"accounting": probe}
                )
        result = asdict(
            WarehouseLoader(SnowflakeBackend(self.connection, self.names)).load(self.batches())
        )
        total = sum(item.row_count for p in self.batches() for item in load_manifest(p).files)
        result["accounting"] = {
            "scope": "production_raw",
            "source_rows": total,
            "accepted_rows": total,
            "rejected_rows": 0,
            "inserted_rows": result["rows_loaded"],
            "updated_rows": 0,
            "skipped_rows": total - result["rows_loaded"],
        }
        if probe:
            result["synthetic_recovery"] = probe
        return result

    def reconcile_raw(self):
        result = validate_remote_warehouse(self.connection, self.names, self.batches())
        if self.mode == "reconciliation_retry" and self.attempt == 1:
            # Only the isolated expected count is wrong; never mutate RAW or manifests.
            raise ObservedFailure(
                "reconciliation",
                "SYNTHETIC_EXPECTED_COUNT_MISMATCH",
                {
                    "actual_rows": result["rows"],
                    "expected_rows": result["rows"] + 1,
                    "row_difference": 1,
                    "original_validation": result,
                },
            )
        return result

    def dbt(self, label, args):
        profiles = self.root / "profiles"
        profiles.mkdir(exist_ok=True)
        (profiles / "profiles.yml").write_text(Path("dbt/profiles.yml.example").read_text())
        target = self.root / label
        env = dict(
            os.environ,
            OLIST_MODEL_PREFIX=self.version,
            OLIST_RELATION_PREFIX="",
            DBT_PROFILES_DIR=str(profiles.resolve()),
            DBT_LOG_PATH=str((self.root / "dbt_logs").resolve()),
            DBT_QUERY_TAG=f"olist_airflow_{self.version}{label}",
        )
        command = [
            str(Path(sys.executable).with_name("dbt")),
            *args,
            "--project-dir",
            "dbt",
            "--target",
            "prod",
            "--target-path",
            str(target.resolve()),
        ]
        started = time.monotonic()
        with (self.root / f"{label}.log").open("w") as log:
            result = subprocess.run(
                command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=900, check=False
            )
        artifact = target / ("sources.json" if args[0] == "source" else "run_results.json")
        payload = json.loads(artifact.read_text()) if artifact.exists() else {}
        outcomes = dict(Counter(r["status"] for r in payload.get("results", [])))
        summary = {
            "exit_code": result.returncode,
            "outcomes": outcomes,
            "seconds": round(time.monotonic() - started, 3),
        }
        if result.returncode or not outcomes or set(outcomes) - {"success", "pass", "warn"}:
            category = {
                "build": "transformation",
                "test": "data_quality",
                "freshness": "freshness",
            }[label]
            raise ObservedFailure(category, "DBT_VALIDATION_FAILED", summary)
        return summary

    def run_dbt_transformations(self):
        return self.dbt("build", ["build"])

    def validate_data_quality(self):
        result = {
            "tests": self.dbt("test", ["test"]),
            "freshness": self.dbt("freshness", ["source", "freshness"]),
        }
        reconciliation = collect_reconciliation(
            self.connection, self.names, model_prefix=self.version
        )
        result["reconciliation"] = reconciliation
        try:
            validate_reconciliation(reconciliation)
        except DataQualityError:
            raise ObservedFailure("reconciliation", "RECONCILIATION_FAILED", result) from None
        if self.mode == "quality_retry":
            # Real SQL evaluates a synthetic one-row candidate; not a production source defect.
            invalid = self.attempt == 1
            violations = int(
                self.sql(
                    "SELECT COUNT(*) FROM (SELECT %s::NUMBER AS amount) WHERE amount < 0",
                    (-1 if invalid else 1,),
                )[0][0]
            )
            result["synthetic_quality"] = {"checked_rows": 1, "violations": violations}
            if violations:
                raise ObservedFailure("data_quality", "SYNTHETIC_NEGATIVE_CANDIDATE", result)
        if self.mode == "quality_failure":
            raise ObservedFailure("data_quality", "CONTROLLED_QUALITY_GATE_FAILURE", result)
        if self.mode == "transient_failure" and self.attempt == 1:
            raise ObservedFailure("data_quality", "CONTROLLED_TRANSIENT_GATE_FAILURE", result)
        return result

    def publication_state(self):
        pointer = self.relation(self.names.audit_schema, "REPORTING_CURRENT")
        return self.sql(f"SELECT version FROM {pointer} WHERE singleton=1")

    def publish_reporting(self):
        # Every gate must be successful even if invoked outside the DAG.
        states = {t: self.state(t) for t in TASKS[:6]}
        require_gates(states)
        pointer = self.relation(self.names.audit_schema, "REPORTING_CURRENT")
        history = self.relation(self.names.audit_schema, "REPORTING_VERSIONS")
        self.sql(
            f"CREATE TABLE IF NOT EXISTS {pointer} "
            "(singleton NUMBER,version VARCHAR,published_at TIMESTAMP_TZ)"
        )
        self.sql(
            f"CREATE TABLE IF NOT EXISTS {history} "
            "(version VARCHAR,run_id VARCHAR,published_at TIMESTAMP_TZ,details VARIANT)"
        )
        # DDL is outside the publication transaction. Existing views are never replaced.
        for model in MARTS:
            candidate = self.relation(self.names.marts_schema, self.version + model)
            store = self.relation(self.names.marts_schema, "REPORT_STORE_" + model)
            view = self.relation(self.names.marts_schema, "REPORT_" + model)
            self.sql(
                f"CREATE TABLE IF NOT EXISTS {store} AS SELECT "
                f"CAST(NULL AS VARCHAR) AS _report_version,c.* FROM {candidate} c WHERE 1=0"
            )
            self.sql(
                f"CREATE VIEW IF NOT EXISTS {view} AS SELECT s.* EXCLUDE (_report_version) "
                f"FROM {store} s JOIN {pointer} p ON p.singleton=1 "
                "AND s._report_version=p.version"
            )
        current = self.publication_state()
        if len(current) > 1:
            raise RuntimeError("Publication pointer is not a singleton")
        if current == [(self.version,)]:
            return {"published": True, "version": self.version, "rerun": "skipped"}
        if self.sql(f"SELECT version FROM {history} WHERE version=%s", (self.version,)):
            raise RuntimeError(
                "Previously published version requires explicit rollback, not recopy"
            )
        metrics = states["validate_data_quality"]["result"]["reconciliation"]["monetary"]
        # All 11 copies, the single pointer and publication history commit together.
        self.sql("BEGIN")
        try:
            for index, model in enumerate(MARTS):
                candidate = self.relation(self.names.marts_schema, self.version + model)
                store = self.relation(self.names.marts_schema, "REPORT_STORE_" + model)
                self.sql(f"INSERT INTO {store} SELECT %s,c.* FROM {candidate} c", (self.version,))
                if self.mode == "publication_retry" and self.attempt == 1 and index == 0:
                    staged = int(
                        self.sql(
                            f"SELECT COUNT(*) FROM {store} WHERE _report_version=%s",
                            (self.version,),
                        )[0][0]
                    )
                    raise ObservedFailure(
                        "publication",
                        "SYNTHETIC_PUBLICATION_INTERRUPTION",
                        {"uncommitted_rows_before_rollback": staged},
                    )
            self.sql(f"DELETE FROM {pointer} WHERE singleton=1")
            self.sql(f"INSERT INTO {pointer} VALUES (1,%s,CURRENT_TIMESTAMP())", (self.version,))
            self.sql(
                f"INSERT INTO {history} SELECT %s,%s,CURRENT_TIMESTAMP(),PARSE_JSON(%s)",
                (self.version, self.run_id, json.dumps(metrics)),
            )
            self.connection.commit()
        except BaseException as exc:
            self.connection.rollback()
            if (
                isinstance(exc, ObservedFailure)
                and exc.code == "SYNTHETIC_PUBLICATION_INTERRUPTION"
            ):
                remaining = sum(
                    int(
                        self.sql(
                            "SELECT COUNT(*) FROM "
                            f"{self.relation(self.names.marts_schema, 'REPORT_STORE_' + m)} "
                            "WHERE _report_version=%s",
                            (self.version,),
                        )[0][0]
                    )
                    for m in MARTS
                )
                preserved = self.publication_state() == current
                if remaining or not preserved:
                    raise RuntimeError("Publication rollback invariant failed") from None
                exc.metrics.update(
                    {
                        "rolled_back_candidate_rows_remaining": remaining,
                        "previous_version": current[0][0],
                        "pointer_preserved": preserved,
                        "published": False,
                    }
                )
            raise
        return {
            "published": True,
            "version": self.version,
            "previous_version": current[0][0] if current else None,
            "models": len(MARTS),
            "monetary": metrics,
        }

    def record_pipeline_audit(self):
        records = {}
        for task in TASKS[:-1]:
            path = self.root / f"{task}.result.json"
            records[task] = (
                json.loads(path.read_text()) if path.exists() else {"state": "not_executed"}
            )
        successful = all(r["state"] == "success" for r in records.values())
        result = {"pipeline_state": "success" if successful else "failed", "tasks": records}
        (self.root / "pipeline_audit.json").write_text(json.dumps(result, indent=2, default=str))
        if not successful:
            # all_done leaf must fail, otherwise Airflow can mask the upstream failure.
            raise RuntimeError("PIPELINE_FAILED_PUBLICATION_NOT_COMPLETED")
        return {"pipeline_state": "success", "tasks": len(records)}

    def execute(self):
        record = {"state": "running", "started_at": datetime.now(timezone.utc).isoformat()}
        start = time.monotonic()
        self.audit(record)
        try:
            record["result"] = getattr(self, self.task)()
            record["result"]["_monitoring"] = observation(
                self.task, record["result"], mode=self.mode, attempt=self.attempt
            )
            record["state"] = "success"
        except BaseException as exc:
            record["state"] = "failed"
            # Do not persist connector errors or configuration values in shared logs.
            code = (
                exc.code
                if isinstance(exc, ObservedFailure)
                else (
                    str(exc)
                    if str(exc).startswith(("CONTROLLED_", "PIPELINE_FAILED_"))
                    else type(exc).__name__
                )
            )
            record["result"] = dict(exc.metrics) if isinstance(exc, ObservedFailure) else {}
            record["result"].update(failure_code=code)
            record["result"]["_monitoring"] = observation(
                self.task, record["result"], exc, self.mode, self.attempt
            )
            raise RuntimeError(code) from None
        finally:
            record.update(
                ended_at=datetime.now(timezone.utc).isoformat(),
                seconds=round(time.monotonic() - start, 3),
            )
            path = self.root / f"{self.task}.result.json"
            path.write_text(json.dumps(record, indent=2, default=str))
            self.audit(record)
            self.connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=TASKS)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--mode", default="normal")
    args = parser.parse_args()
    try:
        Workflow(args.run_id, args.task, args.attempt, args.mode).execute()
    except Exception as exc:
        code = (
            str(exc)
            if str(exc).startswith(("CONTROLLED_", "PIPELINE_FAILED_"))
            else type(exc).__name__
        )
        print(json.dumps({"task": args.task, "state": "failed", "failure_code": code}))
        return 1
    print(json.dumps({"task": args.task, "state": "success"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
