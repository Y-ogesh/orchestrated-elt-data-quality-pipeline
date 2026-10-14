with expected_actual as (
    select
        'customers' as table_name,
        (select count(*) from {{ source('olist_raw', 'customers') }}) as source_rows,
        (select count(*) from {{ ref('stg_customers') }}) as staging_rows
    union all
    select
        'geolocation',
        (select count(*) from {{ source('olist_raw', 'geolocation') }}),
        (select count(*) from {{ ref('stg_geolocation') }})
    union all
    select
        'order_items',
        (select count(*) from {{ source('olist_raw', 'order_items') }}),
        (select count(*) from {{ ref('stg_order_items') }})
    union all
    select
        'order_payments',
        (select count(*) from {{ source('olist_raw', 'order_payments') }}),
        (select count(*) from {{ ref('stg_order_payments') }})
    union all
    select
        'order_reviews',
        (select count(*) from {{ source('olist_raw', 'order_reviews') }}),
        (select count(*) from {{ ref('stg_order_reviews') }})
    union all
    select
        'orders',
        (select count(*) from {{ source('olist_raw', 'orders') }}),
        (select count(*) from {{ ref('stg_orders') }})
    union all
    select
        'products',
        (select count(*) from {{ source('olist_raw', 'products') }}),
        (select count(*) from {{ ref('stg_products') }})
    union all
    select
        'sellers',
        (select count(*) from {{ source('olist_raw', 'sellers') }}),
        (select count(*) from {{ ref('stg_sellers') }})
    union all
    select
        'category_translation',
        (select count(*) from {{ source('olist_raw', 'category_translation') }}),
        (select count(*) from {{ ref('stg_category_translation') }})
)

select *
from expected_actual
where source_rows <> staging_rows
