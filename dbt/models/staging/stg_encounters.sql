-- stg_encounters.sql
-- Standardizes Synthea encounters.csv.
-- Replaces both stg_inpatient_claims and stg_outpatient_claims from the SynPUF design.
-- One row per encounter. Claim type derived from ENCOUNTERCLASS.

with source as (
    select * from {{ source('raw', 'encounters') }}
),

renamed as (
    select
        -- Keys
        cast(Id as string)                                          as encounter_id,
        cast(PATIENT as string)                                     as member_id,
        cast(PROVIDER as string)                                    as provider_id,
        cast(PAYER as string)                                       as payer_id,

        -- Dates
        cast(START as timestamp)                                    as service_start_ts,
        cast(STOP as timestamp)                                     as service_end_ts,
        date(cast(START as timestamp))                              as service_date,
        date(cast(STOP as timestamp))                               as service_end_date,

        -- Encounter classification
        lower(cast(ENCOUNTERCLASS as string))                       as encounter_class,

        -- Map Synthea encounter classes to claim types
        case lower(cast(ENCOUNTERCLASS as string))
            when 'inpatient'    then 'inpatient'
            when 'emergency'    then 'emergency'
            when 'urgentcare'   then 'outpatient'
            when 'outpatient'   then 'outpatient'
            when 'ambulatory'   then 'outpatient'
            when 'office'       then 'carrier'
            when 'wellness'     then 'carrier'
            when 'home'         then 'carrier'
            else                     'outpatient'
        end                                                         as claim_type,

        -- Diagnosis context (reason for visit — SNOMED code)
        cast(REASONCODE as string)                                  as reason_snomed_code,
        cast(REASONDESCRIPTION as string)                           as reason_description,

        -- Encounter type code (SNOMED)
        cast(CODE as string)                                        as encounter_snomed_code,
        cast(DESCRIPTION as string)                                 as encounter_description,

        -- Cost
        coalesce(cast(BASE_ENCOUNTER_COST as numeric), 0)           as base_encounter_cost,
        coalesce(cast(TOTAL_CLAIM_COST as numeric), 0)              as paid_amount,
        coalesce(cast(PAYER_COVERAGE as numeric), 0)                as payer_coverage,
        coalesce(cast(TOTAL_CLAIM_COST as numeric), 0)
            - coalesce(cast(PAYER_COVERAGE as numeric), 0)          as member_paid_amount,

        extract(year from cast(START as timestamp))                 as service_year,
        current_timestamp()                                         as _loaded_at

    from source
    where Id is not null
        and PATIENT is not null
        and START is not null
)

select * from renamed
