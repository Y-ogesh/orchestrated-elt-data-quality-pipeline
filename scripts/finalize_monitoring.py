"""Fail-closed release checks and sanitized M8 evidence from actual audit/query results."""

import json
import re
from datetime import datetime
from pathlib import Path

from airflow_control import request
from validate_monitoring import ROOT, SCENARIOS, token
from validate_orchestration import snapshot

from olist_pipeline.monitoring import collect_monitoring
from olist_pipeline.snowflake_sql import quote_fqn
from olist_pipeline.warehouse import SnowflakeSettings, connect_snowflake


def read(name):
    return json.loads((ROOT / name).read_text())


def test_result(name):
    output = (ROOT / name).read_text()
    count, seconds = re.search(r"Ran (\d+) tests in ([\d.]+)s", output).groups()
    assert re.search(r"^OK(?: \(skipped=\d+\))?$", output, re.MULTILINE)
    skip = re.search(r"OK \(skipped=(\d+)\)", output)
    skipped = int(skip.group(1)) if skip else 0
    return {
        "discovered": int(count),
        "passed": int(count) - skipped,
        "skipped": skipped,
        "seconds": float(seconds),
    }


def main():
    before = read("before.json")
    after = snapshot()
    for key in ("reporting", "production", "metrics"):
        assert before[key] == after[key], key
    failed = read("rejected_source_snapshot.json")
    for key in ("version", "reporting", "production", "metrics", "publications"):
        assert before[key] == failed[key], key
    settings = SnowflakeSettings.from_env()
    connection = connect_snowflake(settings)
    try:
        monitoring = collect_monitoring(connection, settings.names)
        inventory = {}
        with connection.cursor() as cursor:
            for model, (count, _) in after["reporting"].items():
                relation = quote_fqn(
                    settings.names.database, settings.names.marts_schema, "REPORT_STORE_" + model
                )
                cursor.execute(f"SELECT _report_version,COUNT(*) FROM {relation} GROUP BY 1")
                inventory[model] = {v: int(n) for v, n in cursor.fetchall()}
                assert all(n == count for n in inventory[model].values()), model
                assert set(inventory[model]) == {v for v, _ in after["publications"]}
            cursor.execute(
                f"SELECT COUNT(*) FROM "
                f"{quote_fqn(settings.names.database, 'INFORMATION_SCHEMA', 'TABLES')} "
                "WHERE TABLE_SCHEMA=%s AND TABLE_NAME IN "
                "('M8_PROBE_SOURCE','M8_PROBE_QUARANTINE','M8_PROBE_ACCEPTED')",
                (settings.names.audit_schema,),
            )
            remaining_fixture_relations = int(cursor.fetchone()[0])
            assert remaining_fixture_relations == 0
    finally:
        connection.close()
    assert monitoring["summary"]["duplicate_terminal_attempt_keys"] == 0
    assert monitoring["summary"]["inflight_attempts"] == 0
    attempts = monitoring["attempts"]
    runs = {r["run_id"]: r for r in monitoring["runs"]}
    api_runs = request("/api/v2/dags/olist_elt_pipeline/dagRuns?limit=100", token=token())[
        "dag_runs"
    ]
    missing_cloud_audit = [r["dag_run_id"] for r in api_runs if r["dag_run_id"] not in runs]
    assert not missing_cloud_audit, "Airflow runs missing cloud task audit"
    for run in api_runs:
        if run["dag_run_id"] in runs:
            assert run["state"] == runs[run["dag_run_id"]]["state"]
    timed_runs = sorted(
        (r for r in api_runs if r["dag_run_id"] in runs), key=lambda r: r["start_date"]
    )
    runtimes = [
        (
            datetime.fromisoformat(r["end_date"]) - datetime.fromisoformat(r["start_date"])
        ).total_seconds()
        for r in timed_runs
    ]
    scenario_results = {}
    for mode, expected in SCENARIOS:
        run_id = "m8_" + mode + "_20261016"
        assert runs[run_id]["state"] == expected
        captured = read(mode + "_airflow.json")
        captured["seconds"] = round(
            (
                datetime.fromisoformat(captured["end_date"])
                - datetime.fromisoformat(captured["start_date"])
            ).total_seconds(),
            3,
        )
        history = [v for v, r in after["publications"] if r == run_id]
        assert len(history) == (0 if expected == "failed" else 1)
        scenario_results[mode] = captured
    rejects = [
        a
        for a in attempts
        if a["run_id"] == "m8_rejected_source_20261016" and a["task"] == "load_snowflake_raw"
    ]
    assert len(rejects) == 2
    for a in rejects:
        assert a["state"] == "failed" and a["failure_category"] == "snowflake_load"
        account = a["result"]["accounting"]
        assert (
            account["source_rows"],
            account["accepted_rows"],
            account["rejected_rows"],
            account["diagnostics"],
            account["inserted_rows"],
        ) == (3, 1, 2, 3, 0)
    corrected = next(
        a["result"]["synthetic_recovery"]
        for a in attempts
        if a["run_id"] == "m8_recovered_source_20261016" and a["task"] == "load_snowflake_raw"
    )
    assert corrected["inserted_rows"] == corrected["target_rows"] == 3
    assert corrected["rejected_rows"] == corrected["rerun_inserted_rows"] == 0
    for mode, task, category in (
        ("reconciliation_retry", "reconcile_raw", "reconciliation"),
        ("quality_retry", "validate_data_quality", "data_quality"),
        ("publication_retry", "publish_reporting", "publication"),
    ):
        records = [
            a for a in attempts if a["run_id"] == "m8_" + mode + "_20261016" and a["task"] == task
        ]
        assert [(a["attempt"], a["state"]) for a in records] == [(1, "failed"), (2, "success")]
        assert records[0]["failure_category"] == category
        if mode == "publication_retry":
            rollback = records[0]["result"]
            assert rollback["uncommitted_rows_before_rollback"] > 0
            assert rollback["rolled_back_candidate_rows_remaining"] == 0
            assert rollback["pointer_preserved"]
        elif mode == "reconciliation_retry":
            assert records[0]["result"]["row_difference"] == 1
        else:
            assert records[0]["result"]["synthetic_quality"]["violations"] == 1
            assert records[1]["result"]["synthetic_quality"]["violations"] == 0
    timeout = read("timeout_evidence.json")
    assert timeout["timeout_attempts"] == 2
    publication_windows = []
    for event in attempts:
        if not event["run_id"].startswith("m8_") or event["state"] != "failed":
            continue
        at_start = [
            v
            for v, _, at in monitoring["publications"]
            if datetime.fromisoformat(at) <= datetime.fromisoformat(event["started_at"])
        ]
        at_end = [
            v
            for v, _, at in monitoring["publications"]
            if datetime.fromisoformat(at) <= datetime.fromisoformat(event["ended_at"])
        ]
        assert at_start == at_end and at_start
        publication_windows.append(
            {
                "run_id": event["run_id"],
                "task": event["task"],
                "attempt": event["attempt"],
                "prior_version": at_start[-1],
                "published_versions_during_failed_attempt": 0,
                "retained_order_rows": inventory["fct_orders"][at_start[-1]],
            }
        )
    regression = read("production_regression.json")
    assert regression["tests"]["outcomes"] == {"pass": 156, "warn": 1}
    assert regression["freshness"]["outcomes"] == {"pass": 9}
    assert regression["reconciliation"]["production_synthetic_rows"] == 0
    report = {
        "status": "Completed and validated",
        "validation_date": "2026-10-16",
        "monitoring": monitoring,
        "scenarios": scenario_results,
        "rejected_accounting": rejects[0]["result"]["accounting"],
        "corrected_accounting": corrected,
        "cross_run_recovery": {
            "failed": "m8_rejected_source_20261016",
            "recovered": "m8_recovered_source_20261016",
            "basis": "same isolated source fixture corrected; exactly one publication",
        },
        "timeout_evidence": timeout,
        "failed_attempt_publication_windows": publication_windows,
        "airflow_runs_missing_cloud_audit": missing_cloud_audit,
        "production_regression": regression,
        "reporting_version_counts": inventory,
        "remaining_fixture_relations": remaining_fixture_relations,
        "integrity_before": {
            k: before[k] for k in ("version", "reporting", "production", "metrics")
        },
        "integrity_after": {k: after[k] for k in ("version", "reporting", "production", "metrics")},
        "tests": {
            "pipeline": test_result("pipeline_tests.log"),
            "airflow": test_result("airflow_tests.log"),
            "offline": test_result("local_tests.log"),
        },
        "screenshots": "Not captured; optional authenticated UI task documented",
    }
    Path("reports/monitoring_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = {
        "status": report["status"],
        "generated_at": monitoring["generated_at"],
        **monitoring["summary"],
        "airflow_average_runtime_seconds": round(sum(runtimes) / len(runtimes), 3),
        "airflow_latest_runtime_seconds": round(runtimes[-1], 3),
        "timeout_attempts": timeout["timeout_attempts"],
        "timeout_scope": "one separately verified M7 no-cloud probe, not pipeline incidents",
        "cross_run_source_recoveries": 1,
        "latest_reconciliation_status": "pass",
        "current_publication_validated": True,
        "production_integrity_preserved": True,
        "synthetic_fixture_relations_remaining": remaining_fixture_relations,
    }
    Path("reports/monitoring_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "summary": monitoring["summary"],
                "scenario_seconds": {k: v["seconds"] for k, v in scenario_results.items()},
                "tests": report["tests"],
            }
        )
    )


if __name__ == "__main__":
    main()
