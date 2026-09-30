{% macro surrogate_key(columns) -%}
    sha2(
        concat_ws(
            '||',
            {%- for column in columns %}
            coalesce(cast({{ column }} as varchar), '__DBT_NULL__')
            {%- if not loop.last %}, {% endif -%}
            {%- endfor %}
        ),
        256
    )
{%- endmacro %}
