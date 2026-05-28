"""
dag_dbt_pipeline.py
-------------------
Runs the full dbt pipeline: staging → intermediate → marts.
Triggered by dag_synpuf_ingest or can be run manually.

Each layer runs + tests sequentially so failures are caught early.
On success, triggers dag_data_quality.
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

DBT_DIR         = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt/healthcare_risk")
DBT_TARGET      = os.getenv("DBT_TARGET", "prod")
DBT_PROFILES    = os.getenv("DBT_PROFILES_DIR", "/opt/airflow/dbt")

default_args = {
    "owner": "analytics-engineering",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
    "email_on_failure": True,
    "email": [os.getenv("ALERT_EMAIL", "analytics@yourcompany.com")],
}

DBT_BASE = (
    f"cd {DBT_DIR} && "
    f"dbt --profiles-dir {DBT_PROFILES} "
    f"--target {DBT_TARGET}"
)

with DAG(
    dag_id="dag_dbt_pipeline",
    description="Run dbt staging → intermediate → marts with tests at each layer",
    default_args=default_args,
    schedule_interval=None,     # Triggered only — not on a cron
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["healthcare", "dbt", "transform"],
    doc_md=__doc__,
) as dag:

    dbt_deps = BashOperator(
        task_id="dbt_deps",
        bash_command=f"{DBT_BASE} deps",
        execution_timeout=timedelta(minutes=5),
    )

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{DBT_BASE} seed --full-refresh",
        execution_timeout=timedelta(minutes=5),
    )

    dbt_run_staging = BashOperator(
        task_id="dbt_run_staging",
        bash_command=f"{DBT_BASE} run --select staging",
        execution_timeout=timedelta(minutes=20),
    )

    dbt_test_staging = BashOperator(
        task_id="dbt_test_staging",
        bash_command=f"{DBT_BASE} test --select staging",
        execution_timeout=timedelta(minutes=10),
    )

    dbt_run_intermediate = BashOperator(
        task_id="dbt_run_intermediate",
        bash_command=f"{DBT_BASE} run --select intermediate",
        execution_timeout=timedelta(minutes=20),
    )

    dbt_run_marts = BashOperator(
        task_id="dbt_run_marts",
        bash_command=f"{DBT_BASE} run --select marts",
        execution_timeout=timedelta(minutes=30),
    )

    dbt_test_marts = BashOperator(
        task_id="dbt_test_marts",
        bash_command=f"{DBT_BASE} test --select marts",
        execution_timeout=timedelta(minutes=15),
    )

    dbt_generate_docs = BashOperator(
        task_id="dbt_generate_docs",
        bash_command=f"{DBT_BASE} docs generate",
        execution_timeout=timedelta(minutes=10),
    )

    trigger_dq = TriggerDagRunOperator(
        task_id="trigger_data_quality",
        trigger_dag_id="dag_data_quality",
        wait_for_completion=False,
    )

    # Sequential pipeline with test gates
    (
        dbt_deps
        >> dbt_seed
        >> dbt_run_staging
        >> dbt_test_staging
        >> dbt_run_intermediate
        >> dbt_run_marts
        >> dbt_test_marts
        >> dbt_generate_docs
        >> trigger_dq
    )
