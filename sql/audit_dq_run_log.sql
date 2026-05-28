-- audit_dq_run_log.sql
-- BigQuery DDL for the DQ audit log table.
-- Run this once to create the audit dataset and table.

CREATE SCHEMA IF NOT EXISTS `YOUR_PROJECT_ID.audit`
OPTIONS (location = 'US');

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT_ID.audit.dq_run_log` (
    run_timestamp     TIMESTAMP     NOT NULL,
    dag_run_id        STRING        NOT NULL,
    check_type        STRING        NOT NULL,   -- 'row_count' | 'null_rate' | 'freshness'
    table_name        STRING        NOT NULL,
    column_name       STRING,                   -- NULL for row_count checks
    check_result      STRING        NOT NULL,   -- 'pass' | 'fail'
    row_count         INT64,                    -- Populated for row_count checks
    null_rate_pct     FLOAT64,                  -- Populated for null_rate checks
    details           STRING,                   -- Human-readable check detail
    _inserted_at      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(run_timestamp)
CLUSTER BY check_type, table_name
OPTIONS (
    description = 'Data quality audit log for healthcare_risk pipeline',
    partition_expiration_days = 365
);
