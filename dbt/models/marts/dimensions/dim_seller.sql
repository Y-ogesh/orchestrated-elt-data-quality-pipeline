select
    {{ surrogate_key(['sellers.seller_id']) }} as seller_key,
    coalesce(
        geography.geography_key,
        {{ surrogate_key(["'__UNKNOWN__'"]) }}
    ) as geography_key,
    sellers.seller_id,
    sellers.seller_zip_code_prefix,
    sellers.seller_city,
    sellers.seller_state
from {{ ref('stg_sellers') }} as sellers
left join {{ ref('dim_geography') }} as geography
    on sellers.seller_zip_code_prefix = geography.postal_code_prefix
