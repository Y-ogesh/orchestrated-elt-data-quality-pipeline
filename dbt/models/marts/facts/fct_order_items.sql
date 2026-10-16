{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='order_item_key',
        on_schema_change='fail'
    )
}}

with candidates as (
select
    {{ surrogate_key(['items.order_id', 'items.order_item_id']) }} as order_item_key,
    {{ surrogate_key(['items.order_id']) }} as order_key,
    products.product_key,
    sellers.seller_key,
    to_number(to_char(cast(items.shipping_limit_timestamp as date), 'YYYYMMDD'))
        as shipping_limit_date_key,
    items.order_id,
    items.order_item_id,
    items.item_price,
    items.freight_value,
    items.item_price + items.freight_value as item_total_value,
    items.shipping_limit_timestamp,
    items.source_loaded_at
from {{ ref('stg_order_items') }} as items
inner join {{ ref('dim_product') }} as products
    on items.product_id = products.product_id
inner join {{ ref('dim_seller') }} as sellers
    on items.seller_id = sellers.seller_id
)
select * from candidates
{% if is_incremental() %}
minus
select * from {{ this }}
{% endif %}
