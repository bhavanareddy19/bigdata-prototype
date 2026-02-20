from __future__ import annotations

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .airflow_logs import fetch_airflow_task_logs
from .chat_agent import chat
from .k8s_logs import fetch_k8s_pod_logs
from .log_analyzer import analyze_logs
from .models import (
    AnalyzeAirflowTaskRequest,
    AnalyzeK8sPodRequest,
    AnalyzeLogRequest,
    AnalyzeLogResponse,
    ChatRequest,
    ChatResponse,
)


app = FastAPI(title="Deploy Log Observability Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest) -> ChatResponse:
    return chat(req)
