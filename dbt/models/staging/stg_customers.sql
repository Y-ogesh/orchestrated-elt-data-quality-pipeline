select
    nullif(trim(customer_id), '') as customer_id,
    nullif(trim(customer_unique_id), '') as customer_unique_id,
    lpad(nullif(trim(customer_zip_code_prefix), ''), 5, '0') as customer_zip_code_prefix,
    lower(nullif(trim(customer_city), '')) as customer_city,
    upper(nullif(trim(customer_state), '')) as customer_state,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'customers') }}
