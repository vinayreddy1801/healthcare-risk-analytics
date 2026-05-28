-- icd10_in_range.sql
-- Returns a SQL boolean expression for ICD-10 code range matching.
-- SynPUF uses ICD-9 codes; this macro handles both formats.
-- Usage: {{ icd10_in_range('dx_code', 'E11', 'E13') }}

{% macro icd10_in_range(col, start_code, end_code) %}
    ({{ col }} >= '{{ start_code }}' and {{ col }} <= '{{ end_code }}')
{% endmacro %}


-- icd_matches_any.sql
-- Returns a SQL boolean for matching a code column against a list of codes.
-- Usage: {{ icd_matches_any('cpt_code', ['83036','83037','83038']) }}

{% macro icd_matches_any(col, code_list) %}
    {{ col }} in ({{ code_list | map('tojson') | join(', ') }})
{% endmacro %}


-- generate_condition_flag.sql
-- Macro to DRY up condition flag logic across intermediate models.
-- Usage: {{ generate_condition_flag('dx_code', 'diabetes') }}

{% macro generate_condition_flag(dx_col, condition_name) %}
    max(case when condition_category = '{{ condition_name }}' then 1 else 0 end)
{% endmacro %}
