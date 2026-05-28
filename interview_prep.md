# Healthcare Risk Analytics — Interview Preparation & Architectural Pivots
> **Demonstrating Technical Leadership and Adaptability in Analytics Engineering**

This document details the critical architectural decisions and pivots made during the development of this project. Use these points during interviews with healthcare analytics companies (like Arcadia, Innovaccer, Health Catalyst, or payers/providers) to demonstrate real-world engineering judgment and technical maturity.

---

## 🚀 The Two Major Architectural Pivots

### Pivot 1: The Dataset Switch (CMS SynPUF ──► Synthea)
* **The Situation:** The CMS public download links for the 2008–2010 Synthetic Public Use Files (SynPUF) are unstable, frequently broken, and contain highly legacy clinical schema (e.g., ICD-9 codes, hardcoded chronic condition flags).
* **The Pivot:** Migrated the entire pipeline to **Synthea**, a modern, open-source synthetic patient generator that simulates longitudinal patient records (EHR data).
* **Interview Talking Points:**
  > *"When the public CMS SynPUF sources became unstable, I proactively pivoted the entire pipeline to Synthea. In real-world healthcare analytics, data sources are highly volatile due to contract changes, vendor pipeline failures, or schema migrations. I refactored the pipeline from a claims-based layout (separate inpatient, outpatient, and professional tables) to an encounter-centric unified record schema. This demonstrates my ability to design resilient pipelines that focus on core entity structures rather than fragile raw layouts."*

### Pivot 2: The Code Mapping Shift (ICD-10 Ranges ──► SNOMED-CT Exact Matching)
* **The Situation:** CMS SynPUF claims rely on ICD-9/10 billing codes, which are traditionally compared using alphabetical ranges (e.g., `E11` to `E13` for diabetes). Synthea uses **SNOMED-CT** (Clinical Terms) and **RxNorm** codes to capture direct clinical diagnoses and pharmacy events.
* **The Pivot:** Replaced the range-matching SQL macros with an exact-match seed table (`snomed_condition_map.csv`), mapping clinical SNOMED-CT codes directly to Hierarchical Condition Categories (HCC) and risk weights.
* **Interview Talking Points:**
  > *"In my original model, I used lexicographical range matching for ICD-10, which is standard for billing claims but can lead to false positives if clinical definitions shift. When pivoting to Synthea, I designed a seed-driven exact matching system using SNOMED-CT codes. In clinical settings, SNOMED is the gold standard for clinical data capture in EHRs, while ICD is for billing. Mapping SNOMED directly to Hierarchical Condition Categories (HCCs) allows care managers to identify risk tiers and quality gaps weeks or months before a bill is finalized and coded as ICD. This shows I understand both the clinical and financial sides of healthcare data."*

---

## 🛠️ Deep-Dive Technical Decisions

### 1. Unified Staging & Unified Encounter Spine (`int_claims_unioned`)
* **Engineering Decision:** Synthea merges inpatient, outpatient, emergency, and office visits into a single `encounters` source. I modeled this directly as a unified staging model `stg_encounters` and then generated a unified claims/procedures spine `int_claims_unioned`.
* **Talking Point:** 
  > *"Instead of building separate processing pipelines for different claim types, I unioned encounters, conditions, and procedures into a single claims-line spine. This unified spine uses dbt_utils to generate a secure surrogate key on `[claim_id, dx_code, procedure_code, member_id]`, which guarantees referential integrity downstream while allowing consistent cross-cutting calculations for total cost, readmissions, and procedures."*

### 2. Recalculating Cost PMPM (Annual ──► Lifetime Expenses)
* **Engineering Decision:** SynPUF models costs in narrow 12-month frames. Synthea captures a patient's lifetime healthcare expenses under `total_healthcare_expenses`. I refactored the PMPM calculations in `mart_member_risk_profile` to estimate PMPM by dividing lifetime expenses by patient age and active months.
* **Talking Point:**
  > *"Because EHR data captures the entire lifecycle of a patient, we cannot calculate PMPM using simple annual limits. I designed a cost engine that calculates lifetime PMPM by evaluating a patient's date of birth and date of death (or current date) to establish an enrollment month denominator. This longitudinal approach is exactly how value-based care engineers estimate the risk-adjusted Lifetime Value (LTV) of chronic patients in Medicare Advantage."*

### 3. Production-Ready Service Account Authentication
* **Engineering Decision:** Switched the local development authentication from user-level OAuth/ADC to a secure Service Account Key File (`gcp-json-key.json`).
* **Talking Point:**
  > *"On Windows environments, local CLI user authentication (OAuth) is notoriously fragile and difficult to automate. I designed a secure Service Account Key authentication model. By storing credentials in a local JSON key (which is strictly excluded from Git via `.gitignore`) and binding it to the standard `GOOGLE_APPLICATION_CREDENTIALS` environment variable, the pipeline is immediately portable, container-friendly, and ready to deploy directly to a production scheduler like Apache Airflow or Cloud Composer without changing a single line of code."*
