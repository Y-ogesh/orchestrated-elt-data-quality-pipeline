select
    orders.order_id,
    orders.customer_id,
    orders.order_status,
    orders.order_purchase_timestamp,
    orders.order_approved_timestamp,
    orders.order_delivered_carrier_timestamp,
    orders.order_delivered_customer_timestamp,
    orders.order_estimated_delivery_timestamp,
    coalesce(items.order_item_count, 0) as order_item_count,
    coalesce(items.distinct_product_count, 0) as distinct_product_count,
    coalesce(items.distinct_seller_count, 0) as distinct_seller_count,
    coalesce(items.item_merchandise_value, 0.00) as item_merchandise_value,
    coalesce(items.freight_value, 0.00) as freight_value,
    coalesce(items.item_total_value, 0.00) as item_total_value,
    coalesce(payments.payment_count, 0) as payment_count,
    coalesce(payments.distinct_payment_type_count, 0) as distinct_payment_type_count,
    payments.maximum_payment_installments,
    coalesce(payments.payment_total_value, 0.00) as payment_total_value,
    round(
        coalesce(payments.payment_total_value, 0.00)
        - coalesce(items.item_total_value, 0.00),
        2
    ) as payment_item_difference,
    items.order_id is null as is_missing_items,
    payments.order_id is null as is_missing_payments,
    greatest_ignore_nulls(
        orders.source_loaded_at,
        items.source_loaded_at,
        payments.source_loaded_at
    ) as source_loaded_at
from {{ ref('stg_orders') }} as orders
left join {{ ref('int_order_item_totals') }} as items
    on orders.order_id = items.order_id
left join {{ ref('int_order_payment_totals') }} as payments
    on orders.order_id = payments.order_id
