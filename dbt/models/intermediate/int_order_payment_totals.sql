select
    order_id,
    count(*) as payment_count,
    count(distinct payment_type) as distinct_payment_type_count,
    max(payment_installments) as maximum_payment_installments,
    round(sum(payment_value), 2) as payment_total_value,
    max(source_loaded_at) as source_loaded_at
from {{ ref('stg_order_payments') }}
group by order_id
