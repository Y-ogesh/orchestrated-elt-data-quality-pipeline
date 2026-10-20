"""Run authorized M8 scenarios through Airflow and verify live operational evidence.

Use ignored configuration and explicitly enable orchestration probes first.
Checkpointed API captures contain no credentials. Does not unpause scheduling.
"""

import json
import time
from pathlib import Path

from airflow_control import request
from validate_orchestration import snapshot

from olist_pipeline.monitoring import collect_monitoring, quarantine_probe
from olist_pipeline.warehouse import SnowflakeSettings, connect_snowflake

ROOT = Path("data/processed/monitoring")
SCENARIOS = (
    ("rejected_source", "failed"),
    ("recovered_source", "success"),
    ("reconciliation_retry", "success"),
    ("quality_retry", "success"),
    ("publication_retry", "success"),
)


def save(name, data):
    (ROOT / (name + ".json")).write_text(json.dumps(data, indent=2, default=str) + "\n")


def token():
    password = json.loads(Path("data/processed/airflow/passwords.json").read_text())["admin"]
    return request("/auth/token", {"username": "admin", "password": password})["access_token"]


def run_scenario(mode, expected):
    run_id = "m8_" + mode + "_20261016"
    path = "/api/v2/dags/olist_elt_pipeline/dagRuns"
    captures = request(path + "?limit=100", token=token())["dag_runs"]
    if not any(r["dag_run_id"] == run_id for r in captures):
        from datetime import datetime, timezone

        request(
            path,
            {
                "dag_run_id": run_id,
                "logical_date": datetime.now(timezone.utc).isoformat(),
                "conf": {"validation_mode": mode},
            },
            token=token(),
        )
    last = None
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        auth = token()
        run = request(path + "/" + run_id, token=auth)
        tasks = request(path + "/" + run_id + "/taskInstances", token=auth)["task_instances"]
        result = {k: run.get(k) for k in ("dag_run_id", "state", "start_date", "end_date")}
        result["tasks"] = [
            {
                k: t.get(k)
                for k in ("task_id", "state", "try_number", "start_date", "end_date", "duration")
            }
            for t in tasks
        ]
        state = [(t["task_id"], t["state"], t["try_number"]) for t in result["tasks"]]
        if state != last:
            print(json.dumps({"scenario": mode, "state": run["state"], "tasks": state}), flush=True)
            last = state
        if run["state"] in ("success", "failed"):
            save(mode + "_airflow", result)
            if run["state"] != expected:
                raise RuntimeError("Unexpected scenario outcome: " + mode)
            return result
        time.sleep(5)
    raise TimeoutError("Scenario did not reach terminal state")


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    settings = SnowflakeSettings.from_env()
    before_path = ROOT / "before.json"
    if not before_path.exists():
        save("before", snapshot())
    before = json.loads(before_path.read_text())
    connection = connect_snowflake(settings)
    try:
        baseline = quarantine_probe(connection, settings.names, corrected=True)
        assert baseline["source_rows"] == baseline["accepted_rows"] == baseline["target_rows"] == 3
        assert baseline["rejected_rows"] == baseline["rerun_inserted_rows"] == 0
        save("quarantine_baseline", baseline)
    finally:
        connection.close()
    scenarios = {}
    for mode, expected in SCENARIOS:
        scenarios[mode] = run_scenario(mode, expected)
        # Capture after every scenario, including the failed run, before recovery starts.
        checkpoint = ROOT / (mode + "_snapshot.json")
        if checkpoint.exists():
            after = json.loads(checkpoint.read_text())
        else:
            after = snapshot()
            save(mode + "_snapshot", after)
        for key in ("reporting", "production", "metrics"):
            assert before[key] == after[key], (mode, key)
        if mode == "rejected_source":
            assert before["version"] == after["version"]
            assert before["publications"] == after["publications"]
            publication = next(
                t for t in scenarios[mode]["tasks"] if t["task_id"] == "publish_reporting"
            )
            assert publication["try_number"] == 0 and publication["state"] == "upstream_failed"
    connection = connect_snowflake(settings)
    try:
        monitoring = collect_monitoring(connection, settings.names)
    finally:
        connection.close()
    report = {
        "status": "Partially implemented",
        "airflow_runs": scenarios,
        "quarantine_baseline": baseline,
        "monitoring": monitoring,
        "production_preserved": True,
        "reporting_business_state_preserved": True,
        "before": before,
        "after": after,
        "screenshots": "Not captured; manual authenticated UI capture documented",
    }
    save("validation", report)
    print(
        json.dumps({"scenarios_finished": len(scenarios), "summary": monitoring["summary"]}),
        flush=True,
    )


if __name__ == "__main__":
    main()
