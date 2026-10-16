"""Airflow coordinates stable task boundaries; business logic stays in the package."""

import os
import signal
import subprocess
from datetime import datetime, timedelta, timezone

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

from olist_pipeline.orchestration import DAG_ID, TASKS


def execute_boundary(boundary, **context):
    ti = context["ti"]
    mode = (context["dag_run"].conf or {}).get("validation_mode", "normal")
    process = subprocess.Popen(
        [
            "/opt/pipeline-venv/bin/python",
            "-m",
            "olist_pipeline.orchestration",
            boundary,
            "--run-id",
            context["run_id"],
            "--attempt",
            str(ti.try_number),
            "--mode",
            mode,
        ],
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=1500)
        if code:
            raise RuntimeError(f"Pipeline boundary failed with exit code {code}")
    except BaseException:
        # Cancel only this task's process group, including its dbt children.
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
        raise


with DAG(
    DAG_ID,
    description="Validated Olist batch ELT with atomic reporting publication",
    schedule="0 6 * * 1",
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=1,
    dagrun_timeout=timedelta(hours=2),
    default_args={
        "owner": "olist-pipeline",
        "retries": 1,
        "retry_delay": timedelta(seconds=15),
        "execution_timeout": timedelta(minutes=30),
        "pool": "olist_writer",
    },
    tags=["olist", "batch", "validated-publication"],
) as dag:
    tasks = {}
    for name in TASKS:
        tasks[name] = PythonOperator(
            task_id=name,
            python_callable=execute_boundary,
            op_kwargs={"boundary": name},
            do_xcom_push=False,
            trigger_rule="all_done" if name == "record_pipeline_audit" else "all_success",
            retries=0 if name == "record_pipeline_audit" else 1,
        )
    for left, right in zip(TASKS[:-2], TASKS[1:-1]):
        tasks[left] >> tasks[right]
    list(tasks.values())[:-1] >> tasks["record_pipeline_audit"]
