-- mart_care_gaps.sql (Synthea version)
-- HEDIS-adjacent care gap flags using SNOMED procedure codes.

-- Gap definitions:
-- 1. diabetes_a1c       — Diabetic member with no HbA1c procedure in conditions/procedures
-- 2. diabetes_eye_exam  — Diabetic member with no retinal exam procedure
-- 3. high_risk_med_review — Member on 5+ drugs with no medication review procedure
-- 4. readmission_30d    — Inpatient readmit within 30 days of prior discharge

-- SNOMED codes used:
-- HbA1c:          43396009  (Hemoglobin A1c measurement)
-- Retinal exam:   252779009 (Fundoscopy), 6615001 (Ophthalmoscopy)
-- Med review:     182836005 (Drug review), 428191000124101 (Medication reconciliation)

with members as (
    select member_id, measurement_year, cc_diabetes, distinct_drugs
    from {{ ref('mart_member_risk_profile') }}
),

-- All procedures
procedures as (
    select member_id, snomed_code, procedure_date, procedure_year
    from {{ ref('stg_procedures') }}
),

-- Gap 1 & 2: Diabetes quality measures
diabetes_services as (
    select
        m.member_id,
        max(case
            when p.snomed_code in ('43396009','444796002','59408-5')
            then 1 else 0
        end)                                            as had_a1c_test,
        max(case
            when p.snomed_code in ('252779009','6615001','410453006','410451008')
            then 1 else 0
        end)                                            as had_eye_exam,
        max(case
            when p.snomed_code in ('43396009','444796002')
            then p.procedure_date end)                  as last_a1c_date,
        max(case
            when p.snomed_code in ('252779009','6615001')
            then p.procedure_date end)                  as last_eye_exam_date
    from members m
    left join procedures p on m.member_id = p.member_id
    where m.cc_diabetes = 1
    group by m.member_id
),

-- Gap 3: Medication review for polypharmacy patients
med_review_services as (
    select
        m.member_id,
        max(case
            when p.snomed_code in ('182836005','428191000124101','reconcil')
            then 1 else 0
        end)                                            as had_med_review,
        max(case
            when p.snomed_code in ('182836005','428191000124101')
            then p.procedure_date end)                  as last_med_review_date
    from members m
    left join procedures p on m.member_id = p.member_id
    where m.distinct_drugs >= 5
    group by m.member_id
),

-- Gap 4: 30-day readmissions from encounters
inpatient_admits as (
    select
        member_id,
        service_date                                    as admit_date,
        service_end_date                                as discharge_date,
        lag(service_end_date) over (
            partition by member_id
            order by service_date
        )                                               as prior_discharge_date
    from {{ ref('stg_encounters') }}
    where claim_type = 'inpatient'
),

readmission_flags as (
    select
        member_id,
        max(case
            when prior_discharge_date is not null
            and date_diff(admit_date, prior_discharge_date, day) between 1 and 30
            then 1 else 0
        end)                                            as had_readmission,
        max(case
            when prior_discharge_date is not null
            and date_diff(admit_date, prior_discharge_date, day) between 1 and 30
            then admit_date end)                        as readmission_date
    from inpatient_admits
    group by member_id
),

-- Union all gaps
diabetes_a1c as (
    select
        m.member_id,
        m.measurement_year,
        'diabetes_a1c'                                  as gap_type,
        'HbA1c Testing — Diabetes'                     as gap_label,
        case when ds.had_a1c_test = 1 then 0 else 1 end as gap_open,
        ds.last_a1c_date                                as last_service_date,
        'Diabetic members without HbA1c measurement procedure' as gap_definition
    from members m
    inner join diabetes_services ds on m.member_id = ds.member_id
    where m.cc_diabetes = 1
),

diabetes_eye as (
    select
        m.member_id,
        m.measurement_year,
        'diabetes_eye_exam'                             as gap_type,
        'Retinal Eye Exam — Diabetes'                   as gap_label,
        case when ds.had_eye_exam = 1 then 0 else 1 end as gap_open,
        ds.last_eye_exam_date                           as last_service_date,
        'Diabetic members without retinal/fundoscopy exam' as gap_definition
    from members m
    inner join diabetes_services ds on m.member_id = ds.member_id
    where m.cc_diabetes = 1
),

med_review as (
    select
        m.member_id,
        m.measurement_year,
        'high_risk_med_review'                          as gap_type,
        'Medication Review — 5+ Active Drugs'           as gap_label,
        case when mr.had_med_review = 1 then 0 else 1 end as gap_open,
        mr.last_med_review_date                         as last_service_date,
        'Members on 5+ medications without medication reconciliation' as gap_definition
    from members m
    inner join med_review_services mr on m.member_id = mr.member_id
    where m.distinct_drugs >= 5
),

readmit as (
    select
        m.member_id,
        m.measurement_year,
        'readmission_30d'                               as gap_type,
        '30-Day All-Cause Readmission'                  as gap_label,
        coalesce(rf.had_readmission, 0)                 as gap_open,
        rf.readmission_date                             as last_service_date,
        'Inpatient admit within 30 days of prior discharge' as gap_definition
    from members m
    left join readmission_flags rf on m.member_id = rf.member_id
),

all_gaps as (
    select * from diabetes_a1c
    union all
    select * from diabetes_eye
    union all
    select * from med_review
    union all
    select * from readmit
)

select
    {{ dbt_utils.generate_surrogate_key(['member_id', 'gap_type', 'measurement_year']) }} as gap_id,
    member_id,
    measurement_year,
    gap_type,
    gap_label,
    gap_open,
    last_service_date,
    gap_definition,
    current_timestamp() as _loaded_at
from all_gaps
