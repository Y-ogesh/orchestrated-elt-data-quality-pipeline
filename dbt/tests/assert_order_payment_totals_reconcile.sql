with fact_totals as (
    select
        order_id,
        count(*) as payment_count,
        round(sum(payment_value), 2) as payment_total_value
    from {{ ref('fct_order_payments') }}
    group by order_id
)

select
    orders.order_id,
    orders.payment_count,
    facts.payment_count as fact_payment_count,
    orders.payment_total_value,
    facts.payment_total_value as fact_payment_total_value
from {{ ref('fct_orders') }} as orders
left join fact_totals as facts
    on orders.order_id = facts.order_id
where
    orders.payment_count <> coalesce(facts.payment_count, 0)
    or abs(orders.payment_total_value - coalesce(facts.payment_total_value, 0)) > 0.01
