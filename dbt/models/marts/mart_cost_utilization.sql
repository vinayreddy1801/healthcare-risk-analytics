-- mart_cost_utilization.sql
-- Population-level cost and utilization aggregated by risk tier.
-- Drives executive dashboards and trend analysis.

with risk_profiles as (
    select * from {{ ref('mart_member_risk_profile') }}
),

utilization_summary as (
    select
        risk_tier,
        measurement_year,
        count(distinct member_id)                               as member_count,

        -- Cost metrics
        round(avg(cost_pmpm), 2)                               as avg_cost_pmpm,
        round(sum(total_healthcare_expenses), 2)               as total_cost_ytd,
        round(avg(total_encounter_cost * 0.4), 2)              as avg_inpatient_spend,
        round(avg(total_encounter_cost * 0.3), 2)              as avg_outpatient_spend,
        round(avg(total_encounter_cost * 0.3), 2)              as avg_professional_spend,
        round(avg(total_rx_cost), 2)                           as avg_rx_spend,

        -- Utilization rates per 1,000 members
        round(
            sum(ip_admit_count) * 1000.0 / nullif(count(distinct member_id), 0)
        , 1)                                                    as ip_admits_per_1000,
        round(
            sum(er_visit_count) * 1000.0 / nullif(count(distinct member_id), 0)
        , 1)                                                    as er_visits_per_1000,
        round(
            sum(distinct_drugs) * 1000.0 / nullif(count(distinct member_id), 0)
        , 1)                                                    as rx_fills_per_1000,

        -- Clinical complexity
        round(avg(hcc_risk_score), 3)                          as avg_hcc_risk_score,
        round(avg(condition_count), 1)                         as avg_condition_count,
        round(avg(distinct_drugs), 1)                          as avg_distinct_drugs,

        -- Demographics
        round(avg(age_at_year_end), 1)                         as avg_age,
        countif(sex = 'F') * 100.0 / nullif(count(*), 0)      as pct_female,

        current_timestamp()                                     as _loaded_at

    from risk_profiles
    group by risk_tier, measurement_year
),

-- Add % of total population per tier
with_pct as (
    select
        *,
        round(
            member_count * 100.0 / sum(member_count) over (partition by measurement_year)
        , 1)                                                    as pct_of_population,
        round(
            total_cost_ytd * 100.0 / sum(total_cost_ytd) over (partition by measurement_year)
        , 1)                                                    as pct_of_total_cost
    from utilization_summary
)

select * from with_pct
order by measurement_year, 
    case risk_tier
        when 'high' then 1
        when 'rising_cost' then 2
        when 'moderate' then 3
        when 'low' then 4
        else 5
    end
