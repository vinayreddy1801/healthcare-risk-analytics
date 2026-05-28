# Complete Setup Guide — healthcare_risk Portfolio Project (Windows PowerShell Edition)
> Follow every step in order. Each section tells you exactly what to type and what to expect on Windows.

---

## 🚨 CRITICAL BEFORE YOU START — Move Out of OneDrive!
Working inside a cloud-synced folder like **OneDrive** is the number one cause of local development failures. Python virtual environments (`.venv`), git indexes, and `dbt` local compilation caches create thousands of tiny, fast-changing files that trigger OneDrive lock conflicts, permission errors, and sync loops.

Before doing anything else, move your project directory to a clean local path (e.g., `C:\projects\healthcare_risk`).

### How to Move the Project:
1. Open a new **PowerShell** window.
2. Run the following commands to create a clean folder and copy your files over:
```powershell
# 1. Create a project directory outside of OneDrive
New-Item -ItemType Directory -Force -Path "C:\projects"

# 2. Copy the portfolio folder to the new clean path
Copy-Item -Path "C:\Users\vinay\OneDrive - UNT System\Portfolio_Projects\Healthcare Risk Portfolio" -Destination "C:\projects\healthcare_risk" -Recurse -Force

# 3. Change directory to your new clean workspace
cd "C:\projects\healthcare_risk"
```
> [!IMPORTANT]
> From this point forward, perform all commands and code edits inside **`C:\projects\healthcare_risk`**. Open this new path in VS Code (`File` -> `Open Folder`).

---

