# schema_check.py
from google.cloud import bigquery

client = bigquery.Client.from_service_account_json("C:/projects/healthcare_risk/gcp-json-key.json")

tables = ["procedures", "encounters", "conditions", "patients", "medications", "providers"]

for tab in tables:
    try:
        t = client.get_table(f"healthcare-risk-vinay.raw.{tab}")
        fields = [f.name for f in t.schema]
        print(f"Table raw.{tab} fields: {fields}")
    except Exception as e:
        print(f"Error reading raw.{tab}: {e}")
