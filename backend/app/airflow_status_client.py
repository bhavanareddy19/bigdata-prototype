from __future__ import annotations
import os
import requests
import google.auth
import google.auth.transport.requests

def _get_base_url() -> str:
    return os.getenv("AIRFLOW_BASE_URL", "").strip().rstrip("/")

def _get_headers() -> dict:
    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        return {"Authorization": f"Bearer {credentials.token}"}
    except Exception as e:
        print(f"Auth error: {e}")
        return {}

def _api(path: str) -> str:
    return f"{_get_base_url()}/api/v1{path}"

def _get(path: str, params: dict = None) -> dict:
    resp = requests.get(_api(path), headers=_get_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()

def list_dags(limit: int = 100) -> list[dict]:
    return _get("/dags", params={"limit": limit}).get("dags", [])

def list_dag_runs(dag_id: str, limit: int = 5) -> list[dict]:
    return _get(f"/dags/{dag_id}/dagRuns", params={"limit": limit}).get("dag_runs", [])

def list_task_instances(dag_id: str, dag_run_id: str) -> list[dict]:
    return _get(f"/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances").get("task_instances", [])