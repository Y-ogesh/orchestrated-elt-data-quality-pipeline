"""Local Airflow API helper. Reads generated login secret, never prints tokens."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8080"
DAG = "olist_elt_pipeline"


def request(path, data=None, method=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
        method=method,
    )
    with urlopen(req, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("trigger", "status", "pause", "unpause", "inventory"))
    parser.add_argument("--run-id")
    parser.add_argument("--mode", default="normal")
    parser.add_argument("--dag", default=DAG)
    args = parser.parse_args()
    password = json.loads(Path("data/processed/airflow/passwords.json").read_text())["admin"]
    token = request("/auth/token", {"username": "admin", "password": password})["access_token"]
    path = f"/api/v2/dags/{args.dag}"
    if args.action in ("pause", "unpause"):
        result = request(path, {"is_paused": args.action == "pause"}, "PATCH", token)
        print(json.dumps({"dag_id": result["dag_id"], "is_paused": result["is_paused"]}))
    elif args.action == "trigger":
        result = request(
            path + "/dagRuns",
            {
                "dag_run_id": args.run_id,
                "logical_date": datetime.now(timezone.utc).isoformat(),
                "conf": {"validation_mode": args.mode},
            },
            token=token,
        )
        print(json.dumps({"run_id": result["dag_run_id"], "state": result["state"]}))
    elif args.action == "inventory":
        result = request(path + "/tasks", token=token)
        print(json.dumps(result))
    else:
        run = request(path + "/dagRuns/" + args.run_id, token=token)
        tasks = request(path + "/dagRuns/" + args.run_id + "/taskInstances", token=token)
        result = {
            k: run.get(k) for k in ("dag_id", "dag_run_id", "state", "start_date", "end_date")
        }
        result["tasks"] = [
            {
                k: t.get(k)
                for k in ("task_id", "state", "try_number", "start_date", "end_date", "duration")
            }
            for t in tasks["task_instances"]
        ]
        target = Path("data/processed/orchestration/airflow_evidence")
        target.mkdir(parents=True, exist_ok=True)
        # Fixed run-version hashing prevents caller-controlled filesystem paths.
        import hashlib

        filename = (
            hashlib.sha256(args.run_id.encode()).hexdigest()[:16] + "_" + run["state"] + ".json"
        )
        (target / filename).write_text(json.dumps(result, indent=2))
        print(json.dumps(result))


if __name__ == "__main__":
    main()
