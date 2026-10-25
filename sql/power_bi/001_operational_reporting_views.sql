CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.PBI_SOURCE_FRESHNESS AS
WITH source_loads AS (
    SELECT 'customers' AS source_name, MAX(_loaded_at) AS last_loaded_at
    FROM {{DATABASE}}.{{RAW_SCHEMA}}.CUSTOMERS
    UNION ALL
    SELECT 'geolocation', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.GEOLOCATION
    UNION ALL
    SELECT 'order_items', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_ITEMS
    UNION ALL
    SELECT 'order_payments', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_PAYMENTS
    UNION ALL
    SELECT 'order_reviews', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDER_REVIEWS
    UNION ALL
    SELECT 'orders', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.ORDERS
    UNION ALL
    SELECT 'products', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.PRODUCTS
    UNION ALL
    SELECT 'sellers', MAX(_loaded_at) FROM {{DATABASE}}.{{RAW_SCHEMA}}.SELLERS
    UNION ALL
    SELECT 'category_translation', MAX(_loaded_at)
    FROM {{DATABASE}}.{{RAW_SCHEMA}}.CATEGORY_TRANSLATION
)
SELECT
    source_name,
    last_loaded_at,
    DATEDIFF('hour', last_loaded_at, CURRENT_TIMESTAMP()) AS freshness_age_hours,
    CASE
        WHEN last_loaded_at IS NULL THEN 'error'
        WHEN DATEDIFF('hour', last_loaded_at, CURRENT_TIMESTAMP()) > 720 THEN 'error'
        WHEN DATEDIFF('hour', last_loaded_at, CURRENT_TIMESTAMP()) > 168 THEN 'warn'
        ELSE 'pass'
    END AS freshness_status
FROM source_loads;

CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.PBI_PIPELINE_RUNS AS
WITH terminal_attempts AS (
    SELECT
        run_id,
        task_name,
        attempt,
        state,
        started_at,
        ended_at,
        duration_seconds,
        details,
        ROW_NUMBER() OVER (
            PARTITION BY run_id, task_name, attempt
            ORDER BY ended_at DESC NULLS LAST
        ) AS event_rank
    FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.PIPELINE_TASK_ATTEMPTS
    WHERE state <> 'running'
),
deduplicated AS (
    SELECT * EXCLUDE event_rank
    FROM terminal_attempts
    WHERE event_rank = 1
),
final_run_state AS (
    SELECT run_id, state AS final_state
    FROM deduplicated
    WHERE task_name = 'record_pipeline_audit'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY run_id ORDER BY started_at DESC) = 1
),
run_rollup AS (
    SELECT
        run_id,
        MIN(started_at) AS started_at,
        MAX(ended_at) AS ended_at,
        DATEDIFF('second', MIN(started_at), MAX(ended_at)) AS observed_task_span_seconds,
        COUNT_IF(attempt > 1) AS retry_attempt_count,
        COUNT_IF(state = 'failed' AND task_name <> 'record_pipeline_audit')
            AS root_failed_attempt_count,
        MAX(COALESCE(details:_monitoring:warning_count::NUMBER, 0)) AS warning_count,
        MAX(COALESCE(details:_monitoring:test_failures::NUMBER, 0)) AS quality_failure_count,
        MAX(IFF(
            details:_monitoring:accounting_scope::VARCHAR = 'production_raw',
            details:_monitoring:source_rows::NUMBER,
            NULL
        )) AS verified_source_rows,
        MAX(IFF(
            details:_monitoring:accounting_scope::VARCHAR = 'production_raw',
            details:_monitoring:accepted_rows::NUMBER,
            NULL
        )) AS accepted_rows,
        MAX(IFF(
            details:_monitoring:accounting_scope::VARCHAR = 'production_raw',
            details:_monitoring:rejected_rows::NUMBER,
            NULL
        )) AS rejected_rows
    FROM deduplicated
    GROUP BY run_id
)
SELECT
    runs.run_id,
    states.final_state,
    runs.started_at,
    runs.ended_at,
    runs.observed_task_span_seconds,
    runs.retry_attempt_count,
    runs.root_failed_attempt_count,
    runs.warning_count,
    runs.quality_failure_count,
    runs.verified_source_rows,
    runs.accepted_rows,
    runs.rejected_rows,
    publications.version AS published_version,
    publications.published_at,
    publications.version IS NOT NULL AS is_published
