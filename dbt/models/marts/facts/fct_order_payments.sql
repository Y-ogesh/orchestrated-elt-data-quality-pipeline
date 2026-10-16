{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='payment_key',
        on_schema_change='fail'
    )
}}

with candidates as (
select
    {{ surrogate_key(['payments.order_id', 'payments.payment_sequential']) }} as payment_key,
    {{ surrogate_key(['payments.order_id']) }} as order_key,
    payments.order_id,
    payments.payment_sequential,
    payments.payment_type,
    payments.payment_installments,
    payments.payment_value,
    payments.source_loaded_at
from {{ ref('stg_order_payments') }} as payments
)
select * from candidates
{% if is_incremental() %}
minus
select * from {{ this }}
{% endif %}
