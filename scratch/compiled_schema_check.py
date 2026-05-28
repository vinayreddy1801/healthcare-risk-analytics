# compiled_schema_check.py
from google.cloud import bigquery

client = bigquery.Client.from_service_account_json("C:/projects/healthcare_risk/gcp-json-key.json")

views = ["stg_encounters", "stg_conditions", "stg_procedures", "stg_medications", "stg_members"]

for v in views:
    try:
        t = client.get_table(f"healthcare-risk-vinay.healthcare_risk_dev.{v}")
        fields = [(f.name, f.field_type) for f in t.schema]
        print(f"View {v} fields: {fields}\n")
    except Exception as e:
        print(f"Error reading view {v}: {e}\n")
