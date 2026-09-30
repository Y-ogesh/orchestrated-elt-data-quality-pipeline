select
    nullif(trim(order_id), '') as order_id,
    try_to_number(nullif(trim(order_item_id), ''), 38, 0) as order_item_id,
    nullif(trim(product_id), '') as product_id,
    nullif(trim(seller_id), '') as seller_id,
    try_to_timestamp_ntz(nullif(trim(shipping_limit_date), '')) as shipping_limit_timestamp,
    try_to_decimal(nullif(trim(price), ''), 18, 2) as item_price,
    try_to_decimal(nullif(trim(freight_value), ''), 18, 2) as freight_value,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'order_items') }}
