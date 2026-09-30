select orders.order_id
from {{ ref('stg_orders') }} as orders
full outer join {{ ref('fct_orders') }} as facts
    on orders.order_id = facts.order_id
where orders.order_id is null or facts.order_id is null
