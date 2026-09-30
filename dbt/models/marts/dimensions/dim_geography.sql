with known_geography as (
    select
        {{ surrogate_key(['geolocation_zip_code_prefix']) }} as geography_key,
        geolocation_zip_code_prefix as postal_code_prefix,
        representative_city as city,
        representative_state as state_code,
        representative_latitude as latitude,
        representative_longitude as longitude,
        observation_count,
        exact_duplicate_count,
        invalid_coordinate_count,
        false as is_unknown
    from {{ ref('int_geography_deduplicated') }}
)

select * from known_geography
union all
select
    {{ surrogate_key(["'__UNKNOWN__'"]) }} as geography_key,
    '__UNKNOWN__' as postal_code_prefix,
    'unknown' as city,
    'NA' as state_code,
    null::number(12, 8) as latitude,
    null::number(12, 8) as longitude,
    0 as observation_count,
    0 as exact_duplicate_count,
    0 as invalid_coordinate_count,
    true as is_unknown
