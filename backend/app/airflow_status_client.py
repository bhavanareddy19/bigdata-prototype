from __future__ import annotations

import os
from typing import Any

import requests
from .settings import get_airflow_base_url


def _api(path: str) -> str:
    base = get_airflow_base_url().rstrip("/")
    return f"{base}/api/v1{path}"


def _auth() -> tuple[str, str] | None:
    user = os.getenv("AIRFLOW_USERNAME", "").strip()
    pwd = os.getenv("AIRFLOW_PASSWORD", "").strip()
    if user and pwd:
        return (user, pwd)
    return None


def _get(path: str, **kwargs: Any) -> dict:
    resp = requests.get(_api(path), auth=_auth(), timeout=30, **kwargs)
    resp.raise_for_status()
    return resp.json()


def list_dags() -> list[dict]:
    data = _get("/dags")
    return data.get("dags", [])


def list_dag_runs(dag_id: str, limit: int = 5) -> list[dict]:
    data = _get(f"/dags/{dag_id}/dagRuns", params={
        "limit": limit,
        "order_by": "-start_date",
    })
    return data.get("dag_runs", [])


def list_task_instances(dag_id: str, dag_run_id: str) -> list[dict]:
    data = _get(f"/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances")
    return data.get("task_instances", [])
