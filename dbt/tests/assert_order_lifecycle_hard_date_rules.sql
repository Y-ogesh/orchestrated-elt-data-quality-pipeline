select order_id, 'approval_before_purchase' as violation
from {{ ref('stg_orders') }}
where order_approved_timestamp < order_purchase_timestamp

union all

select order_id, 'delivery_before_purchase' as violation
from {{ ref('stg_orders') }}
where order_delivered_customer_timestamp < order_purchase_timestamp

union all

select order_id, 'estimate_before_purchase' as violation
from {{ ref('stg_orders') }}
where order_estimated_delivery_timestamp < order_purchase_timestamp
