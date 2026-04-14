from __future__ import annotations

from typing import Optional, Any
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


_k8s_config_loaded: bool | None = None


def _load_k8s_config() -> bool:
    global _k8s_config_loaded
    if _k8s_config_loaded is True:
        return True
    from kubernetes import config  # type: ignore
    try:
        config.load_incluster_config()
        _k8s_config_loaded = True
        return True
    except Exception:
        try:
            config.load_kube_config()
            _k8s_config_loaded = True
            return True
        except Exception:
            # Do NOT cache failure — kubeconfig may appear later (e.g. patched at startup)
            return False


def _core_api():
    from kubernetes import client  # type: ignore
    _load_k8s_config()
    return client.CoreV1Api()


def _apps_api():
    from kubernetes import client  # type: ignore
    _load_k8s_config()
    return client.AppsV1Api()


def fetch_k8s_pod_logs(
    *,
    namespace: str,
    pod: str,
    container: Optional[str],
    tail_lines: int,
    timestamps: bool,
) -> str:
    v1 = _core_api()
    return v1.read_namespaced_pod_log(
        name=pod,
        namespace=namespace,
        container=container,
        tail_lines=tail_lines,
        timestamps=timestamps,
        _preload_content=True,
    )


def list_namespaces() -> list[str]:
    v1 = _core_api()
    return sorted(ns.metadata.name for ns in v1.list_namespace().items)


def list_pods(namespace: str) -> list[dict[str, Any]]:
    v1 = _core_api()
    pods = v1.list_namespaced_pod(namespace).items
    out: list[dict[str, Any]] = []
    for p in pods:
        phase = p.status.phase or "Unknown"
        restarts = 0
        waiting_reason = None
        last_terminated = None
        containers = []
        for cs in p.status.container_statuses or []:
            restarts += cs.restart_count or 0
            containers.append(cs.name)
            if cs.state and cs.state.waiting and cs.state.waiting.reason:
                waiting_reason = cs.state.waiting.reason
            if cs.last_state and cs.last_state.terminated:
                t = cs.last_state.terminated
                last_terminated = {
                    "reason": t.reason,
                    "exit_code": t.exit_code,
                    "message": (t.message or "")[:500],
                }
        ready = sum(1 for cs in p.status.container_statuses or [] if cs.ready)
        total = len(p.status.container_statuses or [])
        out.append({
            "name": p.metadata.name,
            "namespace": p.metadata.namespace,
            "phase": phase,
            "ready": f"{ready}/{total}",
            "restarts": restarts,
            "node": p.spec.node_name or "",
            "containers": containers,
            "waiting_reason": waiting_reason,
            "last_terminated": last_terminated,
            "age_seconds": _age_seconds(p.metadata.creation_timestamp),
        })
    return out


def _age_seconds(ts) -> int:
    if not ts:
        return 0
    from datetime import datetime, timezone
    return int((datetime.now(timezone.utc) - ts).total_seconds())


def list_events(namespace: str, limit: int = 50) -> list[dict[str, Any]]:
    v1 = _core_api()
    events = v1.list_namespaced_event(namespace).items
    events.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp, reverse=True)
    return [
        {
            "type": e.type,
            "reason": e.reason,
            "object": f"{e.involved_object.kind}/{e.involved_object.name}",
            "message": (e.message or "")[:500],
            "count": e.count or 1,
        }
        for e in events[:limit]
    ]


_TROUBLESHOOT_HINTS: dict[str, str] = {
    "CrashLoopBackOff": "Container is crashing repeatedly. Inspect the pod logs for the latest stack trace and last_terminated exit_code. Common fixes: fix the startup command, missing env var, failed DB connection, or bad config file.",
    "ImagePullBackOff": "Cluster can't pull the image. Check image name/tag exists in the registry, that the node has pull permissions (Artifact Registry IAM, imagePullSecrets), and that the tag is correct.",
    "ErrImagePull": "Cluster can't pull the image. Check image name/tag exists in the registry, that the node has pull permissions, and that you pushed the image before applying the manifest.",
    "OOMKilled": "Container exceeded its memory limit. Increase resources.limits.memory, find the memory leak, or reduce workload. Check container.last_terminated.reason.",
    "CreateContainerConfigError": "Container config is invalid — often a missing ConfigMap/Secret referenced by envFrom or volumeMounts. Check the referenced names exist in the same namespace.",
    "CreateContainerError": "Container failed to be created — often a broken command, missing volume, or invalid mountPath.",
    "Evicted": "Pod was evicted due to node pressure (memory/disk). Check node conditions, add more nodes, or lower resource requests.",
    "Pending": "Pod can't be scheduled. Common causes: insufficient cluster CPU/memory, unbound PVC, node selector/taint mismatch, or unschedulable constraints. Check `kubectl describe pod` events.",
    "FailedScheduling": "Scheduler can't place the pod. Usually means the cluster doesn't have enough CPU/memory, or a PVC is waiting for a volume. Scale the nodepool or reduce requests.",
    "FailedMount": "Pod can't mount a volume. The PVC may be unbound, the Secret/ConfigMap may be missing, or a hostPath may not exist on the node.",
    "Unhealthy": "Readiness/liveness probe failing. Check the probe path/port and whether the app actually responds there.",
    "BackOff": "Kubelet is backing off restarting the container. Usually paired with CrashLoopBackOff — check logs and last_terminated.",
}


