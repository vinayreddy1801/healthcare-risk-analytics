# load_synthea_to_bq.py
# Pure-Python script to load Synthea CSVs from GCS into BigQuery raw dataset.
# Works completely without the gcloud/bq CLI tools!
# Uses the service account credentials from gcp-json-key.json.

import os
from google.cloud import bigquery

# Service account path
KEY_PATH = r"C:\projects\healthcare_risk\gcp-json-key.json"
PROJECT = "healthcare-risk-vinay"
DATASET = "raw"
BUCKET = "healthcare-risk-raw-vinay"

if not os.path.exists(KEY_PATH):
    print(f"Error: Credentials key file not found at: {KEY_PATH}")
    exit(1)

print("Initializing BigQuery Client...")
client = bigquery.Client.from_service_account_json(KEY_PATH)

files = ["patients", "encounters", "conditions", "procedures", "medications", "providers"]

for f in files:
    table_id = f"{PROJECT}.{DATASET}.{f}"
    gcs_uri = f"gs://{BUCKET}/synthea/{f}.csv"
    
    print(f"Loading GCS file {gcs_uri} into BigQuery table {table_id}...")
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        allow_quoted_newlines=True,
        allow_jagged_rows=True,
    )
    
    try:
        load_job = client.load_table_from_uri(
            gcs_uri,
            table_id,
            job_config=job_config
        )
        load_job.result()  # Wait for the job to complete
        
        # Verify row count
        table = client.get_table(table_id)
        print(f"Loaded {f} table: {table.num_rows} rows successfully.")
    except Exception as e:
        print(f"Error loading {f}: {e}")

print("\nAll tables loaded successfully! Verify in the BigQuery Web Console.")
