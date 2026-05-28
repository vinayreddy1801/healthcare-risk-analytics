-- mart_provider_efficiency.sql
-- Provider-level cost and quality scorecard.
-- Identifies high-value vs low-value providers based on
-- cost-adjusted-for-complexity (cost per unit HCC score).

with claims as (
    select
        claim_id,
        provider_npi,
        member_id,
        claim_type,
        paid_amount,
        service_date
    from {{ ref('int_claims_unioned') }}
    where provider_npi is not null
        and provider_npi != ''
),

-- Get member risk profiles for attribution
member_risk as (
    select
        member_id,
        hcc_risk_score,
        risk_tier,
        condition_count,
        cost_pmpm
    from {{ ref('mart_member_risk_profile') }}
),

-- Get care gap closure rates
gap_summary as (
    select
        member_id,
        avg(case when gap_open = 0 then 1.0 else 0.0 end) as gap_closure_rate
    from {{ ref('mart_care_gaps') }}
    group by member_id
),

-- Attribute members to their most frequent provider
provider_attribution as (
    select
        member_id,
        provider_npi,
        count(distinct claim_id) as claim_count,
        row_number() over (
            partition by member_id
            order by count(distinct claim_id) desc
        ) as rank
    from claims
    group by member_id, provider_npi
),

primary_provider as (
    select member_id, provider_npi
    from provider_attribution
    where rank = 1
),

-- Provider spend from claims
provider_spend as (
    select
        provider_npi,
        sum(paid_amount)                as total_spend,
        count(distinct member_id)       as attributed_member_count,
        count(distinct
            case when claim_type = 'inpatient' then member_id end
        )                               as members_with_ip
    from claims
    group by provider_npi
),

-- Top condition per provider (mode)
provider_top_condition as (
    select
        c.provider_npi,
        f.condition_category,
        row_number() over (
            partition by c.provider_npi
            order by count(*) desc
        ) as rn
    from {{ ref('int_dx_code_flags') }} f
    inner join claims c
        on f.encounter_id = c.claim_id
    where f.condition_category is not null
    group by c.provider_npi, f.condition_category
),

assembled as (
    select
        pp.provider_npi,
        ps.attributed_member_count,
        round(avg(mr.hcc_risk_score), 3)                       as avg_hcc_score,
        round(avg(mr.cost_pmpm), 2)                            as avg_cost_pmpm,
        round(ps.total_spend, 2)                               as total_attributed_spend,
        -- Cost efficiency: cost per unit of HCC (lower = more efficient for complexity)
        round(
            avg(mr.cost_pmpm) / nullif(avg(mr.hcc_risk_score), 0)
        , 2)                                                    as cost_per_hcc_unit,
        round(avg(gc.gap_closure_rate) * 100, 1)               as gap_closure_rate_pct,
        round(avg(mr.condition_count), 1)                      as avg_condition_count,
        ptc.condition_category                                  as top_condition,
        current_timestamp()                                     as _loaded_at

    from primary_provider pp
    inner join member_risk mr    on pp.member_id = mr.member_id
    inner join provider_spend ps on pp.provider_npi = ps.provider_npi
    left join gap_summary gc     on pp.member_id = gc.member_id
    left join provider_top_condition ptc
        on pp.provider_npi = ptc.provider_npi and ptc.rn = 1
    group by pp.provider_npi, ps.attributed_member_count, ps.total_spend, ptc.condition_category
),

-- Quadrant classification based on population medians
medians as (
    select
        percentile_cont(avg_cost_pmpm, 0.5) over ()    as median_cost,
        percentile_cont(avg_hcc_score, 0.5)  over ()   as median_hcc
    from assembled
    limit 1
),

quadrant_assigned as (
    select
        a.*,
        m.median_cost,
        m.median_hcc,
        case
            when a.avg_cost_pmpm <= m.median_cost and a.avg_hcc_score >= m.median_hcc then 'High Value'
            when a.avg_cost_pmpm >  m.median_cost and a.avg_hcc_score <  m.median_hcc then 'Low Value'
            when a.avg_cost_pmpm >  m.median_cost and a.avg_hcc_score >= m.median_hcc then 'Complex High Cost'
            else 'Complex Managed'
        end                                             as efficiency_quadrant
    from assembled a
    cross join medians m
)

select * from quadrant_assigned
where attributed_member_count >= 5  -- filter out single-encounter providers
