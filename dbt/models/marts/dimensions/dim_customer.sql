select
    {{ surrogate_key(['customers.customer_unique_id']) }} as customer_key,
    customers.customer_unique_id,
    min(cast(orders.order_purchase_timestamp as date)) as first_order_date,
    max(cast(orders.order_purchase_timestamp as date)) as last_order_date,
    count(distinct orders.order_id) as lifetime_order_count
from {{ ref('stg_customers') }} as customers
left join {{ ref('stg_orders') }} as orders
    on customers.customer_id = orders.customer_id
group by customers.customer_unique_id