def diagnose_namespace(namespace: str) -> dict[str, Any]:
    """High-level K8s diagnosis for a namespace.

    Returns pods with problems, recent warning events, and suggested next actions
    per detected failure mode. Safe to feed into an LLM prompt for remediation.
    """
    pods = list_pods(namespace)
    events = list_events(namespace, limit=50)

    problems: list[dict[str, Any]] = []
    detected_reasons: set[str] = set()

    for p in pods:
        reasons: list[str] = []
        if p["waiting_reason"]:
            reasons.append(p["waiting_reason"])
        if p["last_terminated"] and p["last_terminated"].get("reason"):
            reasons.append(p["last_terminated"]["reason"])
        if p["phase"] == "Pending" and p["age_seconds"] > 60:
            reasons.append("Pending")
        if p["restarts"] >= 3:
            reasons.append("HighRestartCount")
        if not reasons:
            continue
        detected_reasons.update(reasons)
        problems.append({
            "pod": p["name"],
            "phase": p["phase"],
            "ready": p["ready"],
            "restarts": p["restarts"],
            "reasons": sorted(set(reasons)),
            "waiting_reason": p["waiting_reason"],
            "last_terminated": p["last_terminated"],
        })

    warning_events = [e for e in events if e["type"] == "Warning"][:20]
    for e in warning_events:
        if e["reason"]:
            detected_reasons.add(e["reason"])

    hints = []
    for r in sorted(detected_reasons):
        if r in _TROUBLESHOOT_HINTS:
            hints.append({"reason": r, "action": _TROUBLESHOOT_HINTS[r]})

    return {
        "namespace": namespace,
        "pod_count": len(pods),
        "problem_pod_count": len(problems),
        "problems": problems,
        "warning_events": warning_events,
        "remediation_hints": hints,
        "healthy": len(problems) == 0 and not warning_events,
    }


def describe_pod(namespace: str, pod: str) -> dict[str, Any]:
    """Return a compact kubectl-describe-like summary for one pod."""
    v1 = _core_api()
    p = v1.read_namespaced_pod(name=pod, namespace=namespace)
    container_statuses = []
    for cs in p.status.container_statuses or []:
        entry = {
            "name": cs.name,
            "ready": cs.ready,
            "restarts": cs.restart_count,
            "image": cs.image,
        }
        if cs.state:
            if cs.state.waiting:
                entry["state"] = {"waiting": cs.state.waiting.reason, "message": cs.state.waiting.message}
            elif cs.state.running:
                entry["state"] = {"running": cs.state.running.started_at.isoformat() if cs.state.running.started_at else None}
            elif cs.state.terminated:
                t = cs.state.terminated
                entry["state"] = {"terminated": t.reason, "exit_code": t.exit_code, "message": (t.message or "")[:500]}
        if cs.last_state and cs.last_state.terminated:
            t = cs.last_state.terminated
            entry["last_terminated"] = {"reason": t.reason, "exit_code": t.exit_code, "message": (t.message or "")[:500]}
        container_statuses.append(entry)

    field_selector = f"involvedObject.name={pod}"
    events = v1.list_namespaced_event(namespace, field_selector=field_selector).items
    events.sort(key=lambda e: e.last_timestamp or e.event_time or e.metadata.creation_timestamp, reverse=True)

    return {
        "name": p.metadata.name,
        "namespace": p.metadata.namespace,
        "node": p.spec.node_name or "",
        "phase": p.status.phase,
        "conditions": [
            {"type": c.type, "status": c.status, "reason": c.reason, "message": c.message}
            for c in (p.status.conditions or [])
        ],
        "container_statuses": container_statuses,
        "events": [
            {
                "type": e.type,
                "reason": e.reason,
                "message": (e.message or "")[:500],
                "count": e.count or 1,
            }
            for e in events[:20]
        ],
    }


def format_diagnosis_for_llm(diag: dict[str, Any]) -> str:
    """Compact, token-efficient summary for LLM prompts."""
    lines = [f"Kubernetes diagnosis for namespace `{diag['namespace']}`:"]
    lines.append(f"- pods: {diag['pod_count']} total, {diag['problem_pod_count']} with problems")
    if diag["healthy"]:
        lines.append("- all pods healthy, no warning events")
        return "\n".join(lines)
    if diag["problems"]:
        lines.append("Problem pods:")
        for p in diag["problems"][:10]:
            reasons = ",".join(p["reasons"])
            lt = p.get("last_terminated") or {}
            lt_note = f" last_terminated={lt.get('reason')}(exit={lt.get('exit_code')})" if lt else ""
            lines.append(f"- {p['pod']} phase={p['phase']} ready={p['ready']} restarts={p['restarts']} reasons=[{reasons}]{lt_note}")
    if diag["warning_events"]:
        lines.append("Recent warning events:")
        for e in diag["warning_events"][:10]:
            lines.append(f"- {e['reason']} on {e['object']} (x{e['count']}): {e['message']}")
    if diag["remediation_hints"]:
        lines.append("Known remediation hints:")
        for h in diag["remediation_hints"]:
            lines.append(f"- {h['reason']}: {h['action']}")
    return "\n".join(lines)
