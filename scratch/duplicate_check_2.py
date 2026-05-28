# duplicate_check.2.py
from google.cloud import bigquery
client = bigquery.Client.from_service_account_json("C:/projects/healthcare_risk/gcp-json-key.json")

q3 = """
SELECT COUNT(*) FROM (
  SELECT PATIENT, CODE, START, ENCOUNTER, STOP, TOTALCOST, COUNT(*) as c
  from `healthcare-risk-vinay.raw.medications`
  group by PATIENT, CODE, START, ENCOUNTER, STOP, TOTALCOST
  having c > 1
)
"""
r3 = list(client.query(q3))[0][0]
print(f"Duplicates with [PATIENT, CODE, START, ENCOUNTER, STOP, TOTALCOST]: {r3}")

q4 = """
SELECT COUNT(*) FROM (
  SELECT PATIENT, CODE, START, ENCOUNTER, STOP, TOTALCOST, PAYER, BASE_COST, COUNT(*) as c
  from `healthcare-risk-vinay.raw.medications`
  group by PATIENT, CODE, START, ENCOUNTER, STOP, TOTALCOST, PAYER, BASE_COST
  having c > 1
)
"""
r4 = list(client.query(q4))[0][0]
print(f"Duplicates with [PATIENT, CODE, START, ENCOUNTER, STOP, TOTALCOST, PAYER, BASE_COST]: {r4}")
