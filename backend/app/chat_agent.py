from __future__ import annotations

import os
from typing import Any

from .airflow_logs import fetch_airflow_task_logs
from .k8s_logs import fetch_k8s_pod_logs
from .llm_client import analyze_with_llm, llm_available
from .log_analyzer import analyze_logs
from .models import ChatRequest, ChatResponse
from .repo_context import search_repo_snippets


def _workspace_root() -> str:
    # Best-effort: repo root is two levels up from backend/app
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))


def chat(req: ChatRequest) -> ChatResponse:
    repo_root = req.repo_root or _workspace_root()

    sources: list[dict[str, str]] = []
    diagnostics: dict[str, Any] = {}

    repo_snips = []
    if req.include_repo_context:
        repo_snips = search_repo_snippets(root_dir=repo_root, query=req.question)
        sources.extend(
            {
                "type": "repo",
                "path": s.path,
                "snippet": s.snippet,
            }
            for s in repo_snips
        )
        diagnostics["repo_matches"] = len(repo_snips)

    # Optional tool contexts
    tool_notes: list[str] = []

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
                "Kubernetes pod log analysis:\n"
                f"- pod: {req.k8s.namespace}/{req.k8s.pod} (container={req.k8s.container})\n"
                f"- category: {analysis.category}\n"
                f"- signature: {analysis.error_signature}\n"
                f"- suspected_root_cause: {analysis.suspected_root_cause}\n"
                f"- next_actions: {analysis.next_actions}\n"
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
                "dag_run_id": req.airflow.dag_run_id,
                "task_id": req.airflow.task_id,
                "try_number": req.airflow.try_number,
                "analysis": analysis.model_dump(),
            }
            tool_notes.append(
                "Airflow task log analysis:\n"
                f"- dag_id: {req.airflow.dag_id}\n"
                f"- dag_run_id: {req.airflow.dag_run_id}\n"
                f"- task_id: {req.airflow.task_id} (try={req.airflow.try_number})\n"
                f"- category: {analysis.category}\n"
                f"- signature: {analysis.error_signature}\n"
                f"- suspected_root_cause: {analysis.suspected_root_cause}\n"
                f"- next_actions: {analysis.next_actions}\n"
            )
        except Exception as e:
            diagnostics["airflow_error"] = str(e)
            tool_notes.append(f"Airflow log fetch failed: {e}")

    # If LLM is disabled, return a helpful grounded response.
    use_llm = req.mode == "llm" or (req.mode == "auto" and llm_available())
    if not use_llm:
        parts: list[str] = []
        parts.append("LLM is not enabled (start Ollama or set OPENAI_API_KEY) — returning grounded context + tool summaries.")

        if tool_notes:
            parts.append("\n".join(tool_notes))

        if repo_snips:
            parts.append("Top repo matches:")
            for s in repo_snips:
                parts.append(f"- {s.path}\n{s.snippet}\n")
        else:
            parts.append("No repo matches found for the question.")

        return ChatResponse(answer="\n\n".join(parts), sources=sources, diagnostics=diagnostics)

    # Build LLM prompt
    context_blocks: list[str] = []
    if repo_snips:
        context_blocks.append("Project context from repo search:")
        for s in repo_snips:
            context_blocks.append(f"FILE: {s.path}\n{s.snippet}")

    if tool_notes:
        context_blocks.append("Runtime/Deployment tool outputs:")
        context_blocks.extend(tool_notes)

    history_text = "\n".join(
        f"{m.role.upper()}: {m.content}" for m in req.history[-10:]
    )

    prompt = (
        "You are a deployment observability chatbot for a data platform project (Airflow + Kubernetes).\n"
        "Answer the user's question concisely and practically.\n"
        "Rules:\n"
        "- If logs indicate an error, explain: what happened, why likely, and concrete next steps.\n"
        "- If the question is about the project, answer using the provided repo context snippets.\n"
        "- If info is missing, ask 1-2 targeted questions.\n"
        "- Avoid guessing. Prefer 'based on the context provided'.\n\n"
        f"Conversation so far:\n{history_text}\n\n"
        f"Context:\n{os.linesep.join(context_blocks) if context_blocks else '(no extra context)'}\n\n"
        f"User question: {req.question}\n\n"
        "Return STRICT JSON with keys: answer (string), followups (array of strings)."
    )

    raw = analyze_with_llm(prompt=prompt)
    answer = str(raw.get("answer", ""))
    followups = raw.get("followups", [])
    if isinstance(followups, list) and followups:
        answer = answer + "\n\nFollow-up questions:\n" + "\n".join(f"- {q}" for q in followups)

    return ChatResponse(answer=answer, sources=sources, diagnostics=diagnostics)
