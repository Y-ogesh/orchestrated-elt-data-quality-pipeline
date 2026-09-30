select
    {{ surrogate_key([
        "nullif(trim(review_id), '')",
        "nullif(trim(order_id), '')",
        "nullif(trim(review_score), '')",
        "nullif(trim(review_comment_title), '')",
        "nullif(trim(review_comment_message), '')",
        "nullif(trim(review_creation_date), '')",
        "nullif(trim(review_answer_timestamp), '')"
    ]) }} as review_record_key,
    nullif(trim(review_id), '') as review_id,
    nullif(trim(order_id), '') as order_id,
    try_to_number(nullif(trim(review_score), ''), 38, 0) as review_score,
    nullif(trim(review_comment_title), '') as review_comment_title,
    nullif(trim(review_comment_message), '') as review_comment_message,
    try_to_timestamp_ntz(nullif(trim(review_creation_date), '')) as review_creation_timestamp,
    try_to_timestamp_ntz(nullif(trim(review_answer_timestamp), '')) as review_answer_timestamp,
    _batch_id as source_batch_id,
    _source_file as source_file,
    _file_sha256 as source_file_sha256,
    _source_version as source_version,
    _logical_ingestion_date as source_logical_ingestion_date,
    _source_row_number as source_row_number,
    _load_run_id as source_load_run_id,
    _loaded_at as source_loaded_at
from {{ source('olist_raw', 'order_reviews') }}
