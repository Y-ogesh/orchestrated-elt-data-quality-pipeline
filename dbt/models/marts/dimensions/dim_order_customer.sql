select
    {{ surrogate_key(['customers.customer_id']) }} as order_customer_key,
    {{ surrogate_key(['customers.customer_unique_id']) }} as customer_key,
    coalesce(
        geography.geography_key,
        {{ surrogate_key(["'__UNKNOWN__'"]) }}
    ) as geography_key,
    customers.customer_id,
    customers.customer_unique_id,
    customers.customer_zip_code_prefix,
    customers.customer_city,
    customers.customer_state
from {{ ref('stg_customers') }} as customers
left join {{ ref('dim_geography') }} as geography
    on customers.customer_zip_code_prefix = geography.postal_code_prefix
