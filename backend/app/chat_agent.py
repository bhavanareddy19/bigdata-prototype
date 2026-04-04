"""Chat agent — uses the RAG engine (ChromaDB + Ollama) for answers.

Falls back to grounded repo snippets + tool summaries when the LLM is down.
"""
from __future__ import annotations

import os
from typing import Any
from .ops_store import load_ops_snapshot, save_ops_snapshot
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
        "quality", "ml_pipeline", "problem", "error", "issue", "broken",
        "what happened", "which dag", "which pipeline", "down",
    ]
    return any(k in q for k in keywords)


def _fetch_live_airflow_status() -> dict[str, Any] | None:
    """Fetch live status from Airflow API — no cache, real-time."""
    try:
        from .ops_sync import build_ops_snapshot
        snapshot = build_ops_snapshot()
        # Also save it so future requests can use cache if Airflow is down
        save_ops_snapshot(snapshot)
        return snapshot
    except Exception:
        return None


def _format_airflow_status(snapshot: dict[str, Any]) -> str:
    """Format Airflow status into readable text for the LLM."""
    lines = []
    dags = snapshot.get("dags", [])
    failures = snapshot.get("recent_failures", [])

    if not dags:
        return "No Airflow DAG status available."

    lines.append("=== Live Airflow Pipeline Status ===")
    for d in dags:
        dag_id = d.get("dag_id", "?")
        state = d.get("latest_state", "?")
        icon = "PASS" if state == "success" else "FAIL" if state == "failed" else state.upper()
        lines.append(f"  [{icon}] {dag_id} (run: {d.get('dag_run_id', 'n/a')})")

        for t in d.get("tasks", []):
            t_state = t.get("state", "?")
            t_icon = "ok" if t_state == "success" else "FAILED" if t_state == "failed" else t_state
            lines.append(f"        task: {t.get('task_id'):30s} -> {t_icon}")

    if failures:
        lines.append("\n=== Recent Failures (auto-analyzed) ===")
        for f in failures[:5]:
            summary = f.get("summary", {})
            lines.append(
                f"  DAG: {f.get('dag_id')} / Task: {f.get('task_id')}\n"
                f"    Root cause: {summary.get('root_cause', 'unknown')}\n"
                f"    Category: {summary.get('category', '?')}\n"
                f"    Fix: {', '.join(summary.get('next_actions', ['check logs']))}"
            )

    return "\n".join(lines)


def chat(req: ChatRequest) -> ChatResponse:
    repo_root = req.repo_root or _workspace_root()

    sources: list[dict[str, str]] = []
    diagnostics: dict[str, Any] = {}

    # ── Optional tool contexts ───────────────────────────────
    tool_notes: list[str] = []

    # Auto-fetch live Airflow status for ops questions
    if _looks_like_ops_question(req.question):
        # Try live fetch first, fall back to cached snapshot
        snapshot = _fetch_live_airflow_status()
        if not snapshot or not snapshot.get("dags"):
            snapshot = load_ops_snapshot()

        if snapshot and snapshot.get("dags"):
            status_text = _format_airflow_status(snapshot)
            tool_notes.append(status_text)
            diagnostics["airflow_live_status"] = True
            diagnostics["dags_checked"] = len(snapshot.get("dags", []))
            diagnostics["failures_found"] = len(snapshot.get("recent_failures", []))

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
                "container": req.k8s.container,
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

    # ── RAG path (preferred) ─────────────────────────────────
    use_llm = req.mode == "llm" or (req.mode == "auto" and llm_available())
    if use_llm:
        history = [{"role": m.role, "content": m.content} for m in req.history[-10:]]
        result = rag_query(
            question=req.question,
            history=history,
            extra_context=extra_context,
        )

        # Build sources from retrieved chunks
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

    # ── Fallback: no LLM — return grounded context ───────────
    repo_snips = search_repo_snippets(root_dir=repo_root, query=req.question) if req.include_repo_context else []
    sources.extend({"type": "repo", "path": s.path, "snippet": s.snippet} for s in repo_snips)
    diagnostics["repo_matches"] = len(repo_snips)

    parts: list[str] = []
    parts.append("Ollama is not running — returning grounded context + tool summaries.")
    parts.append("Start Ollama (`ollama serve`) and pull a model (`ollama pull llama3.2:1b`) for RAG answers.\n")
    if tool_notes:
        parts.append("\n".join(tool_notes))
    if repo_snips:
        parts.append("Top repo matches:")
        for s in repo_snips:
            parts.append(f"- {s.path}\n{s.snippet}\n")
    else:
        parts.append("No repo matches found.")

    return ChatResponse(answer="\n\n".join(parts), sources=sources, diagnostics=diagnostics)
