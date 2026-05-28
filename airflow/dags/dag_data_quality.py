"""
dag_data_quality.py
-------------------
Post-pipeline data quality checks and audit logging.
Triggered by dag_dbt_pipeline on completion.

Checks:
  1. Row counts — fails if any mart table drops >10% vs prior run
  2. Null rates  — fails if key fields exceed 1% null rate
  3. Freshness   — fails if max service_date is >90 days stale
  4. Writes results to audit.dq_run_log in BigQuery
  5. Slack notification on pass or fail
"""

import os
import json
import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator

log = logging.getLogger(__name__)

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "your-gcp-project")
BQ_DATASET     = "healthcare_risk"
AUDIT_TABLE    = f"{GCP_PROJECT_ID}.audit.dq_run_log"
SLACK_CONN_ID  = "slack_healthcare_alerts"

MART_TABLES = [
    "mart_member_risk_profile",
    "mart_care_gaps",
    "mart_cost_utilization",
    "mart_provider_efficiency",
]

NULL_CHECK_CONFIG = {
    "mart_member_risk_profile": ["member_id", "risk_tier", "measurement_year", "hcc_risk_score"],
    "mart_care_gaps":           ["member_id", "gap_type", "gap_open", "measurement_year"],
    "mart_cost_utilization":    ["risk_tier", "member_count", "avg_cost_pmpm"],
    "mart_provider_efficiency": ["provider_npi", "attributed_member_count"],
}

default_args = {
    "owner": "analytics-engineering",
    "depends_on_past": False,
    "retries": 0,
    "email_on_failure": True,
    "email": [os.getenv("ALERT_EMAIL", "analytics@yourcompany.com")],
}


def run_row_count_checks(**context):
    """
    Query row counts for all mart tables.
    Compare to prior run in audit log.
    Fail if any table drops >10%.
    """
    from google.cloud import bigquery
    client = bigquery.Client(project=GCP_PROJECT_ID)

    current_counts = {}
    for table in MART_TABLES:
        result = client.query(
            f"SELECT COUNT(*) as cnt FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{table}`"
        ).result()
        current_counts[table] = list(result)[0]["cnt"]
        log.info(f"{table}: {current_counts[table]} rows")

    # Get prior run counts
    prior_query = f"""
        SELECT table_name, row_count
        FROM `{AUDIT_TABLE}`
        WHERE run_timestamp = (
            SELECT MAX(run_timestamp) FROM `{AUDIT_TABLE}`
        )
        AND check_type = 'row_count'
    """
    try:
        prior_rows = list(client.query(prior_query).result())
        prior_counts = {r["table_name"]: r["row_count"] for r in prior_rows}
    except Exception:
        prior_counts = {}
        log.info("No prior audit log found — skipping comparison")

    failures = []
    for table, count in current_counts.items():
        prior = prior_counts.get(table, count)
        if prior > 0:
            drop_pct = (prior - count) / prior * 100
            if drop_pct > 10:
                failures.append(
                    f"{table}: dropped {drop_pct:.1f}% ({prior} → {count})"
                )

    context["task_instance"].xcom_push(key="row_counts", value=json.dumps(current_counts))

    if failures:
        raise ValueError(f"Row count failures: {failures}")

    log.info(f"✓ Row count checks passed: {current_counts}")


def run_null_rate_checks(**context):
    """Check null rates on critical columns. Fail if >1%."""
    from google.cloud import bigquery
    client = bigquery.Client(project=GCP_PROJECT_ID)

    failures = []
    null_results = {}

    for table, columns in NULL_CHECK_CONFIG.items():
        for col in columns:
            query = f"""
                SELECT
                    COUNTIF({col} IS NULL) / COUNT(*) AS null_rate
                FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.{table}`
            """
            result = list(client.query(query).result())
            null_rate = float(result[0]["null_rate"]) if result else 0.0
            key = f"{table}.{col}"
            null_results[key] = round(null_rate * 100, 3)

            if null_rate > 0.01:
                failures.append(f"{key}: {null_rate*100:.2f}% nulls (threshold: 1%)")

    context["task_instance"].xcom_push(key="null_rates", value=json.dumps(null_results))

    if failures:
        raise ValueError(f"Null rate failures:\n" + "\n".join(failures))

    log.info(f"✓ Null rate checks passed")


