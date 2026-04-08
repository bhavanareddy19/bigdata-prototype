"""DAG: data_ingestion — Ingests data from sources into the raw data lake zone.

OpenLineage is auto-enabled via the openlineage-airflow provider.
Every task emits START/COMPLETE/FAIL lineage events to Marquez.

Failure scenarios (for observability testing):
  - validate_raw_data: fails if a CSV has wrong/missing required columns
  - validate_raw_data: fails if price column contains non-numeric values
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.storage_paths import build_paths
from utils.storage_io import ensure_dir, get_size, list_files, join_path, copy_file, write_text, path_exists

paths = build_paths()

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# Expected columns for each known file — any deviation triggers a SchemaValidationError
REQUIRED_SCHEMAS = {
    "sales_data.csv": ["id", "product", "category", "quantity", "price", "status", "region"],
    "user_events.csv": ["user_id", "event_type", "timestamp", "page", "duration_seconds", "status"],
}


def ingest_csv_files(**context):
    """Simulate ingesting CSV files from a landing zone into the raw data lake."""
    import os
    import shutil

    landing = paths["landing"]
    raw_zone = paths["raw"]
    ensure_dir(raw_zone)

    files = []
    if path_exists(landing):
        for f in list_files(landing):
            if f.endswith(".csv"):
                src = join_path(landing, f)
                dst = join_path(raw_zone, f)
                copy_file(src, dst)
                files.append(f)

    context["ti"].xcom_push(key="ingested_files", value=files)
    print(f"Ingested {len(files)} CSV files into raw zone: {files}")
    return len(files)


def ingest_api_data(**context):
    """Simulate fetching data from an external REST API."""
    import json
    import os

    raw_zone = paths["raw"]
    ensure_dir(raw_zone)
    # Simulate API response
    sample_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "records": [
            {"id": 1, "value": 42.5, "status": "active"},
            {"id": 2, "value": 18.3, "status": "inactive"},
            {"id": 3, "value": 99.1, "status": "active"},
        ],
    }

    output_path = join_path(raw_zone, f"api_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    write_text(output_path, json.dumps(sample_data, indent=2))
    print(f"Ingested API data to {output_path}")
    return output_path


def validate_raw_data(**context):
    """Validate raw files exist, are non-empty, and match expected schemas.

    Failure scenarios:
      - SchemaValidationError: CSV is missing required columns
      - SchemaValidationError: CSV has unexpected/wrong column names (bad source)
      - DataTypeError: price column contains non-numeric values
    """
    import os

    import pandas as pd

    raw_zone = paths["raw"]
    if not path_exists(raw_zone):
        raise FileNotFoundError(f"Raw zone does not exist: {raw_zone}")

    all_files = [f for f in list_files(raw_zone) if not f.startswith(".")]
    errors = []

    # ── 1. Empty file check ──────────────────────────────────
    for f in all_files:
        fp = join_path(raw_zone, f)
        if get_size(fp) == 0:
            errors.append(f"EmptyFileError: {f} is 0 bytes")

    # ── 2. Schema validation for known CSV files ─────────────
    for fname, required_cols in REQUIRED_SCHEMAS.items():
        fpath = join_path(raw_zone, fname)
        if not path_exists(fpath):
            # Not present yet — soft warning (ingest may not have run)
            print(f"WARNING: expected file {fname} not found in raw zone")
            continue

        df_head = pd.read_csv(fpath, nrows=0)
        actual_cols = list(df_head.columns)

        missing_cols = [c for c in required_cols if c not in actual_cols]
        if missing_cols:
            errors.append(
                f"SchemaValidationError: {fname} is missing required columns {missing_cols}. "
                f"Got columns: {actual_cols}. "
                f"This usually means the source system sent a different schema."
            )

        unexpected_cols = [c for c in actual_cols if c not in required_cols]
        if unexpected_cols:
            errors.append(
                f"SchemaValidationError: {fname} has unexpected columns {unexpected_cols}. "
                f"Expected: {required_cols}. "
                f"Check if the upstream data provider changed their schema."
            )

    # ── 3. Data type checks for critical columns ─────────────
    sales_path = join_path(raw_zone, "sales_data.csv")
    if path_exists(sales_path):
        try:
            df = pd.read_csv(sales_path)
            if "price" in df.columns:
                non_numeric = pd.to_numeric(df["price"], errors="coerce").isna().sum()
                if non_numeric > 0:
                    bad_vals = df[pd.to_numeric(df["price"], errors="coerce").isna()]["price"].unique().tolist()
                    errors.append(
                        f"DataTypeError: sales_data.csv has {non_numeric} non-numeric value(s) "
                        f"in 'price' column: {bad_vals}. "
                        f"Expected all float values. Possible data corruption or encoding issue."
                    )
            if "quantity" in df.columns:
                negative_qty = (pd.to_numeric(df["quantity"], errors="coerce") < 0).sum()
                if negative_qty > 0:
                    errors.append(
                        f"DataQualityError: sales_data.csv has {negative_qty} negative quantity value(s). "
                        f"Negative quantities are not allowed — check source system for data entry errors."
                    )
        except Exception as e:
            errors.append(f"ReadError: Could not read sales_data.csv for type checking: {e}")

    if errors:
        error_summary = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors))
        raise ValueError(
            f"Raw data validation failed with {len(errors)} error(s):\n{error_summary}\n"
            f"Fix the issues above before data_transformation can proceed."
        )

    print(f"Validated {len(all_files)} files in raw zone — all checks passed")


with DAG(
    dag_id="data_ingestion",
    default_args=default_args,
    description="Ingest data from CSV files and APIs into the raw data lake zone",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["ingestion", "data-platform"],
) as dag:

    t_csv = PythonOperator(
        task_id="ingest_csv_files",
        python_callable=ingest_csv_files,
    )

    t_api = PythonOperator(
        task_id="ingest_api_data",
        python_callable=ingest_api_data,
    )

    t_validate = PythonOperator(
        task_id="validate_raw_data",
        python_callable=validate_raw_data,
    )

    [t_csv, t_api] >> t_validate
