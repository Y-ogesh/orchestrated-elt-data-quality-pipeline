"""Operational observations derived from existing audit events; no secret payloads."""

import argparse
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .snowflake_sql import quote_fqn
from .warehouse import SnowflakeSettings, connect_snowflake

CATEGORIES = {
    "ingestion",
    "s3_object",
    "snowflake_load",
    "reconciliation",
    "transformation",
    "data_quality",
    "freshness",
    "publication",
    "timeout_interruption",
    "infrastructure",
}
STAGES = {
    "prepare_source_batch": "ingestion",
    "ingest_to_s3": "s3_object",
    "load_snowflake_raw": "snowflake_load",
    "reconcile_raw": "reconciliation",
    "run_dbt_transformations": "transformation",
    "validate_data_quality": "data_quality",
    "publish_reporting": "publication",
    "record_pipeline_audit": "infrastructure",
}


class ObservedFailure(RuntimeError):
    def __init__(self, category, code, metrics=None):
        if category not in CATEGORIES or not re.fullmatch(r"[A-Z_]{1,100}", code):
            raise ValueError("Invalid failure classification")
        self.category, self.code, self.metrics = category, code, metrics or {}
        super().__init__(code)


def classify(task, exc):
    if isinstance(exc, ObservedFailure):
        return exc.category
    if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired, KeyboardInterrupt)):
        return "timeout_interruption"
    if isinstance(exc, (ConnectionError, OSError)):
        return "infrastructure"
    return STAGES.get(task, "infrastructure")


def observation(task, result, exc=None, mode="normal", attempt=1):
    outcomes = result.get("outcomes", result.get("tests", {}).get("outcomes", {}))
    failures = sum(outcomes.get(k, 0) for k in ("fail", "error", "runtime error"))
    failures += result.get("synthetic_quality", {}).get("violations", 0)
    counts = result.get("accounting", {})
    category = classify(task, exc) if exc else None
    return {
        "schema_version": 1,
        "stage": STAGES[task],
        "execution_origin": "airflow",
        "synthetic": mode != "normal",
        "scenario": mode,
        "failure_category": category,
        "failure_role": "downstream_summary" if task == "record_pipeline_audit" else "root",
        "failure_reason": (exc.code if isinstance(exc, ObservedFailure) else type(exc).__name__)
        if exc
        else None,
        "source_rows": counts.get("source_rows"),
        "accepted_rows": counts.get("accepted_rows"),
        "rejected_rows": counts.get("rejected_rows"),
        "inserted_rows": result.get("rows_loaded", counts.get("inserted_rows")),
        "updated_rows": counts.get("updated_rows"),
        "skipped_rows": counts.get("skipped_rows"),
        "accounting_scope": counts.get("scope"),
        "test_failures": failures,
        "warning_count": outcomes.get("warn", 0),
        "freshness_status": "failed"
        if category == "freshness"
        else "pass"
        if result.get("freshness", {}).get("outcomes") == {"pass": 9}
        else "unknown",
        "reconciliation_status": "failed"
        if category == "reconciliation"
        else "pass"
        if "reconciliation" in result or (task == "reconcile_raw" and not exc)
        else "unknown",
        "publication_status": "published" if result.get("published") else "not_published",
        "warehouse_run_id": result.get("run_id"),
        "recovery_status": "pending"
        if exc
        else "retry_succeeded"
        if attempt > 1
        else "source_corrected"
        if "synthetic_recovery" in result
        else "not_applicable",
    }


