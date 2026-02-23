"""DAG: data_transformation — Cleans, transforms, and aggregates raw data.

Reads from raw zone, applies transformations, writes to processed zone.
OpenLineage tracks every input/output dataset automatically.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def clean_data(**context):
    """Clean raw CSV data: drop nulls, normalize columns, fix types."""
    import os

    import pandas as pd

    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    staging = os.getenv("STAGING_ZONE", "/data/staging")
    os.makedirs(staging, exist_ok=True)

    if not os.path.exists(raw_zone):
        print(f"Raw zone not found: {raw_zone} — skipping (run data_ingestion first)")
        return 0

    processed = 0
    for f in os.listdir(raw_zone):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(raw_zone, f))
        # Drop rows where all values are null
        df = df.dropna(how="all")
        # Normalize column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        df.to_csv(os.path.join(staging, f"cleaned_{f}"), index=False)
        processed += 1

    print(f"Cleaned {processed} files → staging zone")
    return processed


def transform_aggregate(**context):
    """Aggregate cleaned data: group by key columns, compute metrics."""
    import os

    import pandas as pd

    staging = os.getenv("STAGING_ZONE", "/data/staging")
    processed_zone = os.getenv("PROCESSED_ZONE", "/data/processed")
    os.makedirs(processed_zone, exist_ok=True)

    dfs = []
    for f in os.listdir(staging):
        if f.startswith("cleaned_") and f.endswith(".csv"):
            dfs.append(pd.read_csv(os.path.join(staging, f)))

    if not dfs:
        print("No cleaned files to aggregate")
        return

    combined = pd.concat(dfs, ignore_index=True)

    # Example aggregation: if there's a 'status' column, group by it
    if "status" in combined.columns:
        agg = combined.groupby("status").agg("count").reset_index()
        agg.to_csv(os.path.join(processed_zone, "status_aggregation.csv"), index=False)
        print(f"Aggregated {len(combined)} rows by status → processed zone")
    else:
        combined.to_csv(os.path.join(processed_zone, "combined_data.csv"), index=False)
        print(f"Combined {len(combined)} rows → processed zone")


def enrich_with_metadata(**context):
    """Add metadata columns: processing timestamp, source tracking."""
    import os

    import pandas as pd

    processed_zone = os.getenv("PROCESSED_ZONE", "/data/processed")
    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")
    os.makedirs(curated_zone, exist_ok=True)

    for f in os.listdir(processed_zone):
        if not f.endswith(".csv"):
            continue
        df = pd.read_csv(os.path.join(processed_zone, f))
        df["_processed_at"] = datetime.utcnow().isoformat()
        df["_source_file"] = f
        df["_pipeline_version"] = "1.0.0"
        df.to_csv(os.path.join(curated_zone, f"curated_{f}"), index=False)

    print(f"Enriched data → curated zone")


with DAG(
    dag_id="data_transformation",
    default_args=default_args,
    description="Clean, transform, and aggregate raw data into curated datasets",
    schedule="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["transformation", "data-platform"],
) as dag:

    t_clean = PythonOperator(
        task_id="clean_data",
        python_callable=clean_data,
    )

    t_aggregate = PythonOperator(
        task_id="transform_aggregate",
        python_callable=transform_aggregate,
    )

    t_enrich = PythonOperator(
        task_id="enrich_with_metadata",
        python_callable=enrich_with_metadata,
    )

    t_clean >> t_aggregate >> t_enrich
