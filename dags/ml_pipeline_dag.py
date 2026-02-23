"""DAG: ml_pipeline — Feature engineering + model training pipeline.

Reads curated data, builds features, trains scikit-learn model, saves artifacts.
OpenLineage tracks dataset lineage through the ML lifecycle.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def build_features(**context):
    """Create ML features from curated datasets."""
    import os

    import pandas as pd

    curated_zone = os.getenv("CURATED_ZONE", "/data/curated")
    features_dir = os.getenv("FEATURES_DIR", "/data/features")
    os.makedirs(features_dir, exist_ok=True)

    dfs = []
    for f in os.listdir(curated_zone):
        if f.endswith(".csv"):
            dfs.append(pd.read_csv(os.path.join(curated_zone, f)))

    if not dfs:
        print("No curated data to build features from")
        return

    combined = pd.concat(dfs, ignore_index=True)

    # Drop metadata columns
    data_cols = [c for c in combined.columns if not c.startswith("_")]
    features = combined[data_cols].copy()

    # Simple feature engineering: encode categorical, fill nulls
    for col in features.select_dtypes(include=["object"]).columns:
        features[col] = features[col].astype("category").cat.codes

    features = features.fillna(0)

    output = os.path.join(features_dir, "features.csv")
    features.to_csv(output, index=False)
    print(f"Built features: {features.shape} → {output}")
    context["ti"].xcom_push(key="features_path", value=output)


def train_model(**context):
    """Train a simple scikit-learn model and save it."""
    import os
    import pickle

    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    features_dir = os.getenv("FEATURES_DIR", "/data/features")
    models_dir = os.getenv("MODELS_DIR", "/data/models")
    os.makedirs(models_dir, exist_ok=True)

    features_path = os.path.join(features_dir, "features.csv")
    if not os.path.exists(features_path):
        raise FileNotFoundError(f"Features not found: {features_path}")

    df = pd.read_csv(features_path)
    if len(df) < 5 or len(df.columns) < 2:
        print("Not enough data to train — skipping")
        return

    # Use last column as target (demo purpose)
    X = df.iloc[:, :-1]
    y = df.iloc[:, -1]

    # Bin target into classes if continuous
    if y.dtype in ["float64", "float32"]:
        y = pd.qcut(y, q=3, labels=["low", "med", "high"], duplicates="drop")
        y = y.cat.codes

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    score = model.score(X_test, y_test)

    model_path = os.path.join(models_dir, "model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    metrics_path = os.path.join(models_dir, "metrics.json")
    import json

    with open(metrics_path, "w") as f:
        json.dump({"accuracy": round(score, 4), "n_train": len(X_train), "n_test": len(X_test)}, f, indent=2)

    print(f"Model trained — accuracy: {score:.4f} — saved to {model_path}")
    context["ti"].xcom_push(key="model_accuracy", value=score)


def evaluate_model(**context):
    """Load the trained model and produce evaluation summary."""
    import json
    import os

    models_dir = os.getenv("MODELS_DIR", "/data/models")
    metrics_path = os.path.join(models_dir, "metrics.json")

    if not os.path.exists(metrics_path):
        print("No metrics file found — skipping evaluation")
        return

    with open(metrics_path, "r") as f:
        metrics = json.load(f)

    accuracy = metrics.get("accuracy", 0)
    min_accuracy = float(os.getenv("MIN_MODEL_ACCURACY", "0.5"))

    if accuracy < min_accuracy:
        raise ValueError(f"Model accuracy {accuracy:.4f} is below minimum threshold {min_accuracy}")

    print(f"Model evaluation PASSED — accuracy: {accuracy:.4f}")


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
