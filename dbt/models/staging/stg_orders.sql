select
    nullif(trim(order_id), '') as order_id,
    nullif(trim(customer_id), '') as customer_id,
    lower(nullif(trim(order_status), '')) as order_status,
    try_to_timestamp_ntz(nullif(trim(order_purchase_timestamp), '')) as order_purchase_timestamp,
    try_to_timestamp_ntz(nullif(trim(order_approved_at), '')) as order_approved_timestamp,
    try_to_timestamp_ntz(nullif(trim(order_delivered_carrier_date), ''))
        as order_delivered_carrier_timestamp,
    try_to_timestamp_ntz(nullif(trim(order_delivered_customer_date), ''))
        as order_delivered_customer_timestamp,
    try_to_timestamp_ntz(nullif(trim(order_estimated_delivery_date), ''))
        as order_estimated_delivery_timestamp,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'orders') }}
