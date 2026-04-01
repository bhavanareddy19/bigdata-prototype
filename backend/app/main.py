from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .ops_sync import sync_airflow_ops, get_ops_summary
from .airflow_logs import fetch_airflow_task_logs
from .chat_agent import chat
from .embedding_pipeline import get_index_stats, index_codebase, index_log_entry
from .k8s_logs import fetch_k8s_pod_logs
from .lineage_client import (
    get_lineage,
    list_datasets,
    list_jobs,
    list_namespaces,
    sync_lineage_to_vectordb,
)
from .log_analyzer import analyze_logs
from .models import (
    AnalyzeAirflowTaskRequest,
    AnalyzeK8sPodRequest,
    AnalyzeLogRequest,
    AnalyzeLogResponse,
    ChatRequest,
    ChatResponse,
    IndexCodebaseRequest,
    IndexStatsResponse,
    LineageRequest,
)


def _workspace_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


app = FastAPI(title="BigData Platform — Observability Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Log analysis ─────────────────────────────────────────────


@app.post("/analyze-log", response_model=AnalyzeLogResponse)
def analyze_log(req: AnalyzeLogRequest) -> AnalyzeLogResponse:
    return analyze_logs(log_text=req.log_text, max_lines=req.max_lines, mode=req.mode)


@app.post("/analyze-k8s-pod", response_model=AnalyzeLogResponse)
def analyze_k8s_pod(req: AnalyzeK8sPodRequest) -> AnalyzeLogResponse:
    try:
        logs = fetch_k8s_pod_logs(
            namespace=req.namespace,
            pod=req.pod,
            container=req.container,
            tail_lines=req.tail_lines,
            timestamps=req.timestamps,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch k8s logs: {e}")
    return analyze_logs(log_text=logs, max_lines=req.max_lines, mode=req.mode)


@app.post("/analyze-airflow-task", response_model=AnalyzeLogResponse)
def analyze_airflow_task(req: AnalyzeAirflowTaskRequest) -> AnalyzeLogResponse:
    try:
        logs = fetch_airflow_task_logs(
            airflow_base_url=req.airflow_base_url,
            dag_id=req.dag_id,
            dag_run_id=req.dag_run_id,
            task_id=req.task_id,
            try_number=req.try_number,
            full_content=False,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch Airflow task logs: {e}")
    return analyze_logs(log_text=logs, max_lines=req.max_lines, mode=req.mode)


# ── Chat (RAG-powered) ──────────────────────────────────────


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    return chat(req)


# ── Indexing (VectorDB) ─────────────────────────────────────


@app.post("/index/codebase")
def index_codebase_endpoint(req: IndexCodebaseRequest | None = None):
    root = (req.root_dir if req and req.root_dir else None) or _workspace_root()
    reset = req.reset if req else False
    count = index_codebase(root, reset=reset)
    return {"indexed_chunks": count, "root": root}


@app.post("/index/log")
def index_log_endpoint(req: AnalyzeLogRequest):
    doc_id = index_log_entry(req.log_text, source=req.source or "manual")
    return {"doc_id": doc_id}


@app.get("/index/stats", response_model=IndexStatsResponse)
def index_stats_endpoint():
    return IndexStatsResponse(**get_index_stats())


# ── Lineage (Marquez) ───────────────────────────────────────


@app.get("/lineage/namespaces")
def lineage_namespaces():
    try:
        return {"namespaces": list_namespaces()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marquez unreachable: {e}")


@app.get("/lineage/jobs/{namespace}")
def lineage_jobs(namespace: str = "default"):
    try:
        return {"jobs": list_jobs(namespace)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marquez unreachable: {e}")


@app.get("/lineage/datasets/{namespace}")
def lineage_datasets(namespace: str = "default"):
    try:
        return {"datasets": list_datasets(namespace)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marquez unreachable: {e}")


@app.post("/lineage/graph")
def lineage_graph(req: LineageRequest):
    try:
        return get_lineage(req.node_type, req.namespace, req.node_name, depth=req.depth)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marquez unreachable: {e}")


@app.post("/lineage/sync")
def lineage_sync(namespace: str = "bigdata-platform"):
    count = sync_lineage_to_vectordb(namespace)
    return {"synced_events": count}

@app.post("/ops/sync-airflow")
def ops_sync_airflow():
    return sync_airflow_ops()


@app.get("/ops/summary")
def ops_summary():
    return get_ops_summary()


@app.get("/ops/latest-failures")
def ops_latest_failures():
    data = get_ops_summary()
    return {"recent_failures": data.get("recent_failures", [])}


@app.get("/ops/dag-status/{dag_id}")
def ops_dag_status(dag_id: str):
    data = get_ops_summary()
    for dag in data.get("dags", []):
        if dag.get("dag_id") == dag_id:
            return dag
    raise HTTPException(status_code=404, detail=f"No cached status for dag_id={dag_id}")