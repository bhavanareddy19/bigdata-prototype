from __future__ import annotations

import json
from typing import Any

from google.cloud import storage

from .settings import get_gcs_data_bucket

OPS_BLOB = "ops/latest_status.json"


def _client() -> storage.Client:
    return storage.Client()


def load_ops_snapshot() -> dict[str, Any]:
    bucket_name = get_gcs_data_bucket()
    if not bucket_name:
        return {"generated_at": None, "dags": [], "recent_failures": []}

    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(OPS_BLOB)

    if not blob.exists():
        return {"generated_at": None, "dags": [], "recent_failures": []}

    return json.loads(blob.download_as_text())


def save_ops_snapshot(snapshot: dict[str, Any]) -> None:
    bucket_name = get_gcs_data_bucket()
    if not bucket_name:
        raise ValueError("GCS_DATA_BUCKET is not configured")

    client = _client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(OPS_BLOB)
    blob.upload_from_string(
        json.dumps(snapshot, indent=2),
        content_type="application/json",
    )