with expected_actual as (
    select
        'dim_customer' as model_name,
        (select count(distinct customer_unique_id) from {{ ref('stg_customers') }})
            as expected_rows,
        (select count(*) from {{ ref('dim_customer') }}) as actual_rows
    union all
    select
        'dim_order_customer',
        (select count(*) from {{ ref('stg_customers') }}),
        (select count(*) from {{ ref('dim_order_customer') }})
    union all
    select
        'dim_product',
        (select count(*) from {{ ref('stg_products') }}),
        (select count(*) from {{ ref('dim_product') }})
    union all
    select
        'dim_seller',
        (select count(*) from {{ ref('stg_sellers') }}),
        (select count(*) from {{ ref('dim_seller') }})
    union all
    select
        'fct_orders',
        (select count(*) from {{ ref('stg_orders') }}),
        (select count(*) from {{ ref('fct_orders') }})
    union all
    select
        'fct_order_items',
        (select count(*) from {{ ref('stg_order_items') }}),
        (select count(*) from {{ ref('fct_order_items') }})
    union all
    select
        'fct_order_payments',
        (select count(*) from {{ ref('stg_order_payments') }}),
        (select count(*) from {{ ref('fct_order_payments') }})
    union all
    select
        'fct_order_reviews',
        (select count(*) from {{ ref('stg_order_reviews') }}),
        (select count(*) from {{ ref('fct_order_reviews') }})
)

select *
from expected_actual
where expected_rows <> actual_rows
