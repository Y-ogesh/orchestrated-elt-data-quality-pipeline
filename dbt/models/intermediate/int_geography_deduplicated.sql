with observations as (
    select
        *,
        geolocation_latitude between -34 and 6
            and geolocation_longitude between -74 and -34 as is_valid_brazil_coordinate
    from {{ ref('stg_geolocation') }}
),

coordinate_summary as (
    select
        geolocation_zip_code_prefix,
        median(case when is_valid_brazil_coordinate then geolocation_latitude end)
            as representative_latitude,
        median(case when is_valid_brazil_coordinate then geolocation_longitude end)
            as representative_longitude,
        count(*) as observation_count,
        count_if(not is_valid_brazil_coordinate) as invalid_coordinate_count,
        count(*) - count(distinct
            geolocation_latitude,
            geolocation_longitude,
            geolocation_city,
            geolocation_state
        ) as exact_duplicate_count,
        max(source_loaded_at) as source_loaded_at
    from observations
    group by geolocation_zip_code_prefix
),

locality_counts as (
    select
        geolocation_zip_code_prefix,
        geolocation_city,
        geolocation_state,
        count(*) as locality_observation_count
    from observations
    group by geolocation_zip_code_prefix, geolocation_city, geolocation_state
),

representative_locality as (
    select
        geolocation_zip_code_prefix,
        geolocation_city as representative_city,
        geolocation_state as representative_state
    from locality_counts
    qualify row_number() over (
        partition by geolocation_zip_code_prefix
        order by locality_observation_count desc, geolocation_city, geolocation_state
    ) = 1
)

select
    summary.geolocation_zip_code_prefix,
    locality.representative_city,
    locality.representative_state,
    summary.representative_latitude,
    summary.representative_longitude,
    summary.observation_count,
    summary.exact_duplicate_count,
    summary.invalid_coordinate_count,
    summary.source_loaded_at
from coordinate_summary as summary
inner join representative_locality as locality
    on summary.geolocation_zip_code_prefix = locality.geolocation_zip_code_prefix
