with product_categories as (
    select distinct coalesce(product_category_name, '__UNKNOWN__') as product_category_name
    from {{ ref('stg_products') }}
),

translations as (
    select * from {{ ref('stg_category_translation') }}
)

select
    {{ surrogate_key(['categories.product_category_name']) }} as category_key,
    categories.product_category_name,
    case
        when categories.product_category_name = '__UNKNOWN__' then 'unknown'
        else coalesce(translations.product_category_name_english, 'untranslated')
    end as product_category_name_english,
    case
        when categories.product_category_name = '__UNKNOWN__' then 'unknown'
        when translations.product_category_name is null then 'untranslated'
        else 'translated'
    end as translation_status
from product_categories as categories
left join translations
    on categories.product_category_name = translations.product_category_name
