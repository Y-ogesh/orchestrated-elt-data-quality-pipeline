select review_record_key
from {{ ref('stg_order_reviews') }}
where review_answer_timestamp < review_creation_timestamp
