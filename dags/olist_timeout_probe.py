"""Opt-in, no-cloud-write probe of Airflow's actual task timeout enforcement."""

import os
import time
from datetime import datetime, timedelta, timezone

from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG


def exceed_timeout():
    time.sleep(10)


if os.getenv("OLIST_ENABLE_ORCHESTRATION_PROBES") == "1":
    with DAG(
        "olist_timeout_probe",
        schedule=None,
        start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
        catchup=False,
        max_active_runs=1,
        dagrun_timeout=timedelta(minutes=2),
        tags=["validation-only", "no-cloud-writes"],
    ) as dag:
        PythonOperator(
            task_id="timeout_probe",
            python_callable=exceed_timeout,
            execution_timeout=timedelta(seconds=2),
            retries=1,
            retry_delay=timedelta(seconds=2),
            do_xcom_push=False,
        )
