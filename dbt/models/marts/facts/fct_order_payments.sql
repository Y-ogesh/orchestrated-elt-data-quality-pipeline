{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='payment_key',
        on_schema_change='fail'
    )
}}

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
{% if is_incremental() %}
where payments.source_loaded_at >= (
    select coalesce(max(source_loaded_at), '1900-01-01'::timestamp_tz) from {{ this }}
)
{% endif %}