def quarantine_probe(connection, names, *, corrected):
    """Real SQL classification in session TEMP tables; fail-closed whole-batch policy.

    Three fabricated rows, never Olist rows. Diagnostic multiplicity is separate
    from distinct rejected source lines. Temp tables are explicitly dropped.
    """

    def prefix(name):
        return quote_fqn(names.database, names.audit_schema, "M8_PROBE_" + name)

    source, quarantine, target = map(prefix, ("SOURCE", "QUARANTINE", "ACCEPTED"))
    cursor = connection.cursor()
    created = []
    try:
        for table, columns in (
            (source, "source_line NUMBER,record_key VARCHAR,amount NUMBER(18,2)"),
            (quarantine, "source_file VARCHAR,source_line NUMBER,reason VARCHAR,status VARCHAR"),
            (target, "source_line NUMBER,record_key VARCHAR,amount NUMBER(18,2)"),
        ):
            cursor.execute(f"CREATE TEMPORARY TABLE {table} ({columns})")
            created.append(table)
        cursor.executemany(
            f"INSERT INTO {source} VALUES (%s,%s,%s)",
            [
                (1, "synthetic_one", 10),
                (2, "synthetic_two" if corrected else None, 20 if corrected else -20),
                (3, "synthetic_three", 30 if corrected else -30),
            ],
        )
        cursor.execute(
            f"INSERT INTO {quarantine} SELECT 'synthetic://m8/records',source_line,"
            f"'NULL_KEY','open' FROM {source} WHERE record_key IS NULL UNION ALL "
            f"SELECT 'synthetic://m8/records',source_line,'NEGATIVE_AMOUNT','open' "
            f"FROM {source} WHERE amount < 0"
        )
        cursor.execute(f"SELECT COUNT(*),COUNT(DISTINCT source_line) FROM {quarantine}")
        diagnostics, rejected = map(int, cursor.fetchone())
        cursor.execute(f"SELECT COUNT(*) FROM {source}")
        total = int(cursor.fetchone()[0])
        cursor.execute(
            f"SELECT COUNT(*) FROM {source} WHERE record_key IS NOT NULL AND amount >= 0"
        )
        accepted = int(cursor.fetchone()[0])
        cursor.execute(
            f"SELECT source_file,source_line,reason,status FROM {quarantine} "
            "ORDER BY source_line,reason"
        )
        reasons = [list(row) for row in cursor.fetchall()]
        inserted = rerun_inserted = 0
        if not rejected:
            merge = (
                f"MERGE INTO {target} t USING {source} s ON t.source_line=s.source_line "
                "WHEN NOT MATCHED THEN INSERT (source_line,record_key,amount) "
                "VALUES (s.source_line,s.record_key,s.amount)"
            )
            cursor.execute(merge)
            inserted = int(cursor.fetchone()[0])
            cursor.execute(merge)
            rerun_inserted = int(cursor.fetchone()[0])
        cursor.execute(f"SELECT COUNT(*),COUNT(DISTINCT source_line) FROM {target}")
        accepted_target, distinct_target = map(int, cursor.fetchone())
        if total != accepted + rejected or accepted_target != distinct_target:
            raise RuntimeError("Synthetic accounting failed")
        if accepted_target != (0 if rejected else total) or rerun_inserted:
            raise RuntimeError("Synthetic publication policy or recovery failed")
        return {
            "scope": "isolated_synthetic",
            "source_file": "synthetic://m8/records",
            "source_rows": total,
            "accepted_rows": accepted,
            "rejected_rows": rejected,
            "diagnostics": diagnostics,
            "rejected_provenance": reasons,
            "inserted_rows": inserted,
            "updated_rows": 0,
            "rerun_inserted_rows": rerun_inserted,
            "target_rows": accepted_target,
            "held_accepted_rows": total - rejected if rejected else 0,
            "open_quarantine_rows": rejected,
            "policy": "hold_entire_batch_on_any_rejection",
            "quarantine_resolution": "corrected" if corrected else "blocked",
        }
    finally:
        connection.rollback()
        for table in reversed(created):
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        cursor.close()


