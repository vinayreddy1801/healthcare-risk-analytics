-- int_claims_unioned.sql
-- Unified encounter spine for Synthea data.
-- One row per encounter with cost and claim type.
-- Conditions and procedures are joined separately in downstream models.

with encounters as (
    select
        encounter_id                    as claims_line_id,
        encounter_id                    as claim_id,
        member_id,
        service_date,
        service_end_date,
        provider_id                     as provider_npi,
        claim_type,
        reason_snomed_code              as dx_code,
        reason_description              as dx_description,
        cast(null as string)            as procedure_code,
        paid_amount,
        service_year,
        encounter_class
    from {{ ref('stg_encounters') }}
),

-- Bring in all conditions as additional dx rows (one per condition per encounter)
condition_dx as (
    select
        c.condition_id                  as claims_line_id,
        c.encounter_id                  as claim_id,
        c.member_id,
        e.service_date,
        e.service_end_date,
        e.provider_id                   as provider_npi,
        e.claim_type,
        c.snomed_code                   as dx_code,
        c.condition_description         as dx_description,
        cast(null as string)            as procedure_code,
        cast(0 as numeric)              as paid_amount,
        e.service_year,
        e.encounter_class
    from {{ ref('stg_conditions') }} c
    inner join {{ ref('stg_encounters') }} e
        on c.encounter_id = e.encounter_id
),

-- Procedures as service lines
procedure_lines as (
    select
        p.procedure_id                  as claims_line_id,
        p.encounter_id                  as claim_id,
        p.member_id,
        e.service_date,
        e.service_end_date,
        e.provider_id                   as provider_npi,
        e.claim_type,
        cast(null as string)            as dx_code,
        cast(null as string)            as dx_description,
        p.snomed_code                   as procedure_code,
        cast(0 as numeric)              as paid_amount,
        e.service_year,
        e.encounter_class
    from {{ ref('stg_procedures') }} p
    inner join {{ ref('stg_encounters') }} e
        on p.encounter_id = e.encounter_id
),

unioned as (
    select * from encounters
    union all
    select * from condition_dx
    union all
    select * from procedure_lines
)

select
    *
from unioned
