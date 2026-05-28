# healthcare_risk — Claims-Based Population Health Risk Stratification Pipeline

> **A production-style analytics engineering project** demonstrating end-to-end population health analytics on CMS Medicare claims data — from raw ingest through risk-stratified marts to an executive dashboard.

---

## Project Overview

This pipeline ingests CMS Medicare Synthetic Public Use File (SynPUF) claims data, transforms it through a dbt warehouse-first model, and surfaces a population health risk stratification dashboard. The central analytical question is: **which Medicare beneficiaries are at risk of becoming high-cost, high-need patients — and where are their unaddressed care gaps?**

This mirrors the core product logic of companies like Arcadia, Innovaccer, and Health Catalyst: taking claims data, applying condition identification algorithms, stratifying by risk, and identifying actionable quality gaps.

---

## Clinical Context

**HCC Risk Adjustment** — Hierarchical Condition Categories (HCC) is CMS's ICD-10-based risk adjustment model used across Medicare Advantage. Each ICD-10 code maps to a condition category; categories roll up to HCCs; each HCC has a relative risk weight. A member's RAF (Risk Adjustment Factor) score is the sum of their demographic factor plus confirmed condition weights. Higher scores predict higher expected cost. This pipeline implements a simplified HCC-adjacent scoring model using publicly available CMS HCC mappings — not CMS-certified, but using the same ICD-10 grouping logic.

**HEDIS Care Gaps** — HEDIS (Healthcare Effectiveness Data and Information Set) is NCQA's set of standardized quality measures used by payers to assess care quality. Key measures include diabetes HbA1c testing, retinal exams, medication adherence, and 30-day readmissions. This pipeline implements HEDIS-adjacent versions of four measures using claims data. These are not NCQA-validated but follow the same numerator/denominator logic.

**Population Risk Stratification** — Segmenting a patient population into risk tiers (low, moderate, rising cost, high) enables health plans and care management programs to target interventions. High-risk members (top 5% of cost/complexity) typically account for 50%+ of total spend.

---

## Dataset: CMS Medicare SynPUF

CMS released synthetic Medicare claims files (Synthetic Public Use Files) that mirror the structure of real Medicare data. The files include:

| File | Description | Key Fields |
|---|---|---|
| Beneficiary Summary | Demographics + chronic flags + annual costs | Age, sex, 10 condition flags, total reimbursement |
| Inpatient Claims | Hospital admissions | ICD-9 dx codes, DRG, admission/discharge dates |
| Outpatient Claims | Facility outpatient | ICD-9 dx codes, HCPCS/CPT codes |
| Carrier Claims | Professional/physician | CPT codes, provider NPI, ICD-9 dx |
| PDE Events | Part D pharmacy | NDC codes, days supply, drug cost |

**SynPUF vs Real Medicare:** SynPUF preserves the file structure and field names of real Medicare claims but uses synthetic beneficiary data. Clinical patterns are realistic but not statistically representative of the actual Medicare population. All findings are illustrative, not actionable.

---

## Architecture

```
CMS SynPUF CSVs (public)
         │
         ▼
  [GCS Bucket]  ◄── Airflow: dag_synpuf_ingest.py
         │
         ▼
  [BigQuery: raw.*]
  raw.beneficiary_summary
  raw.inpatient_claims
  raw.outpatient_claims
  raw.carrier_claims
  raw.pde_events
         │
         ▼
  [dbt: Staging Layer]  ← type casting, null handling, column standardization
  stg_members
  stg_inpatient_claims   (dx codes unpivoted to long format)
  stg_outpatient_claims  (dx + HCPCS unpivoted)
  stg_carrier_claims
  stg_rx_claims
         │
         ▼
  [dbt: Intermediate Layer]  ← business logic, ICD-10 grouping
  int_claims_unioned         (all claim types in one spine)
  int_dx_code_flags          (ICD-10 → condition category + HCC weight)
  int_member_chronic_flags   (CCW-algorithm chronic condition pivot)
         │
         ▼
  [dbt: Mart Layer]  ← analytics-ready tables
  mart_member_risk_profile   (risk tier, HCC score, PMPM cost per member)
  mart_care_gaps             (HEDIS-adjacent gap flags)
  mart_cost_utilization      (cost/util aggregated by risk tier)
  mart_provider_efficiency   (NPI-level scorecard + quadrant)
         │
         ▼
  [Streamlit Dashboard]
  Tab 1: Population Overview
  Tab 2: Care Gap Analysis
  Tab 3: Cost & Utilization
  Tab 4: Provider Efficiency
         │
  [Airflow Orchestration]
  dag_synpuf_ingest.py    → GCS ingest + BQ load
  dag_dbt_pipeline.py     → dbt run + test + docs
  dag_data_quality.py     → row counts + null rates + freshness + audit log
         │
  [audit.dq_run_log]      ← BigQuery audit table for all DQ runs
```

