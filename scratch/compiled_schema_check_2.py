# compiled_schema_check_2.py
from google.cloud import bigquery

client = bigquery.Client.from_service_account_json("C:/projects/healthcare_risk/gcp-json-key.json")

datasets = ["healthcare_risk_dev_staging", "healthcare_risk_dev", "healthcare_risk_staging"]
views = ["stg_encounters", "stg_conditions", "stg_procedures", "stg_medications", "stg_members"]

for d in datasets:
    print(f"Checking dataset: {d}")
    for v in views:
        try:
            t = client.get_table(f"healthcare-risk-vinay.{d}.{v}")
            fields = [(f.name, f.field_type) for f in t.schema]
            print(f"  View {v} fields: {fields}\n")
        except Exception as e:
            # print(f"  Error reading view {v}: {e}\n")
            pass
