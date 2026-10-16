{% macro generate_alias_name(custom_alias_name=none, node=none) -%}
    {%- set prefix = env_var('OLIST_RELATION_PREFIX', '') -%}
    {%- if prefix and not modules.re.fullmatch('M6_[A-F0-9]{12}_', prefix) -%}
        {{ exceptions.raise_compiler_error('Invalid isolated replay relation prefix') }}
    {%- endif -%}
    {{ prefix }}{{ custom_alias_name | trim if custom_alias_name else node.name }}
{%- endmacro %}
