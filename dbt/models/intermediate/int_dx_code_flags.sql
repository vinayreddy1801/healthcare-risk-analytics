-- int_dx_code_flags.sql (Synthea version)
-- Joins SNOMED condition codes to the snomed_condition_map seed.
-- Uses exact code matching (SNOMED codes are specific, not ranges like ICD-10).

with conditions as (
    select
        condition_id,
        member_id,
        encounter_id,
        onset_date              as service_date,
        onset_year              as service_year,
        snomed_code             as dx_code,
        condition_description,
        is_active,
        resolution_date
    from {{ ref('stg_conditions') }}
    where snomed_code is not null
),

condition_map as (
    select
        cast(snomed_code as string)         as snomed_code,
        condition_category,
        condition_label,
        hcc_category,
        cast(hcc_weight as numeric)         as hcc_weight
    from {{ ref('snomed_condition_map') }}
),

mapped as (
    select
        c.condition_id,
        c.member_id,
        c.encounter_id,
        c.service_date,
        c.service_year,
        c.dx_code,
        c.condition_description,
        c.is_active,
        m.condition_category,
        m.condition_label,
        m.hcc_category,
        m.hcc_weight
    from conditions c
    left join condition_map m
        on c.dx_code = m.snomed_code
)

select * from mapped
