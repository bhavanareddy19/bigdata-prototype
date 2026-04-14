from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .ops_sync import sync_airflow_ops, get_ops_summary
from .airflow_logs import fetch_airflow_task_logs
from .airflow_status_client import list_dags, list_dag_runs, trigger_dag, unpause_dag
from .chat_agent import chat
from .embedding_pipeline import get_index_stats, index_codebase, index_log_entry
from .k8s_logs import (
    describe_pod as k8s_describe_pod,
    diagnose_namespace as k8s_diagnose_namespace,
    fetch_k8s_pod_logs,
    list_events as k8s_list_events,
    list_namespaces as k8s_list_namespaces,
    list_pods as k8s_list_pods,
)
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


SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))  # 5 min default


async def _background_sync():
    """Periodically auto-sync Airflow ops + Marquez lineage into ChromaDB."""
    # Initial delay so startup indexing finishes first
    await asyncio.sleep(30)
    while True:
        try:
            sync_airflow_ops()
            print("[bg-sync] Airflow ops snapshot refreshed")
        except Exception as e:
            print(f"[bg-sync] ops sync failed (non-fatal): {e}")
        try:
            n = sync_lineage_to_vectordb("bigdata-platform")
            if n:
                print(f"[bg-sync] synced {n} lineage events from Marquez")
        except Exception as e:
            print(f"[bg-sync] lineage sync failed (non-fatal): {e}")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-index codebase on every startup so RAG is always ready
    try:
        root = _workspace_root()
        count = index_codebase(root, reset=False)
        print(f"[startup] auto-indexed {count} chunks from {root}")
    except Exception as e:
        print(f"[startup] indexing failed (non-fatal): {e}")
    # Auto-sync Airflow ops snapshot on startup
    try:
        sync_airflow_ops()
        print("[startup] ops snapshot synced from Airflow")
    except Exception as e:
        print(f"[startup] ops sync failed (non-fatal): {e}")
    # Auto-trigger demo DAGs on first deployment (if they've never run)
    _DEMO_DAGS = ["demo_pipeline_dag", "demo_observability_dag"]
    for dag_id in _DEMO_DAGS:
        try:
            runs = list_dag_runs(dag_id, limit=1)
            if not runs:
                unpause_dag(dag_id)
                trigger_dag(dag_id)
                print(f"[startup] triggered {dag_id} (no prior runs found)")
            else:
                print(f"[startup] {dag_id} already has runs, skipping auto-trigger")
        except Exception as e:
            print(f"[startup] could not auto-trigger {dag_id} (non-fatal): {e}")
    # Start background sync loop (Airflow ops + Marquez lineage every 5 min)
    task = asyncio.create_task(_background_sync())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="BigData Platform — Observability Agent",
    version="1.0.0",
    lifespan=lifespan,
)

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
    result = analyze_logs(log_text=req.log_text, max_lines=req.max_lines, mode=req.mode)
    try:
        index_log_entry(req.log_text, source=req.source or "manual", metadata={"category": result.category})
    except Exception:
        pass
    return result


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
    result = analyze_logs(log_text=logs, max_lines=req.max_lines, mode=req.mode)
    try:
        index_log_entry(logs, source=f"k8s/{req.namespace}/{req.pod}", metadata={"category": result.category, "namespace": req.namespace, "pod": req.pod})
    except Exception:
        pass
    return result


@app.get("/k8s/namespaces")
def k8s_namespaces():
    try:
        return {"namespaces": k8s_list_namespaces()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kubernetes API unreachable. Enable Docker Desktop Kubernetes or deploy to GKE. Error: {e}")


@app.get("/k8s/pods/{namespace}")
def k8s_pods(namespace: str):
    try:
        return {"pods": k8s_list_pods(namespace)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kubernetes API unreachable. Enable Docker Desktop Kubernetes or deploy to GKE. Error: {e}")


@app.get("/k8s/events/{namespace}")
def k8s_events(namespace: str, limit: int = 50):
    try:
        return {"events": k8s_list_events(namespace, limit=limit)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kubernetes API unreachable. Enable Docker Desktop Kubernetes or deploy to GKE. Error: {e}")


@app.get("/k8s/diagnose/{namespace}")
def k8s_diagnose(namespace: str):
    try:
        return k8s_diagnose_namespace(namespace)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kubernetes API unreachable. Enable Docker Desktop Kubernetes or deploy to GKE. Error: {e}")


@app.get("/k8s/describe/{namespace}/{pod}")
def k8s_describe(namespace: str, pod: str):
    try:
        return k8s_describe_pod(namespace, pod)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Kubernetes API unreachable. Enable Docker Desktop Kubernetes or deploy to GKE. Error: {e}")


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
    result = analyze_logs(log_text=logs, max_lines=req.max_lines, mode=req.mode)
    try:
        index_log_entry(logs, source=f"airflow/{req.dag_id}/{req.task_id}", metadata={"category": result.category, "dag_id": req.dag_id, "task_id": req.task_id})
    except Exception:
        pass
    return result


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
    marquez_url = os.getenv("MARQUEZ_URL", "")
    if not marquez_url:
        raise HTTPException(status_code=503, detail="MARQUEZ_URL not configured")
    # Quick reachability check
    try:
        import requests as _req
        _req.get(f"{marquez_url.rstrip('/')}/api/v1/namespaces", timeout=5).raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Marquez unreachable at {marquez_url}: {e}")
    count = sync_lineage_to_vectordb(namespace)
    return {"synced_events": count, "namespace": namespace, "marquez_url": marquez_url}


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


@app.get("/ops/list-dags")
def ops_list_dags():
    return {"dags": list_dags(100)}
