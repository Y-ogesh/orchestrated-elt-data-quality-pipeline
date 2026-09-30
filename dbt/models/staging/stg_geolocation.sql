select
    lpad(nullif(trim(geolocation_zip_code_prefix), ''), 5, '0') as geolocation_zip_code_prefix,
    try_to_decimal(nullif(trim(geolocation_lat), ''), 12, 8) as geolocation_latitude,
    try_to_decimal(nullif(trim(geolocation_lng), ''), 12, 8) as geolocation_longitude,
    lower(nullif(trim(geolocation_city), '')) as geolocation_city,
    upper(nullif(trim(geolocation_state), '')) as geolocation_state,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'geolocation') }}
