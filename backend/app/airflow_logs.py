from __future__ import annotations

import os
from typing import Optional

import requests


def _get_airflow_base_url(explicit: Optional[str]) -> str:
    base = (explicit or os.getenv("AIRFLOW_BASE_URL", "")).strip()
    if not base:
        raise ValueError("Airflow base URL not provided. Set AIRFLOW_BASE_URL or pass airflow_base_url.")
    return base.rstrip("/")


def _get_airflow_auth() -> tuple[str, str] | None:
    user = os.getenv("AIRFLOW_USERNAME", "").strip()
    pwd = os.getenv("AIRFLOW_PASSWORD", "").strip()
    if user and pwd:
        return (user, pwd)
    return None


def fetch_airflow_task_logs(
    *,
    airflow_base_url: Optional[str],
    dag_id: str,
    dag_run_id: str,
    task_id: str,
    try_number: int,
    full_content: bool = False,
) -> str:
    """Fetch task instance logs via Airflow REST API.

    Notes:
    - Endpoint exists in Airflow 2.x. Some managed Airflow setups store logs in cloud logging.
      If this endpoint is unavailable, you can switch to fetching logs from CloudWatch/GCS/Loki.
    """

    base = _get_airflow_base_url(airflow_base_url)
    auth = _get_airflow_auth()

    url = (
        f"{base}/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}/logs/{try_number}"
    )
    params = {"full_content": "true" if full_content else "false"}

    r = requests.get(url, params=params, auth=auth, timeout=60)
    r.raise_for_status()

    # Airflow 2.6+ may return plain text logs or JSON depending on version/config
    content_type = r.headers.get("Content-Type", "")
    if "application/json" in content_type:
        data = r.json()
        content = data.get("content", "")
        if not isinstance(content, str):
            raise ValueError("Unexpected Airflow log response shape; expected JSON with 'content' string.")
        return content
    else:
        # Plain text response (Airflow 2.8+ default)
        text = r.text.strip()
        if not text:
            raise ValueError("Airflow returned empty log content.")
        return text
