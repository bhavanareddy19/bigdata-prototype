from __future__ import annotations

from datetime import datetime, timezone

from .airflow_logs import fetch_airflow_task_logs
from .airflow_status_client import list_dag_runs, list_task_instances
from .log_analyzer import analyze_logs
from .ops_store import load_ops_snapshot, save_ops_snapshot
from .settings import get_airflow_base_url

CORE_DAGS = [
    "data_ingestion",
    "data_transformation",
    "data_quality_checks",
    "ml_pipeline",
    "demo_pipeline",
    "demo_observability",
    "deploy_pipeline",
]

from google.cloud import storage
from .settings import get_gcs_data_bucket


def get_ingestion_gcs_status() -> dict:
    bucket_name = get_gcs_data_bucket()
    if not bucket_name:
        return {
            "dag_id": "data_ingestion",
            "latest_state": "UNKNOWN",
            "gcs_error": "GCS_DATA_BUCKET not configured",
        }

    client = storage.Client()
    blobs = list(client.list_blobs(bucket_name, prefix="raw/", max_results=20))

    real_files = [
        b.name for b in blobs
        if not b.name.endswith("/") and not b.name.endswith(".keep")
    ]

    if real_files:
        return {
            "dag_id": "data_ingestion",
            "latest_state": "SUCCESS_FROM_GCS",
            "raw_file_count": len(real_files),
            "sample_files": real_files[:5],
        }

    return {
        "dag_id": "data_ingestion",
        "latest_state": "NO_RAW_OUTPUT",
        "raw_file_count": 0,
    }


def build_ops_snapshot() -> dict:
    dags_out = []
    failures = []

    for dag_id in CORE_DAGS:
        try:
            runs = list_dag_runs(dag_id, limit=3)
        except Exception as e:
            if dag_id == "data_ingestion":
                fallback = get_ingestion_gcs_status()
                fallback["debug_error"] = str(e)
                dags_out.append(fallback)
            else:
                dags_out.append({
                    "dag_id": dag_id,
                    "latest_state": "UNKNOWN",
                    "error": str(e),
                })
            continue

        if not runs:
            dags_out.append({
                "dag_id": dag_id,
                "latest_state": "NO_RUNS",
            })
            continue

        latest = runs[0]
        dag_run_id = latest.get("dag_run_id")
        dag_state = latest.get("state", "UNKNOWN")

        dag_entry = {
            "dag_id": dag_id,
            "dag_run_id": dag_run_id,
            "latest_state": dag_state,
            "start_date": latest.get("start_date"),
            "end_date": latest.get("end_date"),
            "tasks": [],
        }

        try:
            tasks = list_task_instances(dag_id, dag_run_id)
        except Exception as e:
            dag_entry["task_error"] = str(e)
            dags_out.append(dag_entry)
            continue

        for t in tasks:
            task_state = t.get("state", "UNKNOWN")
            task_id = t.get("task_id")
            try_number = t.get("try_number", 1)

            dag_entry["tasks"].append({
                "task_id": task_id,
                "state": task_state,
                "try_number": try_number,
                "start_date": t.get("start_date"),
                "end_date": t.get("end_date"),
            })

            if task_state == "failed":
                failure_item = {
                    "dag_id": dag_id,
                    "dag_run_id": dag_run_id,
                    "task_id": task_id,
                    "try_number": try_number,
                    "state": task_state,
                }

                try:
                    logs = fetch_airflow_task_logs(
                        airflow_base_url=get_airflow_base_url(),
                        dag_id=dag_id,
                        dag_run_id=dag_run_id,
                        task_id=task_id,
                        try_number=try_number,
                        full_content=False,
                    )
                    analysis = analyze_logs(
                        log_text=logs,
                        max_lines=250,
                        mode="heuristic",
                    )
                    failure_item["summary"] = {
                        "category": analysis.category,
                        "signature": analysis.error_signature,
                        "root_cause": analysis.suspected_root_cause,
                        "next_actions": analysis.next_actions,
                    }
                except Exception as e:
                    failure_item["summary_error"] = str(e)

                failures.append(failure_item)

        dags_out.append(dag_entry)

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dags": dags_out,
        "recent_failures": failures[:10],
    }
    return snapshot


def sync_airflow_ops() -> dict:
    snapshot = build_ops_snapshot()
    save_ops_snapshot(snapshot)
    return snapshot


def get_ops_summary() -> dict:
    return load_ops_snapshot()