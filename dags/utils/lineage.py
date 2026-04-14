"""Utility to emit OpenLineage dataset events to Marquez.

Call emit_dataset_lineage() at the end of each task to register
input/output datasets. This populates the Datasets section in Marquez
so the full data flow is visible in the Lineage page.
"""
from __future__ import annotations

import datetime
import os
import uuid

MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://marquez-api:5000")
NAMESPACE = "bigdata-platform"
PRODUCER = "https://github.com/apache/airflow"
SCHEMA_URL = "https://openlineage.io/spec/1-0-5/OpenLineage.json#/definitions/RunEvent"


def _dataset(name: str) -> dict:
    return {"namespace": NAMESPACE, "name": name, "facets": {}}


def emit_dataset_lineage(
    job_name: str,
    inputs: list[str],
    outputs: list[str],
    run_id: str | None = None,
) -> None:
    """Emit an OpenLineage COMPLETE event with input/output datasets to Marquez.

    Args:
        job_name: Full job name e.g. "data_ingestion.ingest_csv_files"
        inputs:   Dataset names being read  e.g. ["landing/sales_data.csv"]
        outputs:  Dataset names being written e.g. ["raw/sales_data.csv"]
        run_id:   Optional UUID (auto-generated if omitted)
    """
    import requests  # imported here so Airflow worker doesn't fail if requests missing

    run_id = run_id or str(uuid.uuid4())
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    event = {
        "eventType": "COMPLETE",
        "eventTime": now,
        "run": {"runId": run_id, "facets": {}},
        "job": {
            "namespace": NAMESPACE,
            "name": job_name,
            "facets": {},
        },
        "inputs":  [_dataset(d) for d in inputs],
        "outputs": [_dataset(d) for d in outputs],
        "producer": PRODUCER,
        "schemaURL": SCHEMA_URL,
    }

    try:
        resp = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5,
        )
        resp.raise_for_status()
        print(f"[lineage] {job_name}: {len(inputs)} input(s) → {len(outputs)} output(s)")
    except Exception as e:
        # Non-fatal — never break the task because of lineage emission
        print(f"[lineage] WARNING: could not emit lineage for {job_name}: {e}")
