select
    nullif(trim(seller_id), '') as seller_id,
    lpad(nullif(trim(seller_zip_code_prefix), ''), 5, '0') as seller_zip_code_prefix,
    lower(nullif(trim(seller_city), '')) as seller_city,
    upper(nullif(trim(seller_state), '')) as seller_state,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'sellers') }}
