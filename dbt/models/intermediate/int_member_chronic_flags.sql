-- int_member_chronic_flags.sql (Synthea version)
-- One row per member with confirmed chronic condition flags.
-- A condition is "confirmed" if it appears at least once in conditions.csv
-- (Synthea records conditions as diagnosed — no need for 2-claim threshold).

with dx_flags as (
    select
        member_id,
        condition_category,
        count(distinct dx_code)     as distinct_codes,
        count(*)                    as total_occurrences,
        min(service_date)           as first_dx_date,
        max(service_date)           as last_dx_date,
        max(case when is_active then 1 else 0 end) as currently_active,
        sum(hcc_weight)             as raw_hcc_contribution
    from {{ ref('int_dx_code_flags') }}
    where condition_category is not null
    group by member_id, condition_category
),

pivoted as (
    select
        member_id,
        max(case when condition_category = 'diabetes_t2'    then 1 else 0 end) as cc_diabetes,
        max(case when condition_category = 'chf'            then 1 else 0 end) as cc_chf,
        max(case when condition_category = 'ckd'            then 1 else 0 end) as cc_ckd,
        max(case when condition_category = 'copd'           then 1 else 0 end) as cc_copd,
        max(case when condition_category = 'alzheimers'     then 1 else 0 end) as cc_alzheimers,
        max(case when condition_category = 'depression'     then 1 else 0 end) as cc_depression,
        max(case when condition_category = 'ihd'            then 1 else 0 end) as cc_ihd,
        max(case when condition_category = 'osteoporosis'   then 1 else 0 end) as cc_osteoporosis,
        max(case when condition_category = 'arthritis'      then 1 else 0 end) as cc_arthritis,
        max(case when condition_category = 'stroke'         then 1 else 0 end) as cc_stroke,
        max(case when condition_category = 'hypertension'   then 1 else 0 end) as cc_hypertension,
        max(case when condition_category = 'hyperlipidemia' then 1 else 0 end) as cc_hyperlipidemia,
        max(case when condition_category = 'cancer_solid'   then 1 else 0 end) as cc_cancer,
        max(case when condition_category = 'obesity'        then 1 else 0 end) as cc_obesity,
        max(case when condition_category = 'afib'           then 1 else 0 end) as cc_afib,
        max(case when condition_category = 'anxiety'        then 1 else 0 end) as cc_anxiety,
        max(case when condition_category = 'asthma'         then 1 else 0 end) as cc_asthma,

        -- Comorbidity burden
        count(distinct condition_category)                          as confirmed_condition_count,

        -- Simplified HCC risk score
        round(
            least(coalesce(sum(raw_hcc_contribution), 0), 5.0)
        , 3)                                                        as hcc_risk_score,
        coalesce(sum(raw_hcc_contribution), 0)                      as hcc_risk_score_raw

    from dx_flags
    group by member_id
)

select * from pivoted
