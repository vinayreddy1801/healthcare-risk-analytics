"""
dag_synpuf_ingest.py
--------------------
Downloads CMS Medicare SynPUF CSV files, uploads to GCS,
and loads into BigQuery raw tables.

Schedule: Monthly on the 1st at 2am UTC.
Triggers: dag_dbt_pipeline on successful completion.
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GCP_PROJECT_ID   = os.getenv("GCP_PROJECT_ID", "your-gcp-project")
GCS_BUCKET       = os.getenv("GCS_BUCKET", "healthcare-risk-raw")
BQ_DATASET_RAW   = "raw"
DOWNLOAD_DIR     = "/tmp/synpuf"

# CMS SynPUF DE1 Sample 1 — public URLs (5% sample)
SYNPUF_FILES = {
    "beneficiary_summary": (
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/"
        "SynPUFs/Downloads/DE1_0_2008_Beneficiary_Summary_File_Sample_1.zip",
        "beneficiary_summary.csv"
    ),
    "inpatient_claims": (
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/"
        "SynPUFs/Downloads/DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.zip",
        "inpatient_claims.csv"
    ),
    "outpatient_claims": (
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/"
        "SynPUFs/Downloads/DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.zip",
        "outpatient_claims.csv"
    ),
    "carrier_claims": (
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/"
        "SynPUFs/Downloads/DE1_0_2008_to_2010_Carrier_Claims_Sample_1A.zip",
        "carrier_claims.csv"
    ),
    "pde_events": (
        "https://www.cms.gov/Research-Statistics-Data-and-Systems/Downloadable-Public-Use-Files/"
        "SynPUFs/Downloads/DE1_0_2008_to_2010_Prescription_Drug_Events_Sample_1.zip",
        "pde_events.csv"
    ),
}

BQ_SCHEMAS = {
    "beneficiary_summary": [
        {"name": "DESYNPUF_ID",          "type": "STRING"},
        {"name": "BENE_BIRTH_DT",         "type": "STRING"},
        {"name": "BENE_DEATH_DT",         "type": "STRING"},
        {"name": "BENE_SEX_IDENT_CD",     "type": "STRING"},
        {"name": "BENE_RACE_CD",          "type": "STRING"},
        {"name": "BENE_ESRD_IND",         "type": "STRING"},
        {"name": "SP_STATE_CODE",         "type": "STRING"},
        {"name": "BENE_COUNTY_CD",        "type": "STRING"},
        {"name": "BENE_HI_CVRAGE_TOT_MONS","type": "STRING"},
        {"name": "BENE_SMI_CVRAGE_TOT_MONS","type": "STRING"},
        {"name": "BENE_HMO_CVRAGE_TOT_MONS","type": "STRING"},
        {"name": "PLAN_CVRG_MOS_NUM",     "type": "STRING"},
        {"name": "SP_ALZHDMTA",           "type": "STRING"},
        {"name": "SP_CHF",                "type": "STRING"},
        {"name": "SP_CHRNKIDN",           "type": "STRING"},
        {"name": "SP_CNCR",               "type": "STRING"},
        {"name": "SP_COPD",               "type": "STRING"},
        {"name": "SP_DEPRESSN",           "type": "STRING"},
        {"name": "SP_DIABETES",           "type": "STRING"},
        {"name": "SP_ISCHMCHT",           "type": "STRING"},
        {"name": "SP_OSTEOPRS",           "type": "STRING"},
        {"name": "SP_RA_OA",              "type": "STRING"},
        {"name": "SP_STRKETIA",           "type": "STRING"},
        {"name": "MEDREIMB_IP",           "type": "FLOAT64"},
        {"name": "BENRES_IP",             "type": "FLOAT64"},
        {"name": "PPPYMT_IP",             "type": "FLOAT64"},
        {"name": "MEDREIMB_OP",           "type": "FLOAT64"},
        {"name": "BENRES_OP",             "type": "FLOAT64"},
        {"name": "PPPYMT_OP",             "type": "FLOAT64"},
        {"name": "MEDREIMB_CAR",          "type": "FLOAT64"},
        {"name": "BENRES_CAR",            "type": "FLOAT64"},
        {"name": "PPPYMT_CAR",            "type": "FLOAT64"},
    ],
}

# ---------------------------------------------------------------------------
# Default args
# ---------------------------------------------------------------------------
default_args = {
    "owner": "analytics-engineering",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": [os.getenv("ALERT_EMAIL", "analytics@yourcompany.com")],
    "email_on_retry": False,
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def check_gcs_bucket(**context):
    """Verify GCS bucket exists and is writable."""
    from google.cloud import storage
    client = storage.Client(project=GCP_PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET)
    if not bucket.exists():
        raise ValueError(f"GCS bucket {GCS_BUCKET} does not exist. Create it first.")
    log.info(f"✓ GCS bucket {GCS_BUCKET} confirmed accessible")


def download_synpuf_files(**context):
    """Download SynPUF zip files from CMS and extract CSVs to local /tmp."""
    import requests
    import zipfile

    Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
    ds = context["ds"]

    for table_name, (url, csv_name) in SYNPUF_FILES.items():
        zip_path = f"{DOWNLOAD_DIR}/{table_name}.zip"
        csv_path = f"{DOWNLOAD_DIR}/{csv_name}"

        log.info(f"Downloading {table_name} from CMS...")
        response = requests.get(url, timeout=300, stream=True)
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        log.info(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, "r") as z:
            # Find the CSV inside the zip
            csv_files = [n for n in z.namelist() if n.endswith(".csv")]
            if not csv_files:
                raise FileNotFoundError(f"No CSV found in {zip_path}")
            z.extract(csv_files[0], DOWNLOAD_DIR)
            extracted = f"{DOWNLOAD_DIR}/{csv_files[0]}"
            if extracted != csv_path:
                Path(extracted).rename(csv_path)

        log.info(f"✓ {table_name}: {csv_path}")

    context["task_instance"].xcom_push(key="download_date", value=ds)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------
with DAG(
    dag_id="dag_synpuf_ingest",
    description="Download CMS SynPUF files → GCS → BigQuery raw tables",
    default_args=default_args,
    schedule_interval="0 2 1 * *",   # Monthly on 1st at 2am UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["healthcare", "ingest", "synpuf"],
    doc_md=__doc__,
) as dag:

    check_bucket = PythonOperator(
        task_id="check_gcs_bucket_exists",
        python_callable=check_gcs_bucket,
    )

    download_files = PythonOperator(
        task_id="download_synpuf_files",
        python_callable=download_synpuf_files,
        execution_timeout=timedelta(hours=2),
    )

    # Upload each file to GCS
    upload_tasks = []
    for table_name, (_, csv_name) in SYNPUF_FILES.items():
        upload = LocalFilesystemToGCSOperator(
            task_id=f"upload_{table_name}_to_gcs",
            src=f"{DOWNLOAD_DIR}/{csv_name}",
            dst=f"synpuf/{{{{ ds }}}}/{csv_name}",
            bucket=GCS_BUCKET,
        )
        upload_tasks.append(upload)

    # Load each file from GCS to BigQuery
    load_tasks = []
    for table_name, (_, csv_name) in SYNPUF_FILES.items():
        load = BigQueryInsertJobOperator(
            task_id=f"load_bq_{table_name}",
            configuration={
                "load": {
                    "sourceUris": [f"gs://{GCS_BUCKET}/synpuf/{{{{ ds }}}}/{csv_name}"],
                    "destinationTable": {
                        "projectId": GCP_PROJECT_ID,
                        "datasetId": BQ_DATASET_RAW,
                        "tableId": table_name,
                    },
                    "sourceFormat": "CSV",
                    "skipLeadingRows": 1,
                    "writeDisposition": "WRITE_TRUNCATE",
                    "autodetect": True,
                    "allowQuotedNewlines": True,
                    "allowJaggedRows": True,
                }
            },
        )
        load_tasks.append(load)

    trigger_dbt = TriggerDagRunOperator(
        task_id="trigger_dbt_pipeline",
        trigger_dag_id="dag_dbt_pipeline",
        wait_for_completion=False,
    )

    # Wire dependencies
    check_bucket >> download_files
    download_files >> upload_tasks
    for upload, load in zip(upload_tasks, load_tasks):
        upload >> load
    load_tasks >> trigger_dbt