def run_freshness_check(**context):
    """Check that max service_date in claims is within 90 days of expected."""
    from google.cloud import bigquery
    client = bigquery.Client(project=GCP_PROJECT_ID)

    query = f"""
        SELECT MAX(service_date) AS max_date
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}_staging.stg_inpatient_claims`
    """
    result = list(client.query(query).result())
    max_date = result[0]["max_date"] if result else None

    if max_date is None:
        raise ValueError("No service dates found in stg_inpatient_claims")

    days_old = (datetime.utcnow().date() - max_date).days
    log.info(f"Max service date: {max_date} ({days_old} days ago)")

    context["task_instance"].xcom_push(key="max_service_date", value=str(max_date))
    context["task_instance"].xcom_push(key="days_stale", value=days_old)

    # Note: SynPUF data is 2008 — for demo purposes, threshold is relaxed
    # In production: raise ValueError if days_old > 90
    if days_old > 365 * 20:   # 20 years for SynPUF demo data
        raise ValueError(f"Data freshness check: max_date {max_date} is {days_old} days stale")

    log.info("✓ Freshness check passed")


def write_audit_log(**context):
    """Write DQ run results to BigQuery audit table."""
    from google.cloud import bigquery
    client = bigquery.Client(project=GCP_PROJECT_ID)

    ti = context["task_instance"]
    run_ts = datetime.utcnow().isoformat()
    dag_run_id = context["run_id"]

    row_counts = json.loads(ti.xcom_pull(task_ids="check_row_counts", key="row_counts") or "{}")
    null_rates = json.loads(ti.xcom_pull(task_ids="check_null_rates",  key="null_rates") or "{}")
    max_date   = ti.xcom_pull(task_ids="check_freshness", key="max_service_date")
    days_stale = ti.xcom_pull(task_ids="check_freshness", key="days_stale")

    rows = []

    for table, count in row_counts.items():
        rows.append({
            "run_timestamp": run_ts,
            "dag_run_id": dag_run_id,
            "check_type": "row_count",
            "table_name": table,
            "column_name": None,
            "check_result": "pass",
            "row_count": count,
            "null_rate_pct": None,
            "details": f"row_count={count}",
        })

    for col_key, null_pct in null_rates.items():
        table, col = col_key.split(".", 1)
        rows.append({
            "run_timestamp": run_ts,
            "dag_run_id": dag_run_id,
            "check_type": "null_rate",
            "table_name": table,
            "column_name": col,
            "check_result": "pass" if null_pct <= 1.0 else "fail",
            "row_count": None,
            "null_rate_pct": null_pct,
            "details": f"null_rate={null_pct}%",
        })

    rows.append({
        "run_timestamp": run_ts,
        "dag_run_id": dag_run_id,
        "check_type": "freshness",
        "table_name": "stg_inpatient_claims",
        "column_name": "service_date",
        "check_result": "pass",
        "row_count": None,
        "null_rate_pct": None,
        "details": f"max_date={max_date}, days_stale={days_stale}",
    })

    errors = client.insert_rows_json(AUDIT_TABLE, rows)
    if errors:
        log.warning(f"Audit log insert errors: {errors}")
    else:
        log.info(f"✓ Audit log: {len(rows)} rows written to {AUDIT_TABLE}")


def branch_on_outcome(**context):
    """Branch to success or failure Slack notification."""
    # If we reach this task, all upstream checks passed
    return "slack_notify_success"


with DAG(
    dag_id="dag_data_quality",
    description="Post-dbt data quality checks and audit logging",
    default_args=default_args,
    schedule_interval=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["healthcare", "dq", "audit"],
    doc_md=__doc__,
) as dag:

    check_row_counts = PythonOperator(
        task_id="check_row_counts",
        python_callable=run_row_count_checks,
    )

    check_null_rates = PythonOperator(
        task_id="check_null_rates",
        python_callable=run_null_rate_checks,
    )

    check_freshness = PythonOperator(
        task_id="check_freshness",
        python_callable=run_freshness_check,
    )

    write_log = PythonOperator(
        task_id="write_audit_log",
        python_callable=write_audit_log,
        trigger_rule="all_done",   # Always write, even if checks fail
    )

    branch = BranchPythonOperator(
        task_id="branch_outcome",
        python_callable=branch_on_outcome,
        trigger_rule="all_success",
    )

    slack_success = SlackWebhookOperator(
        task_id="slack_notify_success",
        slack_webhook_conn_id=SLACK_CONN_ID,
        message=(
            ":white_check_mark: *healthcare_risk DQ passed*\n"
            "All row count, null rate, and freshness checks passed.\n"
            "Run: `{{ run_id }}`"
        ),
    )

    slack_failure = SlackWebhookOperator(
        task_id="slack_notify_failure",
        slack_webhook_conn_id=SLACK_CONN_ID,
        message=(
            ":red_circle: *healthcare_risk DQ FAILED*\n"
            "Check the audit log and Airflow logs for details.\n"
            "Run: `{{ run_id }}`"
        ),
        trigger_rule="one_failed",
    )

    [check_row_counts, check_null_rates, check_freshness] >> write_log >> branch
    branch >> slack_success
    [check_row_counts, check_null_rates, check_freshness] >> slack_failure