def collect_monitoring(connection, names):
    """Read existing events and derive run summaries without another audit ledger."""

    def query(sql, params=()):
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def rel(name):
        return quote_fqn(names.database, names.audit_schema, name)

    events = query(
        f"SELECT run_id,task_name,attempt,state,started_at,ended_at,"
        f"duration_seconds,details FROM {rel('PIPELINE_TASK_ATTEMPTS')} "
        "WHERE state <> 'running' ORDER BY started_at"
    )
    runs = {}
    attempts = []
    for run_id, task, attempt, state, start, end, duration, raw in events:
        detail = json.loads(raw) if isinstance(raw, str) else raw
        obs = detail.get("_monitoring", {})
        code = detail.get("failure_code", "")
        category = obs.get("failure_category")
        if state == "failed" and not category:
            category = STAGES.get(task, "infrastructure")
        item = {
            "run_id": run_id,
            "task": task,
            "attempt": int(attempt),
            "state": state,
            "started_at": start.isoformat(),
            "ended_at": end.isoformat() if end else None,
            "seconds": float(duration) if duration is not None else None,
            "failure_category": category,
            "observation": obs,
            "synthetic": obs.get(
                "synthetic", code.startswith("CONTROLLED_") or run_id.startswith("m7_")
            ),
            "classification_origin": "recorded" if obs else "derived_from_legacy_task",
            "result": {k: v for k, v in detail.items() if k != "_monitoring"},
        }
        attempts.append(item)
        runs.setdefault(run_id, []).append(item)
    publications = query(
        f"SELECT version,run_id,published_at FROM {rel('REPORTING_VERSIONS')} ORDER BY published_at"
    )
    published_runs = {row[1] for row in publications}
    current = query(f"SELECT version FROM {rel('REPORTING_CURRENT')} WHERE singleton=1")
    if len(current) != 1:
        raise RuntimeError("Reporting pointer is not a singleton")
    inflight = query(
        f"SELECT r.run_id,r.task_name,r.attempt,r.started_at,"
        "DATEDIFF('second',r.started_at,CURRENT_TIMESTAMP()) FROM "
        f"{rel('PIPELINE_TASK_ATTEMPTS')} r "
        "WHERE r.state='running' AND NOT EXISTS (SELECT 1 FROM "
        f"{rel('PIPELINE_TASK_ATTEMPTS')} t WHERE t.run_id=r.run_id AND t.task_name=r.task_name "
        "AND t.attempt=r.attempt AND t.state IN ('success','failed'))"
    )
    summaries = []
    for run_id, records in runs.items():
        terminal = {r["task"]: r for r in records}
        audit = terminal.get("record_pipeline_audit")
        state = audit["state"] if audit else "incomplete"
        recovered = state == "success" and any(r["state"] == "failed" for r in records)
        start = min(datetime.fromisoformat(r["started_at"]) for r in records)
        end = max(datetime.fromisoformat(r["ended_at"]) for r in records if r["ended_at"])
        quality = terminal.get("validate_data_quality", {}).get("result", {})
        load = terminal.get("load_snowflake_raw", {}).get("result", {})
        summaries.append(
            {
                "run_id": run_id,
                "state": state,
                "recovered_by_retry": recovered,
                "task_span_seconds": round((end - start).total_seconds(), 3),
                "retries": sum(r["attempt"] > 1 for r in records),
                "publication_status": "published" if run_id in published_runs else "not_published",
                "inserted_raw_rows": load.get("rows_loaded"),
                "verified_inventory": terminal.get("reconcile_raw", {}).get("result"),
                "quality_outcomes": quality.get("tests", {}).get("outcomes"),
                "freshness_outcomes": quality.get("freshness", {}).get("outcomes"),
            }
        )
    states = Counter(r["state"] for r in summaries)
    complete = states["success"] + states["failed"]
    load_errors = query(
        f"SELECT COUNT(*),COUNT(DISTINCT run_id,source_file,error_line),"
        f"COUNT_IF(error_line IS NULL) FROM {rel('LOAD_ERRORS')}"
    )[0]
    failed_categories = Counter(
        a["failure_category"]
        for a in attempts
        if a["state"] == "failed" and a["task"] != "record_pipeline_audit"
    )
    terminal_keys = Counter((a["run_id"], a["task"], a["attempt"]) for a in attempts)
    latest_good = next((r for r in reversed(summaries) if r["state"] == "success"), {})
    rejected_evaluations = sum(
        a["observation"].get("rejected_rows") or 0
        for a in attempts
        if a["observation"].get("accounting_scope") == "isolated_synthetic"
    )
    traceable_synthetic_rejections = {
        (row[0], row[1])
        for a in attempts
        for row in a["result"].get("accounting", {}).get("rejected_provenance", [])
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "existing pipeline task audit; validation runs are not production incidents",
        "summary": {
            "total_runs": len(summaries),
            "successful_runs": states["success"],
            "failed_runs": states["failed"],
            "incomplete_runs": states["incomplete"],
            "recovered_by_retry_runs": sum(r["recovered_by_retry"] for r in summaries),
            "success_rate": states["success"] / complete if complete else None,
            "average_task_span_seconds": round(
                sum(r["task_span_seconds"] for r in summaries) / len(summaries), 3
            )
            if summaries
            else None,
            "latest_task_span_seconds": summaries[-1]["task_span_seconds"] if summaries else None,
            "retry_attempts": sum(r["retries"] for r in summaries),
            "failed_attempt_categories": dict(failed_categories),
            "current_reporting_version": current[0][0],
            "publications": len(publications),
            "load_error_diagnostics": int(load_errors[0]),
            "traceable_rejected_load_lines": int(load_errors[1]),
            "unlocated_load_error_diagnostics": int(load_errors[2] or 0),
            "synthetic_rejected_row_evaluations": rejected_evaluations,
            "distinct_synthetic_rejected_source_lines": len(traceable_synthetic_rejections),
            "latest_verified_inventory": latest_good.get("verified_inventory"),
            "latest_quality_outcomes": latest_good.get("quality_outcomes"),
            "latest_freshness_outcomes": latest_good.get("freshness_outcomes"),
            "recorded_quality_rule_failure_evaluations": sum(
                a["observation"].get("test_failures", 0)
                for a in attempts
                if a["task"] == "validate_data_quality"
            ),
            "failed_quality_gate_attempts": failed_categories.get("data_quality", 0),
            "total_new_raw_rows": sum(r["inserted_raw_rows"] or 0 for r in summaries),
            "inflight_attempts": len(inflight),
            "stale_running_attempts": sum(row[4] > 35 * 60 for row in inflight),
            "duplicate_terminal_attempt_keys": sum(count > 1 for count in terminal_keys.values()),
        },
        "runs": summaries,
        "attempts": attempts,
        "inflight": [
            {
                "run_id": run,
                "task": task,
                "attempt": int(attempt),
                "started_at": start.isoformat(),
                "age_seconds": int(age),
            }
            for run, task, attempt, start, age in inflight
        ],
        "publications": [[v, run, timestamp.isoformat()] for v, run, timestamp in publications],
    }


def read_timeout_evidence(root):
    attempts = []
    for path in sorted(root.glob("attempt=*.log")):
        types = []
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            errors = event.get("error_detail", [])
            if isinstance(errors, list):
                types.extend(
                    e["exc_type"] for e in errors if isinstance(e, dict) and e.get("exc_type")
                )
        attempts.append({"attempt": int(path.stem.split("=")[1]), "exception_types": types})
    return {
        "origin": "actual_airflow_task_logs",
        "scenario_origin": "Milestone 7 reused evidence",
        "run_id": root.parent.name.removeprefix("run_id="),
        "category": "timeout_interruption",
        "synthetic": True,
        "attempts": attempts,
        "timeout_attempts": sum("AirflowTaskTimeout" in a["exception_types"] for a in attempts),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-log-root", type=Path)
    args = parser.parse_args()
    if args.timeout_log_root:
        report = read_timeout_evidence(args.timeout_log_root)
    else:
        settings = SnowflakeSettings.from_env()
        connection = connect_snowflake(settings)
        try:
            report = collect_monitoring(connection, settings.names)
        finally:
            connection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report.get("summary", report)))


if __name__ == "__main__":
    main()
