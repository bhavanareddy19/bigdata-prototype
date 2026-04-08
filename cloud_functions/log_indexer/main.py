import base64
import json
import os
import requests
import functions_framework

BACKEND_URL = os.environ.get(
    "BACKEND_URL",
    "https://bigdata-backend-770757350817.us-central1.run.app"
)

@functions_framework.cloud_event
def index_airflow_log(cloud_event):
    try:
        raw = cloud_event.data["message"].get("data", "")
        if not raw:
            return

        data = json.loads(base64.b64decode(raw).decode("utf-8"))

        log_text = (
            data.get("textPayload")
            or data.get("jsonPayload", {}).get("message", "")
            or ""
        ).strip()

        if not log_text:
            return

        # Composer uses "workflow" for dag_id and "task_id" for task_id
        labels   = data.get("labels", {})
        log_name = data.get("logName", "")
        severity = data.get("severity", "INFO")

        dag_id  = labels.get("workflow", "unknown")
        task_id = labels.get("task_id", "unknown")

        # Skip pure scheduler/system noise with no DAG context
        if dag_id == "unknown" and task_id == "unknown":
            if "airflow-scheduler" in log_name or "airflow-worker" not in log_name:
                return

        source   = f"composer/{dag_id}/{task_id}"
        enriched = (
            f"[Severity: {severity}] "
            f"[DAG: {dag_id}] "
            f"[Task: {task_id}]\n"
            f"{log_text}"
        )

        resp = requests.post(
            f"{BACKEND_URL}/index/log",
            json={"log_text": enriched, "source": source},
            timeout=30,
        )
        resp.raise_for_status()
        print(f"Indexed {source}: {log_text[:80]}")

    except Exception as e:
        print(f"Error: {e}")
        raise
