from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


AnalyzeMode = Literal["auto", "heuristic", "llm"]


class AnalyzeLogRequest(BaseModel):
    log_text: str = Field(..., description="Raw log text (can be multi-line).")
    source: str | None = Field(default=None, description="Where the logs came from (e.g., github_actions, k8s, airflow).")
    service: str | None = Field(default=None, description="Service/app name being deployed.")
    environment: str | None = Field(default=None, description="Environment name (dev/stage/prod).")
    mode: AnalyzeMode = Field(default="auto", description="auto prefers LLM if configured.")
    max_lines: int = Field(default=250, ge=50, le=5000)


class Evidence(BaseModel):
    important_lines: list[str] = Field(default_factory=list)
    traceback: list[str] = Field(default_factory=list)
    matched_patterns: list[str] = Field(default_factory=list)


class AnalyzeLogResponse(BaseModel):
    category: Literal["Infrastructure", "CodeLogic", "DataQuality", "Unknown"]
    error_signature: str
    summary: str
    suspected_root_cause: str
    next_actions: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Evidence
    raw: dict[str, Any] | None = None


class AnalyzeK8sPodRequest(BaseModel):
    namespace: str = Field(default="default")
    pod: str
    container: str | None = None
    tail_lines: int = Field(default=500, ge=10, le=5000)
    timestamps: bool = True
    mode: AnalyzeMode = Field(default="auto")
    max_lines: int = Field(default=250, ge=50, le=5000)
    source: str | None = Field(default="k8s")
    service: str | None = None
    environment: str | None = None


class AnalyzeAirflowTaskRequest(BaseModel):
    airflow_base_url: str | None = Field(
        default=None,
        description="If omitted, uses AIRFLOW_BASE_URL env var.",
    )
    dag_id: str
    dag_run_id: str
    task_id: str
    try_number: int = Field(default=1, ge=1, le=50)
    mode: AnalyzeMode = Field(default="auto")
    max_lines: int = Field(default=250, ge=50, le=5000)
    source: str | None = Field(default="airflow")
    service: str | None = None
    environment: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str
    history: list[ChatMessage] = Field(default_factory=list)

    # Optional extra context the chat can use as "tools"
    log_text: str | None = None
    k8s: AnalyzeK8sPodRequest | None = None
    airflow: AnalyzeAirflowTaskRequest | None = None

    # Grounding
    include_repo_context: bool = True
    repo_root: str | None = Field(
        default=None,
        description="Server-side path to search for project context. Defaults to workspace root.",
    )
    mode: AnalyzeMode = Field(default="auto")


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, str]] = Field(default_factory=list)
    diagnostics: dict[str, Any] | None = None


# ── Indexing / VectorDB ──────────────────────────────────────


class IndexCodebaseRequest(BaseModel):
    root_dir: str | None = Field(default=None, description="Server-side path to index. Defaults to workspace root.")
    reset: bool = Field(default=False, description="Drop existing code collection before re-indexing.")


class IndexStatsResponse(BaseModel):
    code_chunks: int = 0
    log_entries: int = 0
    dag_metadata: int = 0
    lineage_events: int = 0


# ── Lineage ──────────────────────────────────────────────────


class LineageRequest(BaseModel):
    node_type: str = Field(default="job", description="'job' or 'dataset'")
    namespace: str = Field(default="default")
    node_name: str
    depth: int = Field(default=5, ge=1, le=20)
