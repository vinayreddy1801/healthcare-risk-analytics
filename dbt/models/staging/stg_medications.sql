-- stg_medications.sql
-- Standardizes Synthea medications.csv — prescriptions with RxNorm codes.
-- Equivalent to Medicare Part D PDE events in the SynPUF design.

with source as (
    select * from {{ source('raw', 'medications') }}
),

renamed as (
    select
        -- Keys
        cast(PATIENT as string)                                     as member_id,
        cast(ENCOUNTER as string)                                   as encounter_id,
        cast(PAYER as string)                                       as payer_id,

        -- Dates
        cast(START as date)                                         as start_date,
        cast(STOP as date)                                          as stop_date,

        -- Drug codes (RxNorm)
        cast(CODE as string)                                        as rxnorm_code,
        cast(DESCRIPTION as string)                                 as drug_description,

        -- Cost
        coalesce(cast(BASE_COST as numeric), 0)                    as base_cost,
        coalesce(cast(PAYER_COVERAGE as numeric), 0)               as payer_coverage,
        coalesce(cast(TOTALCOST as numeric), 0)                    as total_drug_cost,
        coalesce(cast(DISPENSES as int64), 1)                      as dispenses,

        -- Reason for prescription (SNOMED)
        cast(REASONCODE as string)                                  as reason_snomed_code,
        cast(REASONDESCRIPTION as string)                          as reason_description,

        -- Active flag
        case when STOP is null then true else false end             as is_active,

        {{ dbt_utils.generate_surrogate_key(['PATIENT', 'CODE', 'START', 'ENCOUNTER', 'STOP', 'TOTALCOST']) }} as rx_id,

        current_timestamp()                                         as _loaded_at

    from source
    where PATIENT is not null
        and CODE is not null
)

select * from renamed
