from __future__ import annotations

import requests
from typing import Any
import google.auth
from google.auth.transport.requests import AuthorizedSession
from .settings import get_airflow_base_url

AUTH_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
CREDENTIALS, _ = google.auth.default(scopes=[AUTH_SCOPE])
SESSION = AuthorizedSession(CREDENTIALS)


def _api(path: str) -> str:
    base = get_airflow_base_url().rstrip("/")
    return f"{base}/api/v2{path}"


def _get(path: str, **kwargs: Any) -> dict:
    resp = SESSION.get(_api(path), timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def list_dag_runs(dag_id: str, limit: int = 5) -> list[dict]:
    data = _get(f"/dags/{dag_id}/dagRuns", params={"limit": limit})
    return data.get("dag_runs", [])


def list_task_instances(dag_id: str, dag_run_id: str) -> list[dict]:
    data = _get(f"/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances")
    return data.get("task_instances", [])