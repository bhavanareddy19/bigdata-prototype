"""DAG: data_quality_checks — Validates data quality on curated datasets.

Runs after data_transformation to ensure curated data meets quality standards.
Failures are captured by the observability agent for root-cause analysis.

Failure scenarios (for observability testing):
  - check_schema_conformance: fails if metadata columns (_processed_at etc.) are missing
  - check_null_ratios: fails if any column has >10% nulls (catches merged schema mismatches)
  - check_row_counts: fails if dataset has fewer than 3 rows
  - check_duplicates: fails if >5% duplicate rows found
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.storage_paths import build_paths
from utils.storage_io import ensure_dir, list_files, join_path, copy_file, write_text, path_exists
paths = build_paths()

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}


def check_schema_conformance(**context):
    """Verify curated datasets have the expected metadata columns.

    Failure scenarios:
      - SchemaError: metadata columns missing — enrich_with_metadata didn't run properly
      - FileNotFoundError: curated zone empty — transformation pipeline didn't complete
    """
    import os

    import pandas as pd

    curated_zone = paths["curated"]
    if not path_exists(curated_zone):
        raise FileNotFoundError(
            f"SchemaCheckError: Curated zone not found at {curated_zone}. "
            "The data_transformation DAG must complete before quality checks can run. "
            "Trigger data_transformation first."
        )

    csv_files = [f for f in list_files(curated_zone) if f.endswith(".csv") and not f.startswith(".")]
    if not csv_files:
        raise FileNotFoundError(
            "SchemaCheckError: No CSV files found in curated zone. "
            "The data_transformation DAG produced no output. "
            "Check enrich_with_metadata task logs for errors."
        )

    errors = []
    required_meta = ["_processed_at", "_source_file", "_pipeline_version"]

    for f in csv_files:
        df = pd.read_csv(join_path(curated_zone, f))
        missing = [c for c in required_meta if c not in df.columns]
        if missing:
            errors.append(
                f"SchemaError in {f}: missing metadata columns {missing}. "
                f"These are added by enrich_with_metadata task. "
                f"Got columns: {list(df.columns)}"
            )

    if errors:
        raise ValueError("Schema conformance FAILED:\n" + "\n".join(f"  {e}" for e in errors))

    print(f"Schema conformance PASSED — checked {len(csv_files)} file(s)")


def check_null_ratios(**context):
    """Ensure null ratio per column is below threshold (10%).

    Failure scenarios:
      - NullRatioError: combined_data.csv has massive nulls because sales_data and
        user_events have completely different schemas — when merged, each file's columns
        are null for the other file's rows (e.g. 'price' is null for all user_event rows)
    """
    import os

    import pandas as pd

    curated_zone = paths["curated"]
    # 10% threshold — strict enough to catch schema merge issues
    threshold = float(os.getenv("NULL_RATIO_THRESHOLD", "0.10"))

    violations = []
    for f in list_files(curated_zone):
        if not f.endswith(".csv") or f.startswith("."):
            continue
        df = pd.read_csv(join_path(curated_zone, f))
        if len(df) == 0:
            continue

        for col in df.columns:
            if col.startswith("_"):
                continue  # skip metadata columns
            null_ratio = df[col].isnull().sum() / len(df)
            if null_ratio > threshold:
                violations.append(
                    f"NullRatioError in {f} → column '{col}': null ratio = {null_ratio:.1%} "
                    f"(threshold: {threshold:.0%}, total rows: {len(df)}). "
                    f"High nulls in combined data often mean two files with different schemas "
                    f"were merged together — check transform_aggregate logic."
                )

    if violations:
        raise ValueError(
            f"Null ratio check FAILED with {len(violations)} violation(s):\n"
            + "\n".join(f"  {v}" for v in violations)
        )

    print(f"Null ratio check PASSED — all columns below {threshold:.0%} null threshold")


def check_row_counts(**context):
    """Ensure datasets have a minimum number of rows.

    Failure scenarios:
      - RowCountError: dataset has 0 or very few rows — possible upstream failure
        that produced empty output silently without raising an error
    """
    import os

    import pandas as pd

    curated_zone = paths["curated"]
    min_rows = int(os.getenv("MIN_EXPECTED_ROWS", "3"))

    errors = []
    for f in list_files(curated_zone):
        if not f.endswith(".csv") or f.startswith("."):
            continue
        df = pd.read_csv(join_path(curated_zone, f))
        if len(df) < min_rows:
            errors.append(
                f"RowCountError in {f}: only {len(df)} row(s) found (minimum: {min_rows}). "
                f"Dataset is suspiciously small — possible data loss in transformation. "
                f"Check data_ingestion ran successfully and landing/ folder has source files."
            )

    if errors:
        raise ValueError("Row count check FAILED:\n" + "\n".join(f"  {e}" for e in errors))

    print(f"Row count check PASSED — all datasets have >= {min_rows} rows")


def check_duplicates(**context):
    """Check for duplicate rows in curated datasets.

    Failure scenarios:
      - DuplicateError: >5% duplicate rows — idempotency issue or double ingestion
        (e.g. data_ingestion ran twice copying the same source files)
    """
    import os

    import pandas as pd

    curated_zone = paths["curated"]
    max_dup_ratio = float(os.getenv("MAX_DUPLICATE_RATIO", "0.05"))

    violations = []
    for f in join_path(curated_zone):
        if not f.endswith(".csv") or f.startswith("."):
            continue
        df = pd.read_csv(join_path(curated_zone, f))
        if len(df) == 0:
            continue

        data_cols = [c for c in df.columns if not c.startswith("_")]
        if not data_cols:
            continue

        dup_count = df.duplicated(subset=data_cols).sum()
        dup_ratio = dup_count / len(df)

        if dup_ratio > max_dup_ratio:
            violations.append(
                f"DuplicateError in {f}: {dup_count} duplicate row(s) ({dup_ratio:.1%} of {len(df)} rows). "
                f"Threshold: {max_dup_ratio:.0%}. "
                f"Possible cause: data_ingestion ran multiple times copying the same source files, "
                f"or the source system sent duplicate records."
            )

    if violations:
        raise ValueError("Duplicate check FAILED:\n" + "\n".join(f"  {v}" for v in violations))

    print(f"Duplicate check PASSED — all datasets below {max_dup_ratio:.0%} duplicate threshold")


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

    # All 4 quality checks run in parallel
    [t_schema, t_nulls, t_rows, t_dups]
