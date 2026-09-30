select
    order_id,
    count(*) as order_item_count,
    count(distinct product_id) as distinct_product_count,
    count(distinct seller_id) as distinct_seller_count,
    round(sum(item_price), 2) as item_merchandise_value,
    round(sum(freight_value), 2) as freight_value,
    round(sum(item_price) + sum(freight_value), 2) as item_total_value,
    max(source_loaded_at) as source_loaded_at
from {{ ref('stg_order_items') }}
group by order_id
