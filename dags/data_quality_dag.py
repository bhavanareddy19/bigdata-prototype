"""DAG: data_quality_checks — Validates data quality using Great Expectations.

Runs after data_transformation to ensure curated data meets quality standards.
Failures are captured by the observability agent for root-cause analysis.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}


def check_schema_conformance(**context):
    """Verify that curated datasets have the expected schema."""
    import os

    import pandas as pd

    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")
    if not os.path.exists(curated_zone):
        raise FileNotFoundError(f"Curated zone not found: {curated_zone}")

    errors = []
    for f in os.listdir(curated_zone):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(curated_zone, f))

        # Check required metadata columns exist
        required = ["_processed_at", "_source_file", "_pipeline_version"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            errors.append(f"{f}: missing columns {missing}")

    if errors:
        raise ValueError(f"Schema conformance failed:\n" + "\n".join(errors))

    print("Schema conformance: PASSED")


def check_null_ratios(**context):
    """Ensure null ratio per column is below threshold."""
    import os

    import pandas as pd

    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")
    threshold = float(os.getenv("NULL_RATIO_THRESHOLD", "0.3"))

    warnings = []
    for f in os.listdir(curated_zone):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(curated_zone, f))
        for col in df.columns:
            if col.startswith("_"):
                continue  # skip metadata columns
            null_ratio = df[col].isnull().sum() / len(df) if len(df) > 0 else 0
            if null_ratio > threshold:
                warnings.append(f"{f}.{col}: null ratio = {null_ratio:.2%} (threshold: {threshold:.0%})")

    if warnings:
        raise ValueError(f"Null ratio check failed:\n" + "\n".join(warnings))

    print("Null ratio check: PASSED")


def check_row_counts(**context):
    """Ensure datasets are not unexpectedly empty or have anomalous row counts."""
    import os

    import pandas as pd

    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")
    min_rows = int(os.getenv("MIN_EXPECTED_ROWS", "1"))

    errors = []
    for f in os.listdir(curated_zone):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(curated_zone, f))
        if len(df) < min_rows:
            errors.append(f"{f}: only {len(df)} rows (minimum: {min_rows})")

    if errors:
        raise ValueError(f"Row count check failed:\n" + "\n".join(errors))

    print("Row count check: PASSED")


def check_duplicates(**context):
    """Check for duplicate rows in curated datasets."""
    import os

    import pandas as pd

    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")
    max_dup_ratio = float(os.getenv("MAX_DUPLICATE_RATIO", "0.05"))

    warnings = []
    for f in os.listdir(curated_zone):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(curated_zone, f))
        # Exclude metadata columns for duplicate check
        data_cols = [c for c in df.columns if not c.startswith("_")]
        if not data_cols:
            continue
        dup_count = df.duplicated(subset=data_cols).sum()
        dup_ratio = dup_count / len(df) if len(df) > 0 else 0
        if dup_ratio > max_dup_ratio:
            warnings.append(f"{f}: {dup_count} duplicates ({dup_ratio:.2%})")

    if warnings:
        raise ValueError(f"Duplicate check failed:\n" + "\n".join(warnings))

    print("Duplicate check: PASSED")


with DAG(
    dag_id="data_quality_checks",
    default_args=default_args,
    description="Run data quality validations on curated datasets",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["quality", "data-platform"],
) as dag:

    t_schema = PythonOperator(
        task_id="check_schema_conformance",
        python_callable=check_schema_conformance,
    )

    t_nulls = PythonOperator(
        task_id="check_null_ratios",
        python_callable=check_null_ratios,
    )

    t_rows = PythonOperator(
        task_id="check_row_counts",
        python_callable=check_row_counts,
    )

    t_dups = PythonOperator(
        task_id="check_duplicates",
        python_callable=check_duplicates,
    )

    # All quality checks run in parallel after DAG trigger
    [t_schema, t_nulls, t_rows, t_dups]
