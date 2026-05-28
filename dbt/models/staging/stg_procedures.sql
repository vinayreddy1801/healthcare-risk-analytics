-- stg_procedures.sql
-- Standardizes Synthea procedures.csv — clinical procedures with SNOMED-CT codes.
-- Used for care gap identification (eye exams, medication reviews, etc.)

with source as (
    select * from {{ source('raw', 'procedures') }}
),

renamed as (
    select
        -- Keys
        cast(PATIENT as string)                                     as member_id,
        cast(ENCOUNTER as string)                                   as encounter_id,

        -- Dates
        cast(DATE as date)                                          as procedure_date,
        cast(DATE as date)                                          as procedure_end_date,

        -- Procedure codes (SNOMED-CT)
        cast(CODE as string)                                        as snomed_code,
        cast(DESCRIPTION as string)                                 as procedure_description,

        -- Cost
        coalesce(cast(BASE_COST as numeric), 0)                    as base_cost,

        extract(year from cast(DATE as date))                      as procedure_year,

        {{ dbt_utils.generate_surrogate_key(['PATIENT', 'CODE', 'DATE', 'ENCOUNTER']) }} as procedure_id,

        current_timestamp()                                         as _loaded_at

    from source
    where PATIENT is not null
)

select * from renamed
