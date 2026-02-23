"""DAG: demo_pipeline — Full end-to-end pipeline demo with clean and bad data scenarios.

PURPOSE:
  This DAG is specifically for demonstrating the AI Observability chatbot.
  It runs the FULL pipeline in one DAG so you can see everything at once.

TWO SCENARIOS (select when triggering):
  Scenario A — inject_bad_data: false  (default)
    → Runs full pipeline with clean data only
    → All tasks go GREEN
    → Shows the happy path works

  Scenario B — inject_bad_data: true
    → Copies bad_orders.csv into the pipeline
    → validate_raw_data FAILS  (SchemaValidationError + DataTypeError)
    → clean_data FAILS          (non-numeric price, wrong columns)
    → check_null_ratios FAILS   (combined data has schema mismatch nulls)
    → evaluate_model FAILS      (if data was too messy to train on)
    → Use chatbot to diagnose each failure

HOW TO RUN:
  1. Go to Airflow UI → demo_pipeline → "Trigger DAG w/ config"
  2. Enter config:  {"inject_bad_data": true}   OR  {"inject_bad_data": false}
  3. Watch the tasks
  4. Use chatbot to diagnose any red tasks

CHATBOT USAGE:
  After a failure:
  - Check "Fetch Airflow task logs" in sidebar
  - DAG ID: demo_pipeline
  - Task ID: whichever task went red
  - Ask: "Why did this task fail and how do I fix it?"
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 0,         # No retries in demo — fail fast and show the error clearly
    "retry_delay": timedelta(minutes=1),
}


# ─────────────────────────────────────────────────────────────
# STEP 1 — Setup: inject or clean bad data
# ─────────────────────────────────────────────────────────────

def setup_demo_data(**context):
    """Copy bad_orders.csv into landing/ if inject_bad_data=true, else remove it.

    This simulates a real-world scenario where a new upstream data source
    starts sending files with wrong schema or bad data types.
    """
    import os
    import shutil

    conf = context.get("dag_run").conf or {}
    inject_bad = conf.get("inject_bad_data", False)

    landing = os.getenv("LANDING_ZONE", "/data/landing")
    demo_dir = "/data/demo"
    bad_src  = os.path.join(demo_dir, "bad_orders.csv")
    bad_dst  = os.path.join(landing, "bad_orders.csv")

    if inject_bad:
        if not os.path.exists(bad_src):
            raise FileNotFoundError(
                f"Demo bad data file not found at {bad_src}. "
                "Make sure data/demo/bad_orders.csv exists on the host machine."
            )
        shutil.copy2(bad_src, bad_dst)
        print("=" * 60)
        print("DEMO MODE: INJECTED bad_orders.csv into landing/")
        print("This file has:")
        print("  - Wrong column names (order_id instead of id)")
        print("  - Non-numeric prices (N/A, unknown, free)")
        print("  - Negative quantities")
        print("  - Missing required fields")
        print("Expected failures: validate_raw_data, clean_data")
        print("=" * 60)
    else:
        if os.path.exists(bad_dst):
            os.remove(bad_dst)
            print("DEMO MODE: Removed bad_orders.csv from landing/ (clean run)")
        print("=" * 60)
        print("DEMO MODE: CLEAN RUN — only good data in landing/")
        print("Files present:")
        for f in os.listdir(landing):
            if not f.startswith("."):
                print(f"  - {f}")
        print("Expected result: ALL TASKS GREEN")
        print("=" * 60)


# ─────────────────────────────────────────────────────────────
# STEP 2 — Ingest
# ─────────────────────────────────────────────────────────────

def ingest_all_files(**context):
    """Copy all CSV files from landing/ to raw/.

    Good files and bad files both get copied here.
    The next task (validate) decides if they are acceptable.
    """
    import os
    import shutil

    landing  = os.getenv("LANDING_ZONE", "/data/landing")
    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    os.makedirs(raw_zone, exist_ok=True)

    files = [f for f in os.listdir(landing) if f.endswith(".csv") and not f.startswith(".")]
    for f in files:
        shutil.copy2(os.path.join(landing, f), os.path.join(raw_zone, f))

    print(f"Ingested {len(files)} CSV file(s) into raw zone: {files}")
    context["ti"].xcom_push(key="ingested_files", value=files)
    return files


def ingest_api_records(**context):
    """Simulate API data ingestion (always produces clean data)."""
    import json
    import os

    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    os.makedirs(raw_zone, exist_ok=True)

    payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "demo_api",
        "records": [
            {"id": 1001, "value": 42.5, "status": "active"},
            {"id": 1002, "value": 18.3, "status": "inactive"},
            {"id": 1003, "value": 99.1, "status": "active"},
            {"id": 1004, "value": 55.0, "status": "active"},
            {"id": 1005, "value": 33.7, "status": "active"},
        ],
    }
    out = os.path.join(raw_zone, f"api_demo_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json")
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"API data ingested → {out}")


# Known good schemas — any deviation triggers SchemaValidationError
REQUIRED_SCHEMAS = {
    "sales_data.csv": ["id", "product", "category", "quantity", "price", "status", "region"],
    "user_events.csv": ["user_id", "event_type", "timestamp", "page", "duration_seconds", "status"],
}


def validate_ingested_data(**context):
    """Validate all raw files against known schemas and type rules.

    FAILS when bad_orders.csv is present:
      [1] SchemaValidationError: bad_orders.csv has wrong column names
          Got: [order_id, product_name, qty, unit_price, customer, discount_pct]
          Expected: [id, product, category, quantity, price, status, region]
      [2] DataTypeError: unit_price column has non-numeric values: ['N/A', 'unknown', 'free']
    """
    import os

    import pandas as pd

    raw_zone = os.getenv("RAW_ZONE", "/data/raw")
    errors = []

    all_csvs = [f for f in os.listdir(raw_zone) if f.endswith(".csv") and not f.startswith(".")]

    # ── Schema check for known files ────────────────────────
    for fname, required_cols in REQUIRED_SCHEMAS.items():
        fpath = os.path.join(raw_zone, fname)
        if not os.path.exists(fpath):
            print(f"WARNING: {fname} not found in raw zone")
            continue
        df = pd.read_csv(fpath, nrows=0)
        actual = list(df.columns)
        missing = [c for c in required_cols if c not in actual]
        if missing:
            errors.append(
                f"SchemaValidationError in {fname}: missing required columns {missing}. "
                f"Got: {actual}"
            )

    # ── Unknown files: detect schema/type problems ───────────
    known_files = set(REQUIRED_SCHEMAS.keys())
    for fname in all_csvs:
        if fname in known_files:
            continue
        fpath = os.path.join(raw_zone, fname)
        df = pd.read_csv(fpath)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Check if price-like column has non-numeric values
        price_cols = [c for c in df.columns if "price" in c or "cost" in c or "amount" in c]
        for col in price_cols:
            bad = pd.to_numeric(df[col], errors="coerce").isna().sum()
            if bad > 0:
                bad_vals = df[pd.to_numeric(df[col], errors="coerce").isna()][col].dropna().unique().tolist()
                errors.append(
                    f"DataTypeError in {fname} → column '{col}': "
                    f"{bad} non-numeric value(s) found: {bad_vals[:5]}. "
                    f"All monetary columns must be numeric. "
                    f"Fix: replace 'N/A', 'unknown', 'free' with actual numeric values or NULL."
                )

        # Check for negative quantities
        qty_cols = [c for c in df.columns if "qty" in c or "quantity" in c]
        for col in qty_cols:
            neg = (pd.to_numeric(df[col], errors="coerce") < 0).sum()
            if neg > 0:
                errors.append(
                    f"DataQualityError in {fname} → column '{col}': "
                    f"{neg} negative value(s) found. Quantities cannot be negative."
                )

    if errors:
        summary = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors))
        raise ValueError(
            f"Data validation FAILED with {len(errors)} error(s):\n{summary}\n\n"
            f"These files need to be fixed before the pipeline can continue."
        )

    print(f"Validation PASSED for {len(all_csvs)} file(s) in raw zone")


# ─────────────────────────────────────────────────────────────
# STEP 3 — Transform
# ─────────────────────────────────────────────────────────────

def clean_and_transform(**context):
    """Clean data, validate types, aggregate by status.

    For clean data: works perfectly
    For bad data: raises DataTypeError for non-numeric prices
    """
    import os

    import pandas as pd

    raw_zone     = os.getenv("RAW_ZONE", "/data/raw")
    staging      = os.getenv("STAGING_ZONE", "/data/staging")
    processed    = os.getenv("PROCESSED_ZONE", "/data/processed")
    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")

    for d in [staging, processed, curated_zone]:
        os.makedirs(d, exist_ok=True)

    errors = []
    cleaned_dfs = []

    for f in os.listdir(raw_zone):
        if not f.endswith(".csv") or f.startswith("."):
            continue

        df = pd.read_csv(os.path.join(raw_zone, f))
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Price check
        if "price" in df.columns:
            bad = pd.to_numeric(df["price"], errors="coerce").isna().sum()
            if bad > 0:
                bad_vals = df[pd.to_numeric(df["price"], errors="coerce").isna()]["price"].dropna().unique().tolist()
                errors.append(
                    f"DataTypeError in {f} → 'price' column: "
                    f"{bad} non-numeric value(s) {bad_vals[:3]}. Skipping file."
                )
                continue

        df = df.dropna(how="all")
        if len(df) == 0:
            errors.append(f"EmptyDataError in {f}: 0 rows after cleaning")
            continue

        df.to_csv(os.path.join(staging, f"cleaned_{f}"), index=False)
        cleaned_dfs.append(df)
        print(f"Cleaned {f}: {len(df)} rows")

    if errors:
        raise ValueError(
            f"clean_and_transform failed with {len(errors)} error(s):\n"
            + "\n".join(f"  {e}" for e in errors)
        )

    if not cleaned_dfs:
        raise FileNotFoundError("No files were successfully cleaned. Check raw zone.")

    combined = pd.concat(cleaned_dfs, ignore_index=True)

    if "status" in combined.columns:
        agg = combined.groupby("status").agg("count").reset_index()
        agg.to_csv(os.path.join(processed, "status_aggregation.csv"), index=False)

    combined.to_csv(os.path.join(processed, "combined_data.csv"), index=False)

    # Enrich
    for fname in os.listdir(processed):
        if not fname.endswith(".csv") or fname.startswith("."):
            continue
        df = pd.read_csv(os.path.join(processed, fname))
        df["_processed_at"]      = datetime.utcnow().isoformat()
        df["_source_file"]       = fname
        df["_pipeline_version"]  = "1.0.0"
        df.to_csv(os.path.join(curated_zone, f"curated_{fname}"), index=False)

    print(f"Transformation complete: {len(combined)} rows → curated zone")


# ─────────────────────────────────────────────────────────────
# STEP 4 — Quality checks
# ─────────────────────────────────────────────────────────────

def run_quality_checks(**context):
    """Run all data quality checks on curated data.

    Checks:
      - All metadata columns present
      - No column has >10% nulls
      - At least 3 rows per file
      - No >5% duplicate rows
    """
    import os

    import pandas as pd

    curated = os.getenv("CURATED_ZONE", "/data/curated")
    threshold_null = float(os.getenv("NULL_RATIO_THRESHOLD", "0.10"))
    min_rows       = int(os.getenv("MIN_EXPECTED_ROWS", "3"))
    max_dup_ratio  = float(os.getenv("MAX_DUPLICATE_RATIO", "0.05"))

    csvs = [f for f in os.listdir(curated) if f.endswith(".csv") and not f.startswith(".")]
    if not csvs:
        raise FileNotFoundError(
            "QualityCheckError: No files in curated zone. "
            "clean_and_transform must complete first."
        )

    errors = []
    for f in csvs:
        df = pd.read_csv(os.path.join(curated, f))

        # Schema
        for col in ["_processed_at", "_source_file", "_pipeline_version"]:
            if col not in df.columns:
                errors.append(f"SchemaError in {f}: missing metadata column '{col}'")

        # Row count
        if len(df) < min_rows:
            errors.append(
                f"RowCountError in {f}: only {len(df)} row(s) (min: {min_rows})"
            )

        # Null ratios — this FAILS for combined data from different schemas
        for col in [c for c in df.columns if not c.startswith("_")]:
            ratio = df[col].isnull().sum() / len(df) if len(df) > 0 else 0
            if ratio > threshold_null:
                errors.append(
                    f"NullRatioError in {f} → '{col}': {ratio:.1%} nulls "
                    f"(threshold: {threshold_null:.0%}). "
                    f"Likely caused by merging files with different schemas — "
                    f"each file's columns are NULL for rows from other files."
                )

        # Duplicates
        data_cols = [c for c in df.columns if not c.startswith("_")]
        if data_cols:
            dup_ratio = df.duplicated(subset=data_cols).sum() / len(df)
            if dup_ratio > max_dup_ratio:
                errors.append(
                    f"DuplicateError in {f}: {dup_ratio:.1%} duplicates (max: {max_dup_ratio:.0%})"
                )

    if errors:
        raise ValueError(
            f"Quality checks FAILED with {len(errors)} issue(s):\n"
            + "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(errors))
        )

    print(f"All quality checks PASSED for {len(csvs)} curated file(s)")


# ─────────────────────────────────────────────────────────────
# STEP 5 — ML Training
# ─────────────────────────────────────────────────────────────

def train_and_evaluate(**context):
    """Build features, train model, enforce accuracy >= 0.6.

    PASSES with 70-row sales_data.csv.
    FAILS if data is too small or corrupted.
    """
    import json
    import os
    import pickle

    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    curated   = os.getenv("CURATED_ZONE", "/data/curated")
    feat_dir  = os.getenv("FEATURES_DIR", "/data/features")
    model_dir = os.getenv("MODELS_DIR", "/data/models")

    for d in [feat_dir, model_dir]:
        os.makedirs(d, exist_ok=True)

    dfs = [
        pd.read_csv(os.path.join(curated, f))
        for f in os.listdir(curated)
        if f.endswith(".csv") and not f.startswith(".")
    ]

    if not dfs:
        raise FileNotFoundError(
            "MLError: No curated data found. Run quality_checks first."
        )

    combined = pd.concat(dfs, ignore_index=True)
    data_cols = [c for c in combined.columns if not c.startswith("_")]
    features = combined[data_cols].copy()

    for col in features.select_dtypes(include=["object"]).columns:
        features[col] = features[col].astype("category").cat.codes
    features = features.fillna(0)

    if len(features) < 10:
        raise ValueError(
            f"MLError: Only {len(features)} rows available for training. "
            f"Need at least 10 rows. Add more data to landing/sales_data.csv."
        )

    X, y = features.iloc[:, :-1], features.iloc[:, -1]
    if y.dtype in ["float64", "float32"]:
        y = pd.qcut(y, q=3, labels=["low", "med", "high"], duplicates="drop").cat.codes

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    accuracy = model.score(X_test, y_test)

    with open(os.path.join(model_dir, "model.pkl"), "wb") as f:
        pickle.dump(model, f)

    metrics = {"accuracy": round(accuracy, 4), "n_train": len(X_train), "n_test": len(X_test)}
    with open(os.path.join(model_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    min_acc = float(os.getenv("MIN_MODEL_ACCURACY", "0.6"))
    print(f"Model accuracy: {accuracy:.4f} (threshold: {min_acc})")

    if accuracy < min_acc:
        raise ValueError(
            f"ModelQualityError: Accuracy {accuracy:.4f} ({accuracy:.1%}) below threshold {min_acc:.1%}. "
            f"Training set had {len(X_train)} rows. "
            f"Add more data to landing/sales_data.csv to improve model quality."
        )

    print(f"ML pipeline PASSED — accuracy: {accuracy:.4f} — model saved")


# ─────────────────────────────────────────────────────────────
# STEP 6 — Cleanup (restore clean state)
# ─────────────────────────────────────────────────────────────

def cleanup_demo(**context):
    """Remove bad_orders.csv from landing/ after demo run (restores clean state)."""
    import os

    landing = os.getenv("LANDING_ZONE", "/data/landing")
    bad_dst = os.path.join(landing, "bad_orders.csv")

    if os.path.exists(bad_dst):
        os.remove(bad_dst)
        print("Cleanup: removed bad_orders.csv from landing/ — pipeline restored to clean state")
    else:
        print("Cleanup: nothing to remove — already clean")


# ─────────────────────────────────────────────────────────────
# DAG definition
# ─────────────────────────────────────────────────────────────

with DAG(
    dag_id="demo_pipeline",
    default_args=default_args,
    description=(
        "Full pipeline demo. Trigger with config: "
        '{"inject_bad_data": true} for failure demo, '
        '{"inject_bad_data": false} for clean run.'
    ),
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["demo", "observability", "data-platform"],
    params={"inject_bad_data": False},
) as dag:

    t_setup = PythonOperator(
        task_id="setup_demo_data",
        python_callable=setup_demo_data,
    )

    t_ingest_csv = PythonOperator(
        task_id="ingest_csv_files",
        python_callable=ingest_all_files,
    )

    t_ingest_api = PythonOperator(
        task_id="ingest_api_data",
        python_callable=ingest_api_records,
    )

    t_validate = PythonOperator(
        task_id="validate_raw_data",
        python_callable=validate_ingested_data,
    )

    t_transform = PythonOperator(
        task_id="clean_and_transform",
        python_callable=clean_and_transform,
    )

    t_quality = PythonOperator(
        task_id="run_quality_checks",
        python_callable=run_quality_checks,
    )

    t_ml = PythonOperator(
        task_id="train_and_evaluate_model",
        python_callable=train_and_evaluate,
    )

    t_cleanup = PythonOperator(
        task_id="cleanup_demo",
        python_callable=cleanup_demo,
        trigger_rule="all_done",   # runs even if earlier tasks failed
    )

    # Full pipeline flow
    t_setup >> [t_ingest_csv, t_ingest_api] >> t_validate >> t_transform >> t_quality >> t_ml >> t_cleanup
