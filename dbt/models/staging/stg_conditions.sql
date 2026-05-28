-- stg_conditions.sql
-- Standardizes Synthea conditions.csv — patient diagnoses with SNOMED-CT codes.
-- This is the primary source for condition identification and risk scoring.
-- One row per condition per patient (conditions can be ongoing or resolved).

with source as (
    select * from {{ source('raw', 'conditions') }}
),

renamed as (
    select
        -- Keys
        cast(PATIENT as string)                                     as member_id,
        cast(ENCOUNTER as string)                                   as encounter_id,

        -- Dates
        cast(START as date)                                         as onset_date,
        cast(STOP as date)                                          as resolution_date,

        -- Condition codes (SNOMED-CT)
        cast(CODE as string)                                        as snomed_code,
        cast(DESCRIPTION as string)                                 as condition_description,

        -- Derived flags
        case when STOP is null then true else false end             as is_active,
        extract(year from cast(START as date))                     as onset_year,

        -- Surrogate key
        {{ dbt_utils.generate_surrogate_key(['PATIENT', 'CODE', 'START']) }} as condition_id,

        current_timestamp()                                         as _loaded_at

    from source
    where PATIENT is not null
        and CODE is not null
)

select * from renamed