---

## dbt Model Lineage

```
raw.beneficiary_summary ──► stg_members ──────────────────────────────────┐
raw.inpatient_claims ────► stg_inpatient_claims ──┐                        │
raw.outpatient_claims ───► stg_outpatient_claims ─┼─► int_claims_unioned ─┼─► int_dx_code_flags ──► int_member_chronic_flags ─┐
raw.carrier_claims ──────► stg_carrier_claims ────┘          │             │                                                   │
raw.pde_events ──────────► stg_rx_claims ─────────────────── │ ────────────│────────────────────────────────────────────────── │
                                                              │             │                                                   │
                                         seeds/icd10_condition_map ────────┘                                                   │
                                                              │                                                                 │
                                                              └──────────────────────────────────► mart_member_risk_profile ◄──┘
                                                                                                            │
                                                              int_dx_code_flags ──────────────► mart_care_gaps
                                                                                                            │
                                                              mart_member_risk_profile ─────► mart_cost_utilization
                                                                                                            │
                                                              int_dx_code_flags ──────────── mart_provider_efficiency
```

---

## Key Technical Decisions

- **Claims union pattern over separate fact tables** — unioning inpatient, outpatient, and carrier claims into a single spine (`int_claims_unioned`) enables consistent cross-claim analytics (total cost, utilization rates) without complex joins downstream. The tradeoff is slightly larger intermediate model size.

- **Seed file for ICD-10 condition mapping** — the `icd10_condition_map.csv` seed externalizes condition logic from SQL, making it auditable, version-controlled, and updatable without model changes. This mirrors how production health analytics teams maintain clinical code sets separately from transformation logic.

- **Ephemeral intermediates** — intermediate models are materialized as ephemeral (compiled inline) to avoid BigQuery storage costs during development. In production, promote to views or tables based on query frequency.

- **Separate DQ DAG from dbt DAG** — data quality checks run in a distinct Airflow DAG, writing to an audit log table. This separates transformation concerns from validation concerns, and allows DQ checks to run on any schedule independent of the pipeline.

- **HEDIS-adjacent, not HEDIS-certified** — the care gap measures approximate HEDIS logic but do not meet NCQA certification requirements (no enrollment verification, no hybrid method, no exclusion logic). This is disclosed explicitly in the dashboard and README — a deliberate choice that demonstrates intellectual honesty that interviewers value.

---

## ICD-10 Mapping Logic

The `icd10_in_range` macro handles ICD-10 range matching:

```sql
-- Usage: {{ icd10_in_range('dx_code', 'E11', 'E13') }}
-- Expands to: (dx_code >= 'E11' and dx_code <= 'E13')
{% macro icd10_in_range(col, start_code, end_code) %}
    ({{ col }} >= '{{ start_code }}' and {{ col }} <= '{{ end_code }}')
{% endmacro %}
```

ICD codes sort lexicographically, so range comparisons work correctly for both ICD-9 and ICD-10 within a code system. The seed file includes both ICD-9 (used in SynPUF) and ICD-10 ranges for production readiness.

---

