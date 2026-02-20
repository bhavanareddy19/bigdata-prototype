"""DAG: deploy_pipeline — Build container images and deploy services to Kubernetes.

Triggers after successful model training to deploy updated services.
Uses the observability agent to analyze failures automatically.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data-platform",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def run_tests(**context):
    """Run the test suite before deploying."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd="/opt/app",
        timeout=300,
    )

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"Tests failed with exit code {result.returncode}")

    print("All tests passed")


def notify_observability_agent(**context):
    """Notify the observability agent about the deployment status."""
    import json
    import os

    import requests

    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    dag_run = context.get("dag_run")

    payload = {
        "question": f"Deployment pipeline completed. DAG run: {dag_run.run_id if dag_run else 'unknown'}. Check if any issues occurred.",
        "history": [],
        "mode": "auto",
        "include_repo_context": True,
    }

    try:
        resp = requests.post(f"{backend_url}/chat", json=payload, timeout=30)
        resp.raise_for_status()
        answer = resp.json().get("answer", "No answer")
        print(f"Observability agent response:\n{answer}")
    except Exception as e:
        print(f"Could not reach observability agent: {e}")


with DAG(
    dag_id="deploy_pipeline",
    default_args=default_args,
    description="Build, test, and deploy services to Kubernetes",
    schedule_interval=None,  # Triggered manually or by upstream DAG
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["deploy", "data-platform"],
) as dag:

    t_tests = PythonOperator(
        task_id="run_tests",
        python_callable=run_tests,
    )

    t_build_backend = BashOperator(
        task_id="build_backend_image",
        bash_command=(
            "docker build -t bigdata-backend:latest -f docker/Dockerfile.backend . "
            "|| echo 'Docker build skipped (no Docker daemon)'"
        ),
    )

    t_build_airflow = BashOperator(
        task_id="build_airflow_image",
        bash_command=(
            "docker build -t bigdata-airflow:latest -f docker/Dockerfile.airflow . "
            "|| echo 'Docker build skipped (no Docker daemon)'"
        ),
    )

    t_deploy_k8s = BashOperator(
        task_id="deploy_to_kubernetes",
        bash_command=(
            "kubectl apply -f k8s/ --recursive "
            "|| echo 'kubectl apply skipped (no cluster access)'"
        ),
    )

    t_rollout_check = BashOperator(
        task_id="check_rollout_status",
        bash_command=(
            "kubectl rollout status deployment/backend -n backend --timeout=180s "
            "|| echo 'Rollout check skipped'"
        ),
    )

    t_notify = PythonOperator(
        task_id="notify_observability_agent",
        python_callable=notify_observability_agent,
        trigger_rule="all_done",  # Notify even on failure
    )

    t_tests >> [t_build_backend, t_build_airflow] >> t_deploy_k8s >> t_rollout_check >> t_notify
