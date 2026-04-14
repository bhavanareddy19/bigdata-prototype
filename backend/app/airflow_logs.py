from __future__ import annotations

import os
from typing import Optional
import requests
import google.auth
import google.auth.transport.requests


def _get_airflow_base_url(explicit: Optional[str]) -> str:
    base = (explicit or os.getenv("AIRFLOW_BASE_URL", "")).strip()
    if not base:
        raise ValueError("Airflow base URL not provided.")
    return base.rstrip("/")


def _get_auth(base_url: str):
    """Return (auth, headers) for Airflow requests.

    Cloud Composer: IAM Bearer token.
    Local / self-hosted: HTTP basic auth.
    """
    is_composer = "composer.googleusercontent.com" in base_url
    if is_composer:
        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            auth_req = google.auth.transport.requests.Request()
            credentials.refresh(auth_req)
            return None, {"Authorization": f"Bearer {credentials.token}"}
        except Exception as e:
            print(f"[airflow_logs] GCP auth failed: {e}")

    username = os.getenv("AIRFLOW_USERNAME", "").strip()
    password = os.getenv("AIRFLOW_PASSWORD", "").strip()
    if username and password:
        from requests.auth import HTTPBasicAuth
        return HTTPBasicAuth(username, password), {}
    return None, {}


def fetch_airflow_task_logs(
    *,
    airflow_base_url: Optional[str],
    dag_id: str,
    dag_run_id: str,
    task_id: str,
    try_number: int,
    full_content: bool = False,
) -> str:
    base = _get_airflow_base_url(airflow_base_url)
    auth, headers = _get_auth(base)

    url = f"{base}/api/v1/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}/logs/{try_number}"
    params = {"full_content": "true" if full_content else "false"}

    r = requests.get(url, auth=auth, headers=headers, params=params, timeout=60)
    r.raise_for_status()

    content_type = r.headers.get("Content-Type", "")
    if "application/json" in content_type:
        data = r.json()
        content = data.get("content", "")
        if not isinstance(content, str):
            raise ValueError("Unexpected Airflow log response shape.")
        return content
    else:
        text = r.text.strip()
        if not text:
            raise ValueError("Airflow returned empty log content.")
        # Guard against HTML responses (auth redirect)
        if text.startswith("<!") or text.startswith("<html"):
            raise ValueError("Airflow returned HTML instead of logs — auth issue.")
        return text