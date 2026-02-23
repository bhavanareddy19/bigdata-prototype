"""DAG: demo_observability — Intentionally fails so you can test the AI chatbot.

PURPOSE:
    This DAG exists purely to generate realistic failures.
    Trigger it, let it fail, then open the chatbot (localhost:8501) and ask:
    "Why did the demo_observability DAG fail? How do I fix it?"

TASKS:
    1. task_ok          — succeeds (shows a healthy task)
    2. task_fail_data   — fails with a missing-file/data error (DataQuality category)
    3. task_fail_code   — fails with a Python TypeError (CodeLogic category)
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 0,  # No retries — fail fast for demo
    "retry_delay": timedelta(minutes=1),
}


def task_ok(**context):
    """This task succeeds — it represents a healthy upstream step."""
    print("=== task_ok: Reading sample data from landing zone ===")
    import os
    landing = os.getenv("LANDING_ZONE", "/data/landing")
    files = os.listdir(landing) if os.path.exists(landing) else []
    print(f"Found {len(files)} files in landing zone: {files}")
    print("task_ok: SUCCESS")


def task_fail_data(**context):
    """This task fails because it expects a file that doesn't exist yet.

    The AI chatbot should detect this as a DataQuality / missing-file error
    and suggest running data_ingestion first.
    """
    import os
    import pandas as pd

    # This file won't exist unless data_transformation already ran
    expected_file = os.getenv("CURATED_ZONE", "/data/curated") + "/curated_combined_data.csv"

    print(f"=== task_fail_data: Loading curated dataset ===")
    print(f"Looking for: {expected_file}")

    if not os.path.exists(expected_file):
        raise FileNotFoundError(
            f"Required dataset not found: {expected_file}\n"
            f"This usually means the data_transformation DAG has not run yet, "
            f"or the curated zone is empty. "
            f"Run data_ingestion → data_transformation first."
        )

    df = pd.read_csv(expected_file)

    # Check required columns
    required_cols = ["product_id", "amount", "status", "_processed_at"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Schema mismatch — missing columns: {missing}\n"
            f"Expected: {required_cols}\n"
            f"Got: {list(df.columns)}"
        )

    print(f"Loaded {len(df)} rows. Columns: {list(df.columns)}")


def task_fail_code(**context):
    """This task fails with a Python exception (type error in business logic).

    The AI chatbot should detect this as a CodeLogic error and point to the
    exact line causing the issue.
    """
    print("=== task_fail_code: Computing revenue aggregation ===")

    # Simulated data — mixing string and number types (common real-world bug)
    records = [
        {"product": "Widget A", "revenue": 1500.0},
        {"product": "Widget B", "revenue": "NOT_A_NUMBER"},  # ← bug: bad data
        {"product": "Widget C", "revenue": 3200.5},
    ]

    print(f"Processing {len(records)} records...")

    total = 0
    for rec in records:
        product = rec["product"]
        revenue = rec["revenue"]
        print(f"  Adding {product}: {revenue}")
        total += revenue  # ← TypeError: unsupported operand type(s) for +=: 'float' and 'str'

    print(f"Total revenue: {total}")  # Never reached


with DAG(
    dag_id="demo_observability",
    default_args=default_args,
    description="Demo DAG that intentionally fails — for testing the AI observability chatbot",
    schedule=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["demo", "observability"],
) as dag:

    t_ok = PythonOperator(
        task_id="task_ok",
        python_callable=task_ok,
    )

    t_fail_data = PythonOperator(
        task_id="task_fail_data",
        python_callable=task_fail_data,
    )

    t_fail_code = PythonOperator(
        task_id="task_fail_code",
        python_callable=task_fail_code,
    )

    # t_ok runs first (succeeds), then both failure tasks run in parallel
    t_ok >> [t_fail_data, t_fail_code]
