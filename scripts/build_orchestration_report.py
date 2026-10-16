"""Assemble release evidence from actual API/task/Snowflake captures; fail closed."""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from olist_pipeline.orchestration import TASKS, run_version

ROOT = Path("data/processed/orchestration")
RUNS = {
    "scheduled": "scheduled__2026-10-12T06:00:00+00:00",
    "manual": "m7_success_20261016",
    "failure": "m7_failure_20261016",
    "recovery": "m7_recovery_20261016",
}


def read(path):
    return json.loads(path.read_text())


def api(run_id, state):
    return read(
        ROOT
        / "airflow_evidence"
        / (hashlib.sha256(run_id.encode()).hexdigest()[:16] + "_" + state + ".json")
    )


def test_summary(filename):
    output = (ROOT / filename).read_text()
    count, seconds = re.search(r"Ran (\d+) tests in ([\d.]+)s", output).groups()
    assert re.search(r"^OK(?: \(skipped=\d+\))?$", output, re.MULTILINE)
    skipped = re.search(r"OK \(skipped=(\d+)\)", output)
    skipped = int(skipped.group(1)) if skipped else 0
    return {
        "discovered": int(count),
        "passed": int(count) - skipped,
        "skipped": skipped,
        "seconds": float(seconds),
    }


def main():
    runs = {}
    for label, run_id in RUNS.items():
        state = "failed" if label == "failure" else "success"
        capture = api(run_id, state)
        assert capture["state"] == state
        capture["total_seconds"] = round(
            (
                datetime.fromisoformat(capture["end_date"])
                - datetime.fromisoformat(capture["start_date"])
            ).total_seconds(),
            3,
        )
        capture["results"] = {}
        for task in TASKS:
            path = ROOT / run_version(run_id) / f"{task}.result.json"
            if path.exists():
                capture["results"][task] = read(path)
        runs[label] = capture
    failure_tasks = {t["task_id"]: t for t in runs["failure"]["tasks"]}
    assert failure_tasks["publish_reporting"]["state"] == "upstream_failed"
    assert failure_tasks["publish_reporting"]["try_number"] == 0
    assert failure_tasks["validate_data_quality"]["try_number"] == 2
    assert "publish_reporting" not in runs["failure"]["results"]
    before = read(ROOT / "snapshots/before_failure.json")
    failed = read(ROOT / "snapshots/after_failure.json")
    recovered = read(ROOT / "snapshots/after_recovery.json")
    for key in ("version", "reporting", "production", "metrics", "publications"):
        assert before[key] == failed[key], key
    for key in ("reporting", "production", "metrics"):
        assert before[key] == recovered[key], key
    assert recovered["version"] != before["version"]
    queued = api(RUNS["manual"], "queued")
    assert all(t["try_number"] == 0 for t in queued["tasks"])
    assert runs["manual"]["start_date"] >= runs["scheduled"]["end_date"]
    timeout = api("m7_timeout_verified_20261016", "failed")
    assert timeout["tasks"][0]["try_number"] == 2
    assert timeout["tasks"][0]["duration"] >= 2
    report = {
        "status": "Completed and validated",
        "validation_date": "2026-10-16",
        "runs": runs,
        "overlap_protection": {"queued_run": queued, "non_overlapping_intervals": True},
        "timeout_probe": timeout,
        "reporting_preserved_after_failure": True,
        "production_unchanged": True,
        "integrity_snapshots": {
            label: {key: snapshot[key] for key in ("version", "reporting", "production")}
            for label, snapshot in (
                ("before_failure", before),
                ("after_failure", failed),
                ("after_recovery", recovered),
            )
        },
        "repository_tests": {
            "locked_pipeline": test_summary("final_pipeline_tests.log"),
            "airflow_runtime": test_summary("final_airflow_tests.log"),
            "offline_host": test_summary("final_local_tests.log"),
        },
        "recovery_business_metrics": recovered["metrics"],
        "reporting_counts": {k: v[0] for k, v in recovered["reporting"].items()},
        "publication_history": recovered["publications"],
        "audit_attempts": recovered["audit_attempts"],
        "screenshots": "Not captured; optional authenticated UI capture documented",
    }
    Path("reports/orchestration_validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": report["status"],
                "runs": len(runs),
                "reporting_models": len(recovered["reporting"]),
            }
        )
    )


if __name__ == "__main__":
    main()
