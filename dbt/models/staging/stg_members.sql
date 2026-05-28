-- stg_members.sql
-- Standardizes Synthea patients.csv into the member dimension.
-- One row per patient.

with source as (
    select * from {{ source('raw', 'patients') }}
),

renamed as (
    select
        -- Keys
        cast(Id as string)                                          as member_id,

        -- Demographics
        cast(BIRTHDATE as date)                                     as date_of_birth,
        cast(DEATHDATE as date)                                     as death_date,
        date_diff(
            date({{ var('measurement_year') }}, 12, 31),
            cast(BIRTHDATE as date),
            year
        )                                                           as age_at_year_end,
        case
            when upper(GENDER) = 'M' then 'M'
            when upper(GENDER) = 'F' then 'F'
            else 'U'
        end                                                         as sex,
        initcap(lower(cast(RACE as string)))                        as race,
        initcap(lower(cast(ETHNICITY as string)))                   as ethnicity,
        cast(STATE as string)                                       as state,
        cast(CITY as string)                                        as city,
        cast(ZIP as string)                                         as zip_code,

        -- Cost totals (Synthea tracks lifetime costs per patient)
        coalesce(cast(HEALTHCARE_EXPENSES as numeric), 0)           as total_healthcare_expenses,
        coalesce(cast(HEALTHCARE_COVERAGE as numeric), 0)           as total_healthcare_coverage,
        coalesce(cast(HEALTHCARE_EXPENSES as numeric), 0)
            - coalesce(cast(HEALTHCARE_COVERAGE as numeric), 0)     as total_out_of_pocket,

        -- Derived flags
        case when DEATHDATE is not null then true else false end     as is_deceased,

        -- Measurement context
        {{ var('measurement_year') }}                               as measurement_year,
        current_timestamp()                                         as _loaded_at

    from source
    where Id is not null
)

select * from renamed
