{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='order_key',
        on_schema_change='fail'
    )
}}

select
    {{ surrogate_key(['orders.order_id']) }} as order_key,
    customer.order_customer_key,
    customer.customer_key,
    to_number(to_char(cast(orders.order_purchase_timestamp as date), 'YYYYMMDD'))
        as purchase_date_key,
    orders.order_id,
    orders.order_status,
    orders.order_purchase_timestamp,
    orders.order_approved_timestamp,
    orders.order_delivered_carrier_timestamp,
    orders.order_delivered_customer_timestamp,
    orders.order_estimated_delivery_timestamp,
    orders.order_item_count,
    orders.distinct_product_count,
    orders.distinct_seller_count,
    orders.item_merchandise_value,
    orders.freight_value,
    orders.item_total_value,
    orders.payment_count,
    orders.distinct_payment_type_count,
    orders.maximum_payment_installments,
    orders.payment_total_value,
    orders.payment_item_difference,
    abs(orders.payment_item_difference) > {{ var('payment_reconciliation_tolerance') }}
        as is_payment_reconciliation_exception,
    orders.is_missing_items,
    orders.is_missing_payments,
    datediff(
        day,
        orders.order_purchase_timestamp,
        orders.order_delivered_customer_timestamp
    ) as delivery_days,
    case
        when orders.order_delivered_customer_timestamp is null then null
        else orders.order_delivered_customer_timestamp > orders.order_estimated_delivery_timestamp
    end as is_late_delivery,
    orders.source_loaded_at
from {{ ref('int_orders_enriched') }} as orders
inner join {{ ref('dim_order_customer') }} as customer
    on orders.customer_id = customer.customer_id
{% if is_incremental() %}
where orders.source_loaded_at >= (
    select coalesce(max(source_loaded_at), '1900-01-01'::timestamp_tz) from {{ this }}
)
{% endif %}
