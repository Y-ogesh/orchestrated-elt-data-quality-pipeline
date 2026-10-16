FROM apache/airflow:3.3.2-python3.11@sha256:a6685a7a708ed6fa910c2c05458d7f2b0db9cca5c3bf58a72ded389767ad3e65
USER root
RUN python -m venv /opt/pipeline-venv && chown -R airflow:0 /opt/pipeline-venv
USER airflow
COPY requirements-pipeline.lock /tmp/requirements-pipeline.lock
RUN /opt/pipeline-venv/bin/pip install --no-cache-dir -r /tmp/requirements-pipeline.lock
