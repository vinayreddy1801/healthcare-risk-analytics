-- mart_member_risk_profile.sql (Synthea version)
-- One row per member. Master risk profile table.

with members as (
    select * from {{ ref('stg_members') }}
),

chronic_flags as (
    select * from {{ ref('int_member_chronic_flags') }}
),

-- Encounter-level utilization
encounter_util as (
    select
        member_id,
        count(distinct encounter_id)                                            as total_encounters,
        countif(claim_type = 'inpatient')                                       as ip_admit_count,
        countif(claim_type = 'emergency')                                       as er_visit_count,
        countif(claim_type = 'carrier')                                         as office_visit_count,
        sum(paid_amount)                                                        as total_encounter_cost,
        max(service_date)                                                       as last_encounter_date
    from {{ ref('stg_encounters') }}
    group by member_id
),

-- Medication count (proxy for polypharmacy)
med_summary as (
    select
        member_id,
        count(distinct rxnorm_code)                                             as distinct_drugs,
        countif(is_active)                                                      as active_medications,
        sum(total_drug_cost)                                                    as total_rx_cost
    from {{ ref('stg_medications') }}
    group by member_id
),

combined as (
    select
        m.member_id,
        m.measurement_year,
        m.age_at_year_end,
        m.sex,
        m.race,
        m.ethnicity,
        m.state,
        m.city,
        m.is_deceased,

        -- Condition flags from claims-derived chronic flags
        coalesce(cf.cc_diabetes,        0)  as cc_diabetes,
        coalesce(cf.cc_chf,             0)  as cc_chf,
        coalesce(cf.cc_ckd,             0)  as cc_ckd,
        coalesce(cf.cc_copd,            0)  as cc_copd,
        coalesce(cf.cc_alzheimers,      0)  as cc_alzheimers,
        coalesce(cf.cc_depression,      0)  as cc_depression,
        coalesce(cf.cc_ihd,             0)  as cc_ihd,
        coalesce(cf.cc_osteoporosis,    0)  as cc_osteoporosis,
        coalesce(cf.cc_arthritis,       0)  as cc_arthritis,
        coalesce(cf.cc_stroke,          0)  as cc_stroke,
        coalesce(cf.cc_hypertension,    0)  as cc_hypertension,
        coalesce(cf.cc_hyperlipidemia,  0)  as cc_hyperlipidemia,
        coalesce(cf.cc_cancer,          0)  as cc_cancer,
        coalesce(cf.cc_obesity,         0)  as cc_obesity,
        coalesce(cf.cc_afib,            0)  as cc_afib,
        coalesce(cf.cc_anxiety,         0)  as cc_anxiety,
        coalesce(cf.cc_asthma,          0)  as cc_asthma,

        coalesce(cf.confirmed_condition_count, 0)   as condition_count,
        coalesce(cf.hcc_risk_score, 0.0)            as hcc_risk_score,

        -- Utilization
        coalesce(eu.total_encounters, 0)            as total_encounters,
        coalesce(eu.ip_admit_count, 0)              as ip_admit_count,
        coalesce(eu.er_visit_count, 0)              as er_visit_count,
        coalesce(eu.office_visit_count, 0)          as office_visit_count,
        coalesce(ms.distinct_drugs, 0)              as distinct_drugs,
        coalesce(ms.active_medications, 0)          as active_medications,

        -- Cost (Synthea tracks lifetime costs; we approximate PMPM from total)
        coalesce(eu.total_encounter_cost, 0)        as total_encounter_cost,
        coalesce(ms.total_rx_cost, 0)               as total_rx_cost,
        coalesce(m.total_healthcare_expenses, 0)    as total_healthcare_expenses,

        -- PMPM approximation (divide lifetime cost by estimated months enrolled)
        round(
            coalesce(m.total_healthcare_expenses, 0)
            / nullif(
                greatest(
                    date_diff(
                        coalesce(m.death_date, current_date()),
                        date(1950, 1, 1),  -- Synthea patients can span decades
                        month
                    ), 1
                ), 0
            )
        , 2)                                        as cost_pmpm_lifetime,

        -- Simpler annual PMPM: total expenses / age in years / 12
        round(
            coalesce(m.total_healthcare_expenses, 0)
            / nullif(greatest(coalesce(m.age_at_year_end, 1), 1), 0)
            / 12.0
        , 2)                                        as cost_pmpm,

        current_timestamp()                         as _loaded_at

    from members m
    left join chronic_flags cf  on m.member_id = cf.member_id
    left join encounter_util eu on m.member_id = eu.member_id
    left join med_summary ms    on m.member_id = ms.member_id
),

risk_tiered as (
    select
        *,
        case
            when hcc_risk_score >= 1.5
                or ip_admit_count >= 3
                or er_visit_count >= 5
                or cc_cancer = 1                        then 'high'
            when hcc_risk_score >= 0.8
                or condition_count >= 4
                or cost_pmpm >= 1000                    then 'moderate'
            when condition_count >= 2
                and (
                    ip_admit_count >= 1
                    or er_visit_count >= 2
                )                                       then 'rising_cost'
            else                                             'low'
        end                                             as risk_tier
    from combined
)

select * from risk_tiered
