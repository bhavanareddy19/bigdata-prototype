"""Marquez / OpenLineage client — query lineage data and ingest into VectorDB."""
from __future__ import annotations

import logging
from typing import Any

import requests

from .embedding_pipeline import index_lineage_event
from .settings import get_marquez_url

logger = logging.getLogger(__name__)


def _api(path: str) -> str:
    return f"{get_marquez_url().rstrip('/')}/api/v1{path}"


# ── Read operations ──────────────────────────────────────────


def list_namespaces() -> list[dict[str, Any]]:
    resp = requests.get(_api("/namespaces"), timeout=10)
    resp.raise_for_status()
    return resp.json().get("namespaces", [])


def list_jobs(namespace: str = "default") -> list[dict[str, Any]]:
    resp = requests.get(_api(f"/namespaces/{namespace}/jobs"), timeout=10)
    resp.raise_for_status()
    return resp.json().get("jobs", [])


def get_job(namespace: str, job_name: str) -> dict[str, Any]:
    resp = requests.get(_api(f"/namespaces/{namespace}/jobs/{job_name}"), timeout=10)
    resp.raise_for_status()
    return resp.json()


def list_datasets(namespace: str = "default") -> list[dict[str, Any]]:
    resp = requests.get(_api(f"/namespaces/{namespace}/datasets"), timeout=10)
    resp.raise_for_status()
    return resp.json().get("datasets", [])


def get_dataset(namespace: str, dataset_name: str) -> dict[str, Any]:
    resp = requests.get(_api(f"/namespaces/{namespace}/datasets/{dataset_name}"), timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_job_runs(namespace: str, job_name: str, limit: int = 10) -> list[dict[str, Any]]:
    resp = requests.get(_api(f"/namespaces/{namespace}/jobs/{job_name}/runs"), params={"limit": limit}, timeout=10)
    resp.raise_for_status()
    return resp.json().get("runs", [])


def get_lineage(node_type: str, namespace: str, node_name: str, depth: int = 5) -> dict[str, Any]:
    """Get lineage graph for a job or dataset node."""
    params = {
        "nodeId": f"{node_type}:{namespace}:{node_name}",
        "depth": depth,
    }
    resp = requests.get(_api("/lineage"), params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── Sync lineage into VectorDB ────────────────────────────────


def sync_lineage_to_vectordb(namespace: str = "default") -> int:
    """Fetch all jobs + runs from Marquez and index lineage events into ChromaDB."""
    count = 0
    try:
        jobs = list_jobs(namespace)
    except Exception as e:
        logger.warning("Cannot reach Marquez at %s: %s", get_marquez_url(), e)
        return 0

    for job in jobs:
        job_name = job.get("name", "")
        inputs = [inp.get("name", "") for inp in job.get("inputs", [])]
        outputs = [out.get("name", "") for out in job.get("outputs", [])]

        try:
            runs = get_job_runs(namespace, job_name, limit=5)
        except Exception:
            runs = []

        for run in runs:
            run_id = run.get("id", "")
            state = run.get("state", "UNKNOWN")
            index_lineage_event(
                run_id=run_id,
                job_name=job_name,
                event_type=state,
                inputs=inputs,
                outputs=outputs,
            )
            count += 1

    logger.info("Synced %d lineage events from Marquez (namespace=%s)", count, namespace)
    return count
