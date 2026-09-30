with order_bounds as (
    select
        least_ignore_nulls(
            min(cast(order_purchase_timestamp as date)),
            min(cast(order_approved_timestamp as date)),
            min(cast(order_delivered_carrier_timestamp as date)),
            min(cast(order_delivered_customer_timestamp as date)),
            min(cast(order_estimated_delivery_timestamp as date))
        ) as minimum_date,
        greatest_ignore_nulls(
            max(cast(order_purchase_timestamp as date)),
            max(cast(order_approved_timestamp as date)),
            max(cast(order_delivered_carrier_timestamp as date)),
            max(cast(order_delivered_customer_timestamp as date)),
            max(cast(order_estimated_delivery_timestamp as date))
        ) as maximum_date
    from {{ ref('stg_orders') }}
),

item_bounds as (
    select
        min(cast(shipping_limit_timestamp as date)) as minimum_date,
        max(cast(shipping_limit_timestamp as date)) as maximum_date
    from {{ ref('stg_order_items') }}
),

review_bounds as (
    select
        least_ignore_nulls(
            min(cast(review_creation_timestamp as date)),
            min(cast(review_answer_timestamp as date))
        ) as minimum_date,
        greatest_ignore_nulls(
            max(cast(review_creation_timestamp as date)),
            max(cast(review_answer_timestamp as date))
        ) as maximum_date
    from {{ ref('stg_order_reviews') }}
),

bounds as (
    select
        least_ignore_nulls(orders.minimum_date, items.minimum_date, reviews.minimum_date)
            as minimum_date,
        greatest_ignore_nulls(orders.maximum_date, items.maximum_date, reviews.maximum_date)
            as maximum_date
    from order_bounds as orders
    cross join item_bounds as items
    cross join review_bounds as reviews
),

date_spine as (
    select dateadd(day, row_number() over (order by seq4()) - 1, bounds.minimum_date) as date_day
    from bounds
    cross join table(generator(rowcount => 5000))
    qualify date_day <= bounds.maximum_date
)

select
    to_number(to_char(date_day, 'YYYYMMDD')) as date_key,
    date_day,
    day(date_day) as day_of_month,
    dayofweekiso(date_day) as day_of_week_number,
    dayname(date_day) as day_of_week_name,
    weekiso(date_day) as iso_week_number,
    month(date_day) as month_number,
    monthname(date_day) as month_name,
    quarter(date_day) as quarter_number,
    year(date_day) as year_number,
    dayofweekiso(date_day) in (6, 7) as is_weekend
from date_spine
