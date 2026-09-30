select
    nullif(trim(order_id), '') as order_id,
    try_to_number(nullif(trim(payment_sequential), ''), 38, 0) as payment_sequential,
    lower(nullif(trim(payment_type), '')) as payment_type,
    try_to_number(nullif(trim(payment_installments), ''), 38, 0) as payment_installments,
    try_to_decimal(nullif(trim(payment_value), ''), 18, 2) as payment_value,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'order_payments') }}
