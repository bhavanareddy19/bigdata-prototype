from __future__ import annotations

import os
from typing import Any
from .ops_store import load_ops_snapshot
from .airflow_logs import fetch_airflow_task_logs
from .k8s_logs import fetch_k8s_pod_logs
from .llm_client import llm_available
from .log_analyzer import analyze_logs
from .models import ChatRequest, ChatResponse
from .rag_engine import rag_query
from .repo_context import search_repo_snippets

def _workspace_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))

def _looks_like_ops_question(question: str) -> bool:
    q = question.lower()
    keywords = [
        "status", "failed", "failure", "recent", "today", "running",
        "pipeline health", "dag", "task", "ingestion", "transformation",
        "quality", "ml_pipeline"
    ]
    return any(k in q for k in keywords)

def _format_ops_snapshot_for_user(snapshot: dict) -> str:
    dags = snapshot.get("dags", [])
    if not dags:
        return "No cached pipeline status is available yet."
    lines = ["Pipeline status summary:"]
    for dag in dags:
        dag_id = dag.get("dag_id", "unknown")
        state = dag.get("latest_state", "UNKNOWN")
        if dag_id == "data_ingestion":
            if state == "SUCCESS_FROM_GCS":
                file_count = dag.get("raw_file_count", 0)
                sample_files = dag.get("sample_files", [])[:3]
                short_names = [os.path.basename(f) for f in sample_files]
                lines.append(f"- data_ingestion appears successful: {file_count} file(s) in raw/.")
                if short_names:
                    lines.append(f"  Sample files: {', '.join(short_names)}")
            elif state == "NO_RAW_OUTPUT":
                lines.append("- data_ingestion has no raw output yet.")
            elif state == "NO_RUNS":
                lines.append("- data_ingestion has not run yet.")
            else:
                lines.append(f"- data_ingestion status is currently {state}.")
        else:
            tasks = dag.get("tasks", [])
            failed_tasks = [t["task_id"] for t in tasks if t.get("state") == "failed"]
            if failed_tasks:
                lines.append(f"- {dag_id}: {state} (failed tasks: {', '.join(failed_tasks)})")
            else:
                lines.append(f"- {dag_id}: {state}")
    recent_failures = snapshot.get("recent_failures", [])
    if recent_failures:
        lines.append("")
        lines.append("Recent failures:")
        for f in recent_failures[:5]:
            summary = f.get("summary", {})
            root_cause = summary.get("root_cause") or f.get("state", "failed")
            lines.append(f"- {f.get('dag_id')} / {f.get('task_id')}: {root_cause}")
    return "\n".join(lines)


def chat(req: ChatRequest) -> ChatResponse:
    repo_root = req.repo_root or _workspace_root()
    sources: list[dict[str, str]] = []
    diagnostics: dict[str, Any] = {}
    tool_notes: list[str] = []

    if _looks_like_ops_question(req.question):
        snapshot = load_ops_snapshot()
        if snapshot.get("dags"):
            tool_notes.append(_format_ops_snapshot_for_user(snapshot))
            diagnostics["ops_snapshot_loaded"] = True

    if req.log_text and req.log_text.strip():
        analysis = analyze_logs(log_text=req.log_text, max_lines=400, mode=req.mode)
        diagnostics["log_analysis"] = analysis.model_dump()
        tool_notes.append(
            "Log analysis result:\n"
            f"- category: {analysis.category}\n"
            f"- signature: {analysis.error_signature}\n"
            f"- suspected_root_cause: {analysis.suspected_root_cause}\n"
            f"- next_actions: {analysis.next_actions}\n"
        )

    if req.k8s is not None:
        try:
            logs = fetch_k8s_pod_logs(
                namespace=req.k8s.namespace,
                pod=req.k8s.pod,
                container=req.k8s.container,
                tail_lines=req.k8s.tail_lines,
                timestamps=req.k8s.timestamps,
            )
            analysis = analyze_logs(log_text=logs, max_lines=req.k8s.max_lines, mode=req.mode)
            diagnostics["k8s"] = {
                "namespace": req.k8s.namespace,
                "pod": req.k8s.pod,
                "analysis": analysis.model_dump(),
            }
            tool_notes.append(
                f"Kubernetes pod log analysis ({req.k8s.namespace}/{req.k8s.pod}):\n"
                f"- category: {analysis.category}\n"
                f"- signature: {analysis.error_signature}\n"
                f"- suspected_root_cause: {analysis.suspected_root_cause}\n"
            )
        except Exception as e:
            diagnostics["k8s_error"] = str(e)
            tool_notes.append(f"Kubernetes log fetch failed: {e}")

    if req.airflow is not None:
        try:
            logs = fetch_airflow_task_logs(
                airflow_base_url=req.airflow.airflow_base_url,
                dag_id=req.airflow.dag_id,
                dag_run_id=req.airflow.dag_run_id,
                task_id=req.airflow.task_id,
                try_number=req.airflow.try_number,
                full_content=False,
            )
            analysis = analyze_logs(log_text=logs, max_lines=req.airflow.max_lines, mode=req.mode)
            diagnostics["airflow"] = {
                "dag_id": req.airflow.dag_id,
                "task_id": req.airflow.task_id,
                "analysis": analysis.model_dump(),
            }
            tool_notes.append(
                f"Airflow task log analysis (dag={req.airflow.dag_id}, task={req.airflow.task_id}):\n"
                f"- category: {analysis.category}\n"
                f"- signature: {analysis.error_signature}\n"
                f"- suspected_root_cause: {analysis.suspected_root_cause}\n"
            )
        except Exception as e:
            diagnostics["airflow_error"] = str(e)
            tool_notes.append(f"Airflow log fetch failed: {e}")

    extra_context = "\n".join(tool_notes) if tool_notes else ""

    use_llm = req.mode in ("llm", "auto")
    if use_llm:
        history = [{"role": m.role, "content": m.content} for m in req.history[-10:]]
        try:
            result = rag_query(
                question=req.question,
                history=history,
                extra_context=extra_context,
            )
            for chunk in result.retrieved_chunks[:8]:
                sources.append({
                    "type": chunk.collection,
                    "path": chunk.metadata.get("file", chunk.metadata.get("dag_id", "")),
                    "snippet": chunk.document[:500],
                    "relevance": f"{1 - chunk.distance:.2f}",
                })
            diagnostics["rag_chunks"] = len(result.retrieved_chunks)
            diagnostics["prompt_tokens_approx"] = result.prompt_tokens_approx
            return ChatResponse(answer=result.answer, sources=sources, diagnostics=diagnostics)
        except RuntimeError as e:
            if "rate-limited" in str(e).lower():
                return ChatResponse(
                    answer="The AI model is temporarily rate-limited. Please wait a minute and try again.",
                    sources=[],
                    diagnostics={"error": "rate_limited"}
                )
            raise

    repo_snips = search_repo_snippets(root_dir=repo_root, query=req.question) if req.include_repo_context else []
    sources.extend({"type": "repo", "path": s.path, "snippet": s.snippet} for s in repo_snips)
    diagnostics["repo_matches"] = len(repo_snips)

    parts: list[str] = ["LLM generation is currently unavailable — returning grounded context + tool summaries."]
    if tool_notes:
        parts.append("\n".join(tool_notes))
    if repo_snips:
        parts.append("Top repo matches:")
        for s in repo_snips:
            parts.append(f"- {s.path}\n{s.snippet}\n")
    else:
        parts.append("No repo matches found.")

    return ChatResponse(answer="\n\n".join(parts), sources=sources, diagnostics=diagnostics)