## Care Gap Definitions

| Gap Name | Eligible Denominator | Numerator (met = no gap) | CPT Codes Used |
|---|---|---|---|
| `diabetes_a1c` | Diabetic members (ICD dx confirmed) | HbA1c lab test in measurement year | 83036, 83037, 83038 |
| `diabetes_eye_exam` | Diabetic members | Retinal/dilated eye exam in measurement year | 92002, 92004, 92012, 92014, 92228, 92229 |
| `high_risk_med_review` | Members with 5+ distinct NDC/drugs | Medication therapy review in year | 99605, 99606, 99607 |
| `readmission_30d` | Members with ≥1 inpatient admit | No inpatient readmit within 30 days of discharge | N/A (claims pattern) |

---

## Setup Instructions

### Prerequisites
- Python 3.10+
- Google Cloud account with BigQuery and GCS enabled
- Airflow 2.6+ (local, Astronomer, or Cloud Composer)

### 1. GCP Setup
```bash
# Create GCP project and enable APIs
gcloud projects create your-project-id
gcloud config set project your-project-id
gcloud services enable bigquery.googleapis.com storage.googleapis.com

# Create BigQuery datasets
bq mk --dataset your-project-id:raw
bq mk --dataset your-project-id:healthcare_risk
bq mk --dataset your-project-id:audit

# Create GCS bucket
gsutil mb -l US gs://healthcare-risk-raw
```

### 2. Project Setup
```bash
git clone <this-repo>
cd healthcare_risk
bash setup.sh
```

### 3. dbt Setup
```bash
cd dbt
cp profiles.yml ~/.dbt/profiles.yml   # Edit with your project ID
dbt deps
dbt seed
dbt run
dbt test
dbt docs generate && dbt docs serve
```

### 4. Download SynPUF Data
Download DE1 Sample 1 files from:
https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs

Upload to BigQuery:
```bash
bq load --autodetect --source_format=CSV \
  your-project-id:raw.beneficiary_summary \
  gs://healthcare-risk-raw/synpuf/DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv
# Repeat for each file
```

### 5. Streamlit Dashboard
```bash
cd streamlit
pip install -r requirements.txt
# Add GCP credentials to .streamlit/secrets.toml
streamlit run app.py
```

---

## What This Is Not

This project is intentionally transparent about its limitations:

- **Not CMS-certified HCC scoring** — the risk scores use CMS HCC mappings but are not calculated using the official CMS-HCC model software. Do not use for actual risk adjustment payments.
- **Not NCQA-validated HEDIS measures** — care gap logic approximates HEDIS but omits enrollment verification, hybrid method, and NCQA-required exclusion logic.
- **Synthetic data only** — SynPUF data is structurally realistic but statistically synthetic. No findings reflect actual Medicare population health trends.
- **ICD-9, not ICD-10** — SynPUF uses ICD-9 codes. The model is built to handle ICD-10 in production; the seed file includes both.

These limitations are documented to demonstrate the kind of intellectual rigor expected in production health analytics environments.

---

## Skills Demonstrated

- **Claims data modeling** — inpatient, outpatient, carrier, pharmacy claim types; dx code unpivoting; claim spine patterns
- **ICD-10 / CPT coding** — condition category mapping, HCC weight assignment, CPT-based quality measure logic  
- **HEDIS-adjacent analytics** — care gap identification, numerator/denominator logic, member attribution
- **HCC risk adjustment** — simplified RAF scoring, condition hierarchy, risk tier classification
- **dbt** — staging/intermediate/mart layering, ephemeral models, seeds, macros, schema tests, dbt-utils
- **BigQuery** — window functions, UNNEST for array unpivoting, partitioned/clustered tables
- **Airflow** — DAG design, task dependencies, TriggerDagRunOperator, BranchPythonOperator, audit logging
- **Streamlit** — multi-tab dashboard, Plotly charts, BigQuery integration, caching
- **Regulated data patterns** — source-to-target reconciliation, audit logging, lineage documentation
