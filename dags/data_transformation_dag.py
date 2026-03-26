"""DAG: data_transformation — Cleans, transforms, and aggregates raw data.

Reads from raw zone, applies transformations, writes to processed zone.
OpenLineage tracks every input/output dataset automatically.

Failure scenarios (for observability testing):
  - clean_data: DataTypeError if price column has non-numeric/negative values
  - transform_aggregate: fails if required 'status' column is missing after clean
  - enrich_with_metadata: fails if processed zone is empty (nothing to enrich)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.storage_io import ensure_dir, join_path, path_exists
from utils.storage_paths import build_paths

paths = build_paths()

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def clean_data(**context):
    """Clean raw CSV data: drop nulls, normalize columns, validate types.

    Failure scenarios:
      - DataTypeError: price column contains non-numeric values (e.g. 'N/A', 'unknown')
      - DataTypeError: negative prices detected — possible data corruption
      - EmptyDataError: all rows dropped after cleaning
    """
    import os

    import pandas as pd

    raw_zone = paths["raw"]
    staging = paths["staging"]
    ensure_dir(staging, exist_ok=True)

    if not path_exists(raw_zone):
        print(f"Raw zone not found: {raw_zone} — skipping (run data_ingestion first)")
        return 0

    processed = 0
    errors = []

    for f in join_path(raw_zone):
        if not f.endswith(".csv") or f.startswith("."):
            continue

        filepath = join_path(raw_zone, f)
        df = pd.read_csv(filepath)

        # Normalize column names first
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # ── Price column validation ──────────────────────────
        if "price" in df.columns:
            numeric_price = pd.to_numeric(df["price"], errors="coerce")
            bad_vals = df[numeric_price.isna()]["price"].dropna().unique().tolist()
            if bad_vals:
                errors.append(
                    f"DataTypeError in {f}: 'price' column has {len(bad_vals)} non-numeric "
                    f"value(s): {bad_vals[:5]}. "
                    f"All prices must be numeric floats. Check source system for data entry errors."
                )
                continue  # skip this file, do not write bad data downstream

            negative_prices = (numeric_price < 0).sum()
            if negative_prices > 0:
                errors.append(
                    f"DataQualityError in {f}: found {negative_prices} negative price(s). "
                    f"Negative prices are invalid — possible sign error or data corruption in source."
                )
                continue

        # ── Quantity validation ──────────────────────────────
        if "quantity" in df.columns:
            numeric_qty = pd.to_numeric(df["quantity"], errors="coerce")
            null_qty = numeric_qty.isna().sum()
            if null_qty > 0:
                print(f"WARNING: {f} has {null_qty} null quantity value(s) — rows will be dropped")
                df = df[numeric_qty.notna()].copy()

        # ── Drop rows where all values are null ──────────────
        before = len(df)
        df = df.dropna(how="all")
        dropped = before - len(df)
        if dropped > 0:
            print(f"Dropped {dropped} fully-null rows from {f}")

        if len(df) == 0:
            errors.append(
                f"EmptyDataError in {f}: after cleaning, 0 rows remain. "
                f"The source file may be entirely null or have wrong encoding."
            )
            continue

        out_path = join_path(staging, f"cleaned_{f}")
        df.to_csv(out_path, index=False)
        processed += 1
        print(f"Cleaned {f}: {len(df)} rows → {out_path}")

    if errors:
        error_summary = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors))
        raise ValueError(
            f"clean_data failed with {len(errors)} error(s):\n{error_summary}\n"
            f"Fix the source data issues above before re-running."
        )

    print(f"Cleaned {processed} files → staging zone")
    return processed


def transform_aggregate(**context):
    """Aggregate cleaned data: group by status, compute totals.

    Failure scenarios:
      - FileNotFoundError: no cleaned files exist (clean_data wrote nothing)
      - ValueError: 'status' column missing — cannot group data as expected
    """
    import os

    import pandas as pd

    staging = paths["staging"]
    processed_zone = paths["processed"]
    ensure_dir(processed_zone, exist_ok=True)

    cleaned_files = [f for f in join_path(staging) if f.startswith("cleaned_") and f.endswith(".csv")]

    if not cleaned_files:
        raise FileNotFoundError(
            "AggregationError: No cleaned files found in staging zone. "
            "Either data_ingestion has not run yet, or clean_data failed for all files. "
            "Run data_ingestion first, then check clean_data task logs for errors."
        )

    dfs = []
    for f in cleaned_files:
        dfs.append(pd.read_csv(join_path(staging, f)))

    combined = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(combined)} total rows from {len(dfs)} cleaned file(s)")

    if "status" not in combined.columns:
        raise ValueError(
            "SchemaError: 'status' column not found after combining cleaned files. "
            f"Available columns: {list(combined.columns)}. "
            "The 'status' column is required for aggregation. "
            "Check if clean_data renamed or dropped this column."
        )

    agg = combined.groupby("status").agg("count").reset_index()
    agg.to_csv(join_path(processed_zone, "status_aggregation.csv"), index=False)
    combined.to_csv(join_path(processed_zone, "combined_data.csv"), index=False)

    print(f"Aggregated {len(combined)} rows by status → {len(agg)} groups")
    print(f"Status breakdown:\n{agg.to_string(index=False)}")


def enrich_with_metadata(**context):
    """Add metadata columns: processing timestamp, source tracking, pipeline version.

    Failure scenarios:
      - FileNotFoundError: processed zone is empty (transform_aggregate wrote nothing)
    """
    import os

    import pandas as pd

    processed_zone = paths["processed"]
    curated_zone = paths["curated"]
    ensure_dir(curated_zone, exist_ok=True)

    csv_files = [f for f in join_path(processed_zone) if f.endswith(".csv") and not f.startswith(".")]

    if not csv_files:
        raise FileNotFoundError(
            "EnrichmentError: No processed CSV files found in processed zone. "
            "transform_aggregate must complete successfully before enrichment can run. "
            "Check transform_aggregate task logs."
        )

    enriched = 0
    for f in csv_files:
        df = pd.read_csv(join_path(processed_zone, f))
        df["_processed_at"] = datetime.utcnow().isoformat()
        df["_source_file"] = f
        df["_pipeline_version"] = "1.0.0"
        out_path = join_path(curated_zone, f"curated_{f}")
        df.to_csv(out_path, index=False)
        enriched += 1
        print(f"Enriched {f} ({len(df)} rows) → {out_path}")

    print(f"Enrichment complete: {enriched} file(s) written to curated zone")


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
