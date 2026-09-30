with fact_totals as (
    select
        order_id,
        count(*) as order_item_count,
        round(sum(item_price), 2) as item_merchandise_value,
        round(sum(freight_value), 2) as freight_value,
        round(sum(item_total_value), 2) as item_total_value
    from {{ ref('fct_order_items') }}
    group by order_id
)

select
    orders.order_id,
    orders.order_item_count,
    facts.order_item_count as fact_order_item_count,
    orders.item_merchandise_value,
    facts.item_merchandise_value as fact_item_merchandise_value,
    orders.freight_value,
    facts.freight_value as fact_freight_value,
    orders.item_total_value,
    facts.item_total_value as fact_item_total_value
from {{ ref('fct_orders') }} as orders
left join fact_totals as facts
    on orders.order_id = facts.order_id
where
    orders.order_item_count <> coalesce(facts.order_item_count, 0)
    or abs(orders.item_merchandise_value - coalesce(facts.item_merchandise_value, 0)) > 0.01
    or abs(orders.freight_value - coalesce(facts.freight_value, 0)) > 0.01
    or abs(orders.item_total_value - coalesce(facts.item_total_value, 0)) > 0.01
