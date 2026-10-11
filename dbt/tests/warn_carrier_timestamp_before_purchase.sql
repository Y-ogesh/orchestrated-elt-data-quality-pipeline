{{ config(severity='warn') }}

select order_id
from {{ ref('stg_orders') }}
where order_delivered_carrier_timestamp < order_purchase_timestamp
