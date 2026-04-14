from __future__ import annotations

import json
import os
from typing import Any

from .settings import get_gcs_data_bucket

OPS_BLOB = "ops/latest_status.json"
# Use the ChromaDB PVC directory so data survives pod restarts
_CHROMADB_DIR = os.getenv("CHROMADB_PERSIST_DIR", "/tmp")
_LOCAL_SNAPSHOT = os.path.join(_CHROMADB_DIR, "ops_latest_status.json")
_EMPTY: dict[str, Any] = {"generated_at": None, "dags": [], "recent_failures": []}


def load_ops_snapshot() -> dict[str, Any]:
    bucket_name = get_gcs_data_bucket()

    if bucket_name:
        try:
            from google.cloud import storage  # type: ignore
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(OPS_BLOB)
            if blob.exists():
                return json.loads(blob.download_as_text())
        except Exception:
            pass  # fall through to local file

    # Local dev fallback
    if os.path.exists(_LOCAL_SNAPSHOT):
        try:
            with open(_LOCAL_SNAPSHOT) as f:
                return json.load(f)
        except Exception:
            pass

    return dict(_EMPTY)


def save_ops_snapshot(snapshot: dict[str, Any]) -> None:
    bucket_name = get_gcs_data_bucket()

    if bucket_name:
        try:
            from google.cloud import storage  # type: ignore
            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(OPS_BLOB)
            blob.upload_from_string(
                json.dumps(snapshot, indent=2),
                content_type="application/json",
            )
            return
        except Exception:
            pass  # fall through to local file

    # Local dev fallback — write to /tmp
    os.makedirs(os.path.dirname(_LOCAL_SNAPSHOT), exist_ok=True)
    with open(_LOCAL_SNAPSHOT, "w") as f:
        json.dump(snapshot, f, indent=2)
