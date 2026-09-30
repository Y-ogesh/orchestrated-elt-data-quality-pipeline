select
    {{ surrogate_key(['products.product_id']) }} as product_key,
    categories.category_key,
    products.product_id,
    products.product_category_name,
    products.product_name_length,
    products.product_description_length,
    products.product_photos_quantity,
    products.product_weight_grams,
    products.product_length_cm,
    products.product_height_cm,
    products.product_width_cm
from {{ ref('stg_products') }} as products
inner join {{ ref('dim_category') }} as categories
    on coalesce(products.product_category_name, '__UNKNOWN__')
        = categories.product_category_name
