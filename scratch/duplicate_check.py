# duplicate_check.py
from google.cloud import bigquery
client = bigquery.Client.from_service_account_json("C:/projects/healthcare_risk/gcp-json-key.json")

q1 = """
SELECT COUNT(*) FROM (
  SELECT PATIENT, CODE, START, COUNT(*) as c
  from `healthcare-risk-vinay.raw.medications`
  group by PATIENT, CODE, START
  having c > 1
)
"""
r1 = list(client.query(q1))[0][0]
print(f"Duplicates with [PATIENT, CODE, START]: {r1}")

q2 = """
SELECT COUNT(*) FROM (
  SELECT PATIENT, CODE, START, ENCOUNTER, COUNT(*) as c
  from `healthcare-risk-vinay.raw.medications`
  group by PATIENT, CODE, START, ENCOUNTER
  having c > 1
)
"""
r2 = list(client.query(q2))[0][0]
print(f"Duplicates with [PATIENT, CODE, START, ENCOUNTER]: {r2}")
