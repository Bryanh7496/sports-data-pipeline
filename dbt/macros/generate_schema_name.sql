{#
  By default dbt names custom schemas <target_schema>_<custom_schema>
  (e.g. ANALYTICS_STAGING). This override uses the custom schema name
  as-is, so models land in SPORTS_DB.STAGING and SPORTS_DB.MARTS, which
  matches the raw -> staging -> marts layering in the docs.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
