from __future__ import annotations

from typing import Optional


def fetch_k8s_pod_logs(
    *,
    namespace: str,
    pod: str,
    container: Optional[str],
    tail_lines: int,
    timestamps: bool,
) -> str:
    """Fetch Kubernetes pod logs using the Kubernetes Python client.

    Works either:
    - in-cluster (ServiceAccount token mounted)
    - out-of-cluster (KUBECONFIG)

    Raises an exception on failure.
    """

    from kubernetes import client, config  # type: ignore

    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()

    v1 = client.CoreV1Api()
    return v1.read_namespaced_pod_log(
        name=pod,
        namespace=namespace,
        container=container,
        tail_lines=tail_lines,
        timestamps=timestamps,
        _preload_content=True,
    )
