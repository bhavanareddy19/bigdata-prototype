from __future__ import annotations

import os
from typing import Any
from .ops_store import load_ops_snapshot
from .airflow_logs import fetch_airflow_task_logs
from .k8s_logs import (
    diagnose_namespace as k8s_diagnose_namespace,
    fetch_k8s_pod_logs,
    format_diagnosis_for_llm,
    list_namespaces as k8s_list_namespaces,
)
from .llm_client import llm_available
from .log_analyzer import analyze_logs
from .models import ChatRequest, ChatResponse
from .rag_engine import rag_query
from .repo_context import search_repo_snippets

def _workspace_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))

def _looks_like_k8s_question(question: str) -> tuple[bool, str | None]:
    q = question.lower()
    triggers = [
        # failure modes
        "crashloop", "crash loop", "imagepull", "image pull", "oomkill", "oom kill",
        "oomkilled", "evicted", "pending pod", "pod stuck", "pod crash", "pod failing",
        # general k8s terms
        "kubernetes", "k8s", "kubectl",
        "pod", "pods", "container", "containers",
        "namespace", "namespaces",
        "deployment", "deployments", "replica", "node",
        "cluster", "ingress", "service mesh",
        # health / status questions
        "pod health", "pod status", "all pods", "pods healthy", "pods running",
        "pods up", "pods down", "pods failing",
        "running in", "deployed", "what's running", "whats running",
    ]
    hit = any(t in q for t in triggers)
    if not hit:
        return False, None
    # Try to infer a namespace from the question
    for ns_hint in ("backend", "airflow", "data", "kube-system", "default", "monitoring"):
        if ns_hint in q:
            return True, ns_hint
    return True, None


def _looks_like_ops_question(question: str) -> bool:
    q = question.lower()
    keywords = [
        "status", "failed", "failure", "error", "errors", "problem", "problems",
        "broken", "issue", "issues", "recent", "today", "running", "health",
        "pipeline", "dag", "dags", "task", "tasks", "ingestion", "transformation",
        "quality", "ml_pipeline", "what happened", "whats wrong", "what's wrong",
    ]
    return any(k in q for k in keywords)


def _format_ops_snapshot_for_user(snapshot: dict) -> str:
    dags = snapshot.get("dags", [])
    if not dags:
        return "No live pipeline status available yet — Airflow sync has not run."

    lines = ["=== LIVE PIPELINE STATUS (from Airflow) ==="]
    failed_dags = []
    healthy_dags = []

    for dag in dags:
        dag_id = dag.get("dag_id", "unknown")
        state = dag.get("latest_state", "UNKNOWN")
        tasks = dag.get("tasks", [])
        failed_tasks = [t for t in tasks if t.get("state") == "failed"]
        success_tasks = [t for t in tasks if t.get("state") == "success"]

        if state in ("failed", "error") or failed_tasks:
            failed_dags.append((dag_id, state, failed_tasks, tasks))
        else:
            healthy_dags.append((dag_id, state))

    if failed_dags:
        lines.append("\n--- FAILING DAGS ---")
        for dag_id, state, failed_tasks, all_tasks in failed_dags:
            lines.append(f"\n[FAILED] {dag_id} — overall state: {state}")
            for t in all_tasks:
                task_state = t.get("state", "unknown")
                tid = t.get("task_id", "?")
                tries = t.get("try_number", 1)
                marker = "✗" if task_state == "failed" else "✓"
                lines.append(f"  {marker} {tid}: {task_state} (tried {tries}x)")

    if healthy_dags:
        lines.append("\n--- HEALTHY DAGS ---")
        for dag_id, state in healthy_dags:
            lines.append(f"  ✓ {dag_id}: {state}")

    recent_failures = snapshot.get("recent_failures", [])
    if recent_failures:
        lines.append("\n--- RECENT FAILURES (last 5) ---")
        for f in recent_failures[:5]:
            summary = f.get("summary", {})
            root_cause = summary.get("root_cause") or "see task logs"
            next_actions = summary.get("next_actions") or []
            lines.append(f"  • {f.get('dag_id')} / {f.get('task_id')}: {root_cause}")
            for action in next_actions[:2]:
                lines.append(f"    → {action}")

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

    if req.k8s_diagnose is not None:
        try:
            diag = k8s_diagnose_namespace(req.k8s_diagnose.namespace)
            diagnostics["k8s_diagnose"] = diag
            tool_notes.append(format_diagnosis_for_llm(diag))
        except Exception as e:
            diagnostics["k8s_diagnose_error"] = str(e)
            tool_notes.append(f"Kubernetes diagnose failed: {e}")
    else:
        is_k8s, ns_hint = _looks_like_k8s_question(req.question)
        if is_k8s:
            try:
                _SKIP_NS = {"kube-system", "kube-public", "kube-node-lease", "gke-managed-system",
                            "gke-managed-cim", "gke-managed-filestorecsi", "local-path-storage"}
                # Prioritise app namespaces, then fill with others up to 6 total
                if ns_hint:
                    candidates = [ns_hint]
                else:
                    all_ns = k8s_list_namespaces()
                    app_ns = [n for n in all_ns if n in {"backend", "airflow", "data", "default", "monitoring"}]
                    rest = [n for n in all_ns if n not in _SKIP_NS and n not in app_ns]
                    candidates = (app_ns + rest)[:6]

                all_diag: list[dict[str, Any]] = []
                for ns in candidates:
                    d = k8s_diagnose_namespace(ns)
                    all_diag.append(d)

                problem_diags = [d for d in all_diag if not d["healthy"]]
                healthy_diags = [d for d in all_diag if d["healthy"]]

                lines = ["=== LIVE KUBERNETES STATUS ==="]
                if problem_diags:
                    for d in problem_diags:
                        lines.append(format_diagnosis_for_llm(d))
                if healthy_diags:
                    lines.append("\nHealthy namespaces:")
                    for d in healthy_diags:
                        lines.append(f"  ✓ {d['namespace']}: {d['pod_count']} pod(s), all running")

                diagnostics["k8s_auto_diagnose"] = {
                    "scanned": len(all_diag),
                    "problems": len(problem_diags),
                }
                tool_notes.append("\n".join(lines))
            except Exception as e:
                err_str = str(e)
                diagnostics["k8s_auto_diagnose_error"] = err_str
                tool_notes.append(
                    "Kubernetes cluster is not reachable from this environment. "
                    "For live pod/namespace diagnostics, use the Kubernetes tab directly. "
                    "I can still answer general Kubernetes questions based on my training."
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
        except Exception as e:
            err_str = str(e)
            if "rate-limited" in err_str.lower() or "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                return ChatResponse(
                    answer="The AI model is temporarily rate-limited. Please wait a minute and try again.",
                    sources=[],
                    diagnostics={"error": "rate_limited"}
                )
            # Return error as a chat message rather than crashing the endpoint
            return ChatResponse(
                answer=f"Sorry, I encountered an error while generating a response: {err_str}",
                sources=[],
                diagnostics={"error": err_str},
            )

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
