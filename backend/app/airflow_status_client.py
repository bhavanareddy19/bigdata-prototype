from __future__ import annotations

import os
import requests
from requests.auth import HTTPBasicAuth


def _get_base_url() -> str:
    return os.getenv("AIRFLOW_BASE_URL", "").strip().rstrip("/")


def _get_auth():
    """Return auth for Airflow requests.

    - GCP Cloud Composer: uses IAM Bearer token (GOOGLE_API_KEY / ADC)
    - Local / self-hosted Airflow: uses AIRFLOW_USERNAME + AIRFLOW_PASSWORD
    """
    username = os.getenv("AIRFLOW_USERNAME", "").strip()
    password = os.getenv("AIRFLOW_PASSWORD", "").strip()

    # Try GCP IAM first (Cloud Composer requires Bearer token, not basic auth)
    base_url = _get_base_url()
    is_composer = "composer.googleusercontent.com" in base_url

    if is_composer:
        try:
            import google.auth
            import google.auth.transport.requests
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            return None, {"Authorization": f"Bearer {credentials.token}"}
        except Exception as e:
            print(f"[airflow_client] GCP auth failed, trying basic auth: {e}")

    # Basic auth for local / self-hosted Airflow
    if username and password:
        return HTTPBasicAuth(username, password), {}

    return None, {}


def _api(path: str) -> str:
    return f"{_get_base_url()}/api/v1{path}"


def _get(path: str, params: dict | None = None) -> dict:
    auth, headers = _get_auth()
    resp = requests.get(
        _api(path),
        auth=auth,
        headers=headers,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def list_dags(limit: int = 100) -> list[dict]:
    return _get("/dags", params={"limit": limit}).get("dags", [])


def list_dag_runs(dag_id: str, limit: int = 5) -> list[dict]:
    return _get(f"/dags/{dag_id}/dagRuns", params={"limit": limit}).get("dag_runs", [])


def list_task_instances(dag_id: str, dag_run_id: str) -> list[dict]:
    return _get(f"/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances").get("task_instances", [])


def trigger_dag(dag_id: str, conf: dict | None = None) -> dict:
    """Trigger a DAG run via the Airflow REST API."""
    auth, headers = _get_auth()
    headers["Content-Type"] = "application/json"
    resp = requests.post(
        _api(f"/dags/{dag_id}/dagRuns"),
        auth=auth,
        headers=headers,
        json={"conf": conf or {}},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def unpause_dag(dag_id: str) -> dict:
    """Unpause a DAG so it can be triggered."""
    auth, headers = _get_auth()
    headers["Content-Type"] = "application/json"
    resp = requests.patch(
        _api(f"/dags/{dag_id}"),
        auth=auth,
        headers=headers,
        json={"is_paused": False},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
