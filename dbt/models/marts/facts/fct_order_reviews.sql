{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='review_key',
        on_schema_change='fail'
    )
}}

select
    reviews.review_record_key as review_key,
    {{ surrogate_key(['reviews.order_id']) }} as order_key,
    to_number(to_char(cast(reviews.review_creation_timestamp as date), 'YYYYMMDD'))
        as review_creation_date_key,
    reviews.review_id,
    reviews.order_id,
    reviews.review_score,
    reviews.review_comment_title,
    reviews.review_comment_message,
    reviews.review_creation_timestamp,
    reviews.review_answer_timestamp,
    reviews.source_loaded_at
from {{ ref('stg_order_reviews') }} as reviews
{% if is_incremental() %}
where reviews.source_loaded_at >= (
    select coalesce(max(source_loaded_at), '1900-01-01'::timestamp_tz) from {{ this }}
)
{% endif %}