FROM run_rollup AS runs
LEFT JOIN final_run_state AS states USING (run_id)
LEFT JOIN {{DATABASE}}.{{AUDIT_SCHEMA}}.REPORTING_VERSIONS AS publications USING (run_id);

CREATE OR REPLACE VIEW {{DATABASE}}.{{AUDIT_SCHEMA}}.PBI_PIPELINE_HEALTH AS
WITH current_publication AS (
    SELECT
        pointer.version AS current_reporting_version,
        history.run_id AS latest_validated_run_id,
        history.published_at AS latest_validated_at
    FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.REPORTING_CURRENT AS pointer
    INNER JOIN {{DATABASE}}.{{AUDIT_SCHEMA}}.REPORTING_VERSIONS AS history
        ON pointer.version = history.version
    WHERE pointer.singleton = 1
),
latest_quality AS (
    SELECT
        run_id,
        COALESCE(details:tests:outcomes:pass::NUMBER, 0) AS quality_tests_passed,
        COALESCE(details:tests:outcomes:warn::NUMBER, 0) AS quality_test_warnings,
        COALESCE(details:_monitoring:test_failures::NUMBER, 0) AS quality_test_failures,
        COALESCE(details:freshness:outcomes:pass::NUMBER, 0) AS freshness_sources_passed
    FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.PIPELINE_TASK_ATTEMPTS
    WHERE task_name = 'validate_data_quality' AND state = 'success'
    QUALIFY ROW_NUMBER() OVER (ORDER BY ended_at DESC) = 1
),
production_accounting AS (
    SELECT
        SUM(loaded_rows) AS accepted_rows,
        SUM(expected_rows) AS source_rows,
        SUM(expected_rows - loaded_rows) AS rejected_or_missing_rows
    FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.BATCH_RECONCILIATION
    WHERE status = 'SUCCEEDED'
),
rejected_lines AS (
    SELECT
        COUNT(*) AS rejection_diagnostics,
        COUNT(DISTINCT run_id, source_file, error_line) AS traceable_rejected_rows,
        COUNT_IF(error_line IS NULL) AS unlocated_rejection_diagnostics
    FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.LOAD_ERRORS
),
freshness AS (
    SELECT
        MAX(freshness_age_hours) AS maximum_freshness_age_hours,
        COUNT_IF(freshness_status = 'pass') AS current_freshness_pass_count,
        COUNT_IF(freshness_status = 'warn') AS current_freshness_warning_count,
        COUNT_IF(freshness_status = 'error') AS current_freshness_error_count
    FROM {{DATABASE}}.{{AUDIT_SCHEMA}}.PBI_SOURCE_FRESHNESS
)
SELECT
    publication.current_reporting_version,
    publication.latest_validated_run_id,
    publication.latest_validated_at,
    'success' AS latest_pipeline_status,
    quality.quality_tests_passed,
    quality.quality_test_warnings,
    quality.quality_test_failures,
    quality.freshness_sources_passed AS freshness_sources_passed_at_validation,
    accounting.source_rows,
    accounting.accepted_rows,
    accounting.rejected_or_missing_rows,
    rejected.traceable_rejected_rows,
    rejected.rejection_diagnostics,
    rejected.unlocated_rejection_diagnostics,
    freshness.maximum_freshness_age_hours,
    freshness.current_freshness_pass_count,
    freshness.current_freshness_warning_count,
    freshness.current_freshness_error_count,
    IFF(freshness.current_freshness_error_count > 0, 'error',
        IFF(freshness.current_freshness_warning_count > 0, 'warn', 'pass'))
        AS current_freshness_status
FROM current_publication AS publication
CROSS JOIN latest_quality AS quality
CROSS JOIN production_accounting AS accounting
CROSS JOIN rejected_lines AS rejected
CROSS JOIN freshness;
