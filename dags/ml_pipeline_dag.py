"""DAG: ml_pipeline — Feature engineering + model training pipeline.

Reads curated data, builds features, trains scikit-learn model, saves artifacts.
OpenLineage tracks dataset lineage through the ML lifecycle.

Failure scenarios (for observability testing):
  - build_features: fails if curated zone is empty (data_transformation didn't run)
  - train_model: fails if features.csv has fewer than 5 rows (not enough training data)
  - evaluate_model: fails if model accuracy < 0.6 threshold
    (likely with small dataset — catches "not enough data" problem)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.storage_paths import build_paths
from utils.storage_io import ensure_dir, list_files, join_path, copy_file, write_text, path_exists
from utils.lineage import emit_dataset_lineage
paths = build_paths()

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def build_features(**context):
    """Create ML features from curated datasets.

    Failure scenarios:
      - FileNotFoundError: curated zone empty — data_transformation didn't run
      - ValueError: after feature engineering, too few usable columns remain
    """
    import os

    import pandas as pd

    curated_zone = paths["curated"]
    features_dir = paths["features"]
    ensure_dir(features_dir, exist_ok=True)

    csv_files = [f for f in join_path(curated_zone) if f.endswith(".csv") and not f.startswith(".")]

    if not csv_files:
        raise FileNotFoundError(
            "FeatureBuildError: No curated CSV files found. "
            f"Curated zone is empty: {curated_zone}. "
            "The data_transformation DAG must run successfully before ml_pipeline. "
            "Run: data_ingestion → data_transformation → ml_pipeline in order."
        )

    dfs = []
    for f in csv_files:
        dfs.append(pd.read_csv(join_path(curated_zone, f)))

    combined = pd.concat(dfs, ignore_index=True)

    # Drop metadata columns — not useful as features
    data_cols = [c for c in combined.columns if not c.startswith("_")]
    features = combined[data_cols].copy()

    if len(features.columns) < 2:
        raise ValueError(
            f"FeatureBuildError: Only {len(features.columns)} usable column(s) after dropping metadata. "
            f"Need at least 2 columns (features + target). "
            f"Check that data_transformation is producing complete datasets."
        )

    # Encode categoricals, fill nulls
    for col in features.select_dtypes(include=["object"]).columns:
        features[col] = features[col].astype("category").cat.codes

    features = features.fillna(0)

    output = join_path(features_dir, "features.csv")
    features.to_csv(output, index=False)
    print(f"Built features: {features.shape[0]} rows × {features.shape[1]} columns → {output}")
    context["ti"].xcom_push(key="features_path", value=output)
    context["ti"].xcom_push(key="feature_count", value=features.shape[0])
    emit_dataset_lineage(
        job_name="ml_pipeline.build_features",
        inputs=["curated/curated_combined_data.csv", "curated/curated_status_aggregation.csv"],
        outputs=["features/features.csv"],
    )


def train_model(**context):
    """Train a RandomForestClassifier and save the model artifact.

    Failure scenarios:
      - FileNotFoundError: features.csv not found (build_features didn't run)
      - ValueError: fewer than 5 rows — cannot split into train/test meaningfully
    """
    import json
    import os
    import pickle

    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    features_dir = paths["features"]
    models_dir = paths["models"]
    ensure_dir(models_dir, exist_ok=True)

    features_path = join_path(features_dir, "features.csv")
    if not path_exists(features_path):
        raise FileNotFoundError(
            f"TrainError: Features file not found at {features_path}. "
            "build_features task must complete before train_model. "
            "Check build_features task logs."
        )

    df = pd.read_csv(features_path)

    if len(df) < 5:
        raise ValueError(
            f"TrainError: Only {len(df)} row(s) in features.csv — not enough to train a model. "
            f"Need at least 5 rows for a meaningful train/test split. "
            f"Run data_ingestion with more source data in landing/ folder, "
            f"then re-run data_transformation → ml_pipeline."
        )

    # Use last column as target
    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]

    # Bin continuous target into classes
    if y.dtype in ["float64", "float32"]:
        y = pd.qcut(y, q=3, labels=["low", "med", "high"], duplicates="drop")
        y = y.cat.codes

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)

    model_path = join_path(models_dir, "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    metrics = {
        "accuracy": round(score, 4),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_features": X.shape[1],
    }
    with open(join_path(models_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Model trained — accuracy: {score:.4f} — n_train: {len(X_train)} — saved to {model_path}")
    context["ti"].xcom_push(key="model_accuracy", value=score)
    emit_dataset_lineage(
        job_name="ml_pipeline.train_model",
        inputs=["features/features.csv"],
        outputs=["models/model.pkl", "models/metrics.json"],
    )


def evaluate_model(**context):
    """Load metrics and enforce minimum accuracy threshold.

    Failure scenarios:
      - ValueError: accuracy below 0.6 threshold — model is not good enough to deploy.
        This happens when training data is too small (< 20 rows) or data quality is poor.
        With the sample dataset (~10 rows), this will FAIL — by design.
        Fix: add more data to landing/ folder or improve feature engineering.
    """
    import json
    import os

    models_dir = paths["models"]
    metrics_path = join_path(models_dir, "metrics.json")

    if not path_exists(metrics_path):
        raise FileNotFoundError(
            f"EvaluationError: metrics.json not found at {metrics_path}. "
            "train_model task must complete before evaluate_model."
        )

    with open(metrics_path) as f:
        metrics = json.load(f)

    accuracy = metrics.get("accuracy", 0)
    n_train = metrics.get("n_train", 0)
    n_test = metrics.get("n_test", 0)
    # Minimum acceptable accuracy — 60%
    min_accuracy = float(os.getenv("MIN_MODEL_ACCURACY", "0.6"))

    print(f"Model metrics: accuracy={accuracy:.4f}, n_train={n_train}, n_test={n_test}")

    if accuracy < min_accuracy:
        raise ValueError(
            f"ModelQualityError: Model accuracy {accuracy:.4f} ({accuracy:.1%}) is below "
            f"the minimum deployment threshold of {min_accuracy:.1%}. "
            f"Training set had only {n_train} row(s) — model likely underfit. "
            f"To fix: add more rows to landing/sales_data.csv (need at least 50+ rows), "
            f"then re-run data_ingestion → data_transformation → ml_pipeline."
        )

    print(f"Model evaluation PASSED — accuracy {accuracy:.4f} >= threshold {min_accuracy}")
    emit_dataset_lineage(
        job_name="ml_pipeline.evaluate_model",
        inputs=["models/metrics.json"],
        outputs=[],
    )


with DAG(
    dag_id="ml_pipeline",
    default_args=default_args,
    description="Feature engineering and model training pipeline",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["ml", "data-platform"],
) as dag:

    t_features = PythonOperator(
        task_id="build_features",
        python_callable=build_features,
    )

    t_train = PythonOperator(
        task_id="train_model",
        python_callable=train_model,
    )

    t_eval = PythonOperator(
        task_id="evaluate_model",
        python_callable=evaluate_model,
    )

    t_features >> t_train >> t_eval
