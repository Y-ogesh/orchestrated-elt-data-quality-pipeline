select
    nullif(trim(product_id), '') as product_id,
    nullif(trim(product_category_name), '') as product_category_name,
    try_to_number(nullif(trim(product_name_lenght), ''), 38, 0) as product_name_length,
    try_to_number(nullif(trim(product_description_lenght), ''), 38, 0)
        as product_description_length,
    try_to_number(nullif(trim(product_photos_qty), ''), 38, 0) as product_photos_quantity,
    try_to_decimal(nullif(trim(product_weight_g), ''), 18, 3) as product_weight_grams,
    try_to_decimal(nullif(trim(product_length_cm), ''), 18, 3) as product_length_cm,
    try_to_decimal(nullif(trim(product_height_cm), ''), 18, 3) as product_height_cm,
    try_to_decimal(nullif(trim(product_width_cm), ''), 18, 3) as product_width_cm,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'products') }}
