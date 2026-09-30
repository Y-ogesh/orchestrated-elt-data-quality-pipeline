CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{AUDIT_SCHEMA}}.LOAD_RUNS (
    run_id VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    batches_expected NUMBER NOT NULL,
    batches_loaded NUMBER NOT NULL DEFAULT 0,
    batches_skipped NUMBER NOT NULL DEFAULT 0,
    expected_rows NUMBER NOT NULL,
    loaded_rows NUMBER NOT NULL DEFAULT 0,
    started_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    completed_at TIMESTAMP_TZ,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{AUDIT_SCHEMA}}.BATCH_LOADS (
    run_id VARCHAR NOT NULL,
    batch_id VARCHAR NOT NULL,
    batch_kind VARCHAR NOT NULL,
    source_version VARCHAR NOT NULL,
    logical_ingestion_date DATE NOT NULL,
    status VARCHAR NOT NULL,
    expected_files NUMBER NOT NULL,
    loaded_files NUMBER NOT NULL DEFAULT 0,
    expected_rows NUMBER NOT NULL,
    loaded_rows NUMBER NOT NULL DEFAULT 0,
    started_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    completed_at TIMESTAMP_TZ,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{AUDIT_SCHEMA}}.FILE_LOADS (
    run_id VARCHAR NOT NULL,
    batch_id VARCHAR NOT NULL,
    table_name VARCHAR NOT NULL,
    stage_path VARCHAR NOT NULL,
    artifact_sha256 VARCHAR(64) NOT NULL,
    source_sha256 VARCHAR(64) NOT NULL,
    expected_rows NUMBER NOT NULL,
    loaded_rows NUMBER NOT NULL,
    status VARCHAR NOT NULL,
    copy_query_id VARCHAR,
    first_error VARCHAR,
    loaded_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS {{DATABASE}}.{{AUDIT_SCHEMA}}.LOAD_ERRORS (
    run_id VARCHAR NOT NULL,
    batch_id VARCHAR,
    table_name VARCHAR,
    source_file VARCHAR,
    query_id VARCHAR,
    error_code VARCHAR,
    error_message VARCHAR,
    error_line NUMBER,
    error_character NUMBER,
    rejected_record VARCHAR,
    captured_at TIMESTAMP_TZ NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.BATCH_RECONCILIATION AS
SELECT
    batch_id,
    source_version,
    logical_ingestion_date,
    status,
    expected_files,
    loaded_files,
    expected_rows,
    loaded_rows,
    expected_rows - loaded_rows AS row_difference,
    expected_files - loaded_files AS file_difference,
    completed_at
FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.BATCH_LOADS
QUALIFY ROW_NUMBER() OVER (PARTITION BY batch_id ORDER BY started_at DESC) = 1;
