"""DAG: data_ingestion — Ingests data from sources into the raw data lake zone.

OpenLineage is auto-enabled via the openlineage-airflow provider.
Every task emits START/COMPLETE/FAIL lineage events to Marquez.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def ingest_csv_files(**context):
    """Simulate ingesting CSV files from a landing zone into the raw data lake."""
    import os
    import shutil

    landing = os.getenv("LANDING_ZONE", "/data/landing")
    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    os.makedirs(raw_zone, exist_ok=True)

    files = []
    if os.path.exists(landing):
        for f in os.listdir(landing):
            if f.endswith(".csv"):
                src = os.path.join(landing, f)
                dst = os.path.join(raw_zone, f)
                shutil.copy2(src, dst)
                files.append(f)

    context["ti"].xcom_push(key="ingested_files", value=files)
    print(f"Ingested {len(files)} CSV files into raw zone")
    return len(files)


def ingest_api_data(**context):
    """Simulate fetching data from an external REST API."""
    import json
    import os

    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    os.makedirs(raw_zone, exist_ok=True)

    # Simulate API response
    sample_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "records": [
            {"id": 1, "value": 42.5, "status": "active"},
            {"id": 2, "value": 18.3, "status": "inactive"},
            {"id": 3, "value": 99.1, "status": "active"},
        ],
    }

    output_path = os.path.join(raw_zone, f"api_data_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(output_path, "w") as f:
        json.dump(sample_data, f, indent=2)

    print(f"Ingested API data to {output_path}")
    return output_path


def validate_raw_data(**context):
    """Basic validation: check that raw files are non-empty and have expected format."""
    import os

    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    if not os.path.exists(raw_zone):
        raise FileNotFoundError(f"Raw zone does not exist: {raw_zone}")

    errors = []
    for f in os.listdir(raw_zone):
        fp = os.path.join(raw_zone, f)
        if os.path.getsize(fp) == 0:
            errors.append(f"{f} is empty")

    if errors:
        raise ValueError(f"Raw data validation failed: {errors}")

    print(f"Validated {len(os.listdir(raw_zone))} files in raw zone")


with DAG(
    dag_id="data_ingestion",
    default_args=default_args,
    description="Ingest data from CSV files and APIs into the raw data lake zone",
    schedule="@hourly",
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