## Before You Start — Tool Checklist
Verify you have the following installed on your machine:
- **Python 3.10+** — check: `python --version`
- **Git** — check: `git --version`
- **Google Cloud CLI (gcloud)** — check: `gcloud --version`
  - *If not installed, download the [Google Cloud CLI Installer for Windows](https://cloud.google.com/sdk/docs/install#windows) and run it.*

---

# PHASE 1 — Google Cloud Setup

## Step 1 — Log in to Google Cloud
```powershell
gcloud auth login
```
This opens a web browser window. Sign in with your Google account. When it says "You are now authenticated", close the browser and return to PowerShell.

## Step 2 — Create a GCP Project
Every GCP command requires a project. Create one with a globally unique ID (we will use `healthcare-risk-vinay`):
```powershell
gcloud projects create healthcare-risk-vinay --name="Healthcare Risk Analytics"
```
Set it as your active project:
```powershell
gcloud config set project healthcare-risk-vinay
```
Verify the active project:
```powershell
gcloud config get-value project
# Expected output: healthcare-risk-vinay
```

## Step 3 — Enable Billing
GCP requires a billing account linked to the project to run BigQuery load jobs and queries, even though your usage will remain well within the free-tier limit (10GB storage + 1TB query scanning per month).
1. Go to: https://console.cloud.google.com/billing
2. Select your new project `healthcare-risk-vinay`.
3. Click **Link a billing account** or **Create billing account**.
4. Input credit/debit card information (you will not be charged).

## Step 4 — Enable Required APIs
Activate the core data platform services in your project:
```powershell
gcloud services enable bigquery.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable bigquerystorage.googleapis.com
```

## Step 5 — Create BigQuery Datasets
Always prefix your datasets with your project ID when creating them to guarantee correct scope:
```powershell
bq mk --dataset --location=US healthcare-risk-vinay:raw
bq mk --dataset --location=US healthcare-risk-vinay:healthcare_risk
bq mk --dataset --location=US healthcare-risk-vinay:healthcare_risk_dev
bq mk --dataset --location=US healthcare-risk-vinay:audit
```
Verify they were successfully created:
```powershell
bq ls healthcare-risk-vinay:
# Should display: raw, healthcare_risk, healthcare_risk_dev, audit
```

## Step 6 — Create GCS Bucket
Create a globally unique Cloud Storage bucket to stage raw data:
```powershell
gsutil mb -l US gs://healthcare-risk-raw-vinay
```

## Step 7 — Set up Application Default Credentials (ADC)
This allows your local Python environment (dbt, Streamlit) to authenticate securely with BigQuery:
```powershell
gcloud auth application-default login
gcloud auth application-default set-quota-project healthcare-risk-vinay
```

---

# PHASE 2 — Environment & Configurations

## Step 8 — Set PowerShell Environment Variables
Rather than typing environment variables repeatedly, set them in your active PowerShell session:
```powershell
$env:GCP_PROJECT_ID="healthcare-risk-vinay"
$env:GCS_BUCKET="healthcare-risk-raw-vinay"
$env:DBT_PROJECT_DIR="C:\projects\healthcare_risk\dbt"
$env:DBT_PROFILES_DIR="C:\projects\healthcare_risk\dbt"
```

### 💡 Quality of Life Tip: Persist Variables Permanently
To avoid retyping these environment variables every time you open a new PowerShell terminal, add them to your user profile:
```powershell
# 1. Create a PowerShell profile if it doesn't exist
if (!(Test-Path $PROFILE)) { New-Item -Type File -Force $PROFILE }

# 2. Append the variables to your profile
@'
$env:GCP_PROJECT_ID="healthcare-risk-vinay"
$env:GCS_BUCKET="healthcare-risk-raw-vinay"
$env:DBT_PROJECT_DIR="C:\projects\healthcare_risk\dbt"
$env:DBT_PROFILES_DIR="C:\projects\healthcare_risk\dbt"
'@ | Add-Content $PROFILE
```

## Step 9 — Configure `.env` File
Create a `.env` file in the root of the moved project:
```powershell
Copy-Item .env.example .env
```
Open `.env` in VS Code and fill out the details:
```env
GCP_PROJECT_ID=healthcare-risk-vinay
GCS_BUCKET=healthcare-risk-raw-vinay
DBT_PROJECT_DIR=C:\projects\healthcare_risk\dbt
DBT_TARGET=dev
DBT_PROFILES_DIR=C:\projects\healthcare_risk\dbt
ALERT_EMAIL=vinay@example.com
```

## Step 10 — Configure and Copy `profiles.yml`
dbt looks for configurations in your user home directory. Copy the project profile there:
```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.dbt"
Copy-Item dbt\profiles.yml -Destination "$HOME\.dbt\profiles.yml"
```

## Step 11 — Create Python Virtual Environment
Initialize and activate your virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Upgrade pip and install dependencies:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Step 12 — Verify Authentication Early
Before downloading massive files or running transformations, run `dbt debug` inside the `dbt` folder to test authentication and paths:
```powershell
cd dbt
dbt debug
cd ..
```
Look for **`All connections passed`** at the bottom. If it fails, check your environment variables and ADC setup (see Troubleshooting).

---

# PHASE 3 — Download & Ingest CMS SynPUF Data

## Step 13 — Download CMS SynPUF Files
Go to the [CMS SynPUF DE-1 page](https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/SynPUFs/DE_Syn_PUF).
Download these **5 zip files** from **DE1 — 5% Sample 1**:
1. `DE1_0_2008_Beneficiary_Summary_File_Sample_1.zip`
2. `DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.zip`
3. `DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.zip`
4. `DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.zip`
5. `DE1_0_2008_to_2010_Prescription_Drug_Events_Sample_1.zip`

## Step 14 — Extract and Rename to Standard Files
Create a raw data directory:
```powershell
New-Item -ItemType Directory -Force -Path "C:\projects\healthcare_risk\data\raw"
```
Extract the `.csv` file inside each zip into `C:\projects\healthcare_risk\data\raw` and rename them exactly to:
* `beneficiary_summary.csv`
* `inpatient_claims.csv`
* `outpatient_claims.csv`
* `carrier_claims.csv`
* `pde_events.csv`

## Step 15 — Upload CSVs to Google Cloud Storage
Stage the CSVs to GCS so BigQuery can load them:
```powershell
cd C:\projects\healthcare_risk\data\raw

gsutil cp beneficiary_summary.csv gs://healthcare-risk-raw-vinay/synpuf/
gsutil cp inpatient_claims.csv gs://healthcare-risk-raw-vinay/synpuf/
gsutil cp outpatient_claims.csv gs://healthcare-risk-raw-vinay/synpuf/
gsutil cp carrier_claims.csv gs://healthcare-risk-raw-vinay/synpuf/
gsutil cp pde_events.csv gs://healthcare-risk-raw-vinay/synpuf/
```

## Step 16 — Load CSVs into BigQuery
> [!IMPORTANT]
> You **must** include `--allow_jagged_rows` and `--allow_quoted_newlines`. SynPUF Carrier and Outpatient files contain inconsistent columns (jagged rows) and line breaks within fields. Without these flags, BigQuery loads will fail.

Run these commands in PowerShell (each as a single line):
```powershell
bq load --autodetect --source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines --allow_jagged_rows healthcare-risk-vinay:raw.beneficiary_summary gs://healthcare-risk-raw-vinay/synpuf/beneficiary_summary.csv

bq load --autodetect --source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines --allow_jagged_rows healthcare-risk-vinay:raw.inpatient_claims gs://healthcare-risk-raw-vinay/synpuf/inpatient_claims.csv

bq load --autodetect --source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines --allow_jagged_rows healthcare-risk-vinay:raw.outpatient_claims gs://healthcare-risk-raw-vinay/synpuf/outpatient_claims.csv

bq load --autodetect --source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines --allow_jagged_rows healthcare-risk-vinay:raw.carrier_claims gs://healthcare-risk-raw-vinay/synpuf/carrier_claims.csv

bq load --autodetect --source_format=CSV --skip_leading_rows=1 --allow_quoted_newlines --allow_jagged_rows healthcare-risk-vinay:raw.pde_events gs://healthcare-risk-raw-vinay/synpuf/pde_events.csv
```
Confirm success:
```powershell
bq ls healthcare-risk-vinay:raw
# Should show 5 tables loaded successfully
```

---

# PHASE 4 — Run the dbt Pipeline (with Layered Gates)

## Step 17 — Initialize Data Quality Log Table
Inject your active GCP project ID into the audit table DDL script:
```powershell
cd C:\projects\healthcare_risk
((Get-Content sql\audit_dq_run_log.sql) -replace 'YOUR_PROJECT_ID', 'healthcare-risk-vinay') | Set-Content sql\audit_dq_run_log.sql
```
Run the query to create the audit schema and logging table in BigQuery:
```powershell
Get-Content sql\audit_dq_run_log.sql -Raw | bq query --use_legacy_sql=false
```

## Step 18 — Run and Test the dbt Pipeline in Layers
Running dbt in sequential layers with testing gates prevents cascading model failures and isolates compilation bugs.

Make sure virtual environment is active (`.\.venv\Scripts\Activate.ps1`), navigate to `dbt`, and execute the following:
```powershell
cd C:\projects\healthcare_risk\dbt

# 1. Install dbt Packages
dbt deps

# 2. Seed clinical condition mapping reference file
dbt seed

# 3. RUN & TEST Staging Layer (Validates base views)
dbt run --select staging
dbt test --select staging

# 4. RUN Intermediate Layer (Validates business rules)
dbt run --select intermediate

# 5. RUN & TEST Mart Layer (Validates final gold analytics tables)
dbt run --select marts
dbt test --select marts
```

## Step 19 — Generate Docs
Generate documentation and visual dependency graphs:
```powershell
dbt docs generate
dbt docs serve
```
*(Press `Ctrl + C` in PowerShell to stop the local documentation server).*

---

# PHASE 5 — Streamlit Analytics Dashboard

## Step 20 — Create Streamlit Secrets Configuration
Create a local secret file so Streamlit connects to BigQuery under your project ID:
```powershell
cd C:\projects\healthcare_risk
New-Item -ItemType Directory -Force -Path streamlit\.streamlit
@'
[gcp]
project_id = "healthcare-risk-vinay"
'@ | Set-Content streamlit\.streamlit\secrets.toml
```

## Step 21 — Run the Dashboard
Ensure virtual environment is active, navigate to the streamlit directory, and run:
```powershell
cd C:\projects\healthcare_risk\streamlit
streamlit run app.py
```
Your browser will open automatically to `http://localhost:8501`. Take screenshots of the four tabs (Population Overview, Care Gap Analysis, Cost & Utilization, Provider Scorecard) for your portfolio!

---

# Troubleshooting Common Windows Errors

### 1. `dbt debug` fails / "database connection failed"
* **Check Environment Variables:** Make sure you ran the PowerShell environment configuration (Step 8). Run `dir env:` to see if `GCP_PROJECT_ID` is displayed.
* **Re-auth Application Default Credentials:** Run:
  ```powershell
  gcloud auth application-default login --no-browser
  ```
  (Or standard `gcloud auth application-default login` if in an interactive shell).

### 2. `bq load` fails on Carrier or Outpatient claims
* **Missing Jagged Rows Flag:** SynPUF carrier files have different column counts on different rows due to missing fields. Double check that you are running `bq load` with `--allow_jagged_rows` and `--allow_quoted_newlines` flags.

### 3. Execution Policy Error when activating `.venv`
* If PowerShell refuses to run the activation script with a permission error:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
  .\.venv\Scripts\Activate.ps1
  ```

### 4. Streamlit Dashboard displays blank charts
* Verify that the final marts tables have data inside BigQuery by running:
  ```powershell
  bq query --use_legacy_sql=false "SELECT COUNT(*) FROM healthcare-risk-vinay.healthcare_risk_dev.mart_member_risk_profile"
  ```
* If count is 0, make sure you ran the mart models (`dbt run --select marts`).

---

# Quick Reference — Common Command Board
Bookmark this section for day-to-day work!

```powershell
# 1. Activate Environment (Every session)
cd C:\projects\healthcare_risk
.\.venv\Scripts\Activate.ps1

# 2. Build full DBT pipeline
cd C:\projects\healthcare_risk\dbt
dbt deps && dbt seed && dbt run && dbt test

# 3. Launch Documentation
dbt docs generate && dbt docs serve

# 4. Launch Streamlit
cd C:\projects\healthcare_risk\streamlit
streamlit run app.py
```
