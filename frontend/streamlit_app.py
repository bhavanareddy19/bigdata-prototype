from __future__ import annotations

import os

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="BigData Platform — Observability Agent", layout="wide")

st.title("BigData Platform — Observability Agent")
st.caption(
    "RAG-powered chatbot using ChromaDB + Ollama (LLaMA 3.1). "
    "Ask about your code, DAGs, deployments, lineage, or paste logs for analysis."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Settings")
    mode = st.selectbox("Mode", ["auto", "heuristic", "llm"], index=0)
    st.text_input("Backend URL", value=BACKEND_URL, key="backend_url")

    # ── Index controls ───────────────────────────────────
    st.subheader("RAG Index")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Index Codebase", use_container_width=True):
            try:
                resp = requests.post(f"{st.session_state.backend_url}/index/codebase", json={"reset": False}, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                st.success(f"Indexed {data.get('indexed_chunks', 0)} code chunks")
            except Exception as e:
                st.error(f"Indexing failed: {e}")
    with col2:
        if st.button("View Stats", use_container_width=True):
            try:
                resp = requests.get(f"{st.session_state.backend_url}/index/stats", timeout=10)
                resp.raise_for_status()
                stats = resp.json()
                st.json(stats)
            except Exception as e:
                st.error(f"Stats failed: {e}")

    # ── Lineage controls ─────────────────────────────────
    st.subheader("Lineage (Marquez)")
    if st.button("Sync Lineage to VectorDB", use_container_width=True):
        try:
            resp = requests.post(f"{st.session_state.backend_url}/lineage/sync", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            st.success(f"Synced {data.get('synced_events', 0)} lineage events")
        except Exception as e:
            st.warning(f"Lineage sync failed (Marquez may not be running): {e}")

    # ── Optional: Paste logs ─────────────────────────────
    st.subheader("Optional: Paste logs")
    log_text = st.text_area("Logs", height=150, placeholder="Paste failing deploy/job logs here (optional)")

    # ── Optional: Kubernetes pod ─────────────────────────
    st.subheader("Optional: Kubernetes pod")
    use_k8s = st.checkbox("Fetch K8s pod logs", value=False)
    k8s_namespace = st.text_input("Namespace", value="default")
    k8s_pod = st.text_input("Pod name", value="")
    k8s_container = st.text_input("Container (optional)", value="")
    k8s_tail = st.number_input("Tail lines", min_value=10, max_value=5000, value=500, step=50)

    # ── Optional: Airflow task ───────────────────────────
    st.subheader("Optional: Airflow task")
    use_airflow = st.checkbox("Fetch Airflow task logs", value=False)
    airflow_base_url = st.text_input("Airflow Base URL (optional)", value=os.getenv("AIRFLOW_BASE_URL", ""))
    airflow_dag_id = st.text_input("DAG ID", value="")
    airflow_dag_run_id = st.text_input("DAG Run ID", value="")
    airflow_task_id = st.text_input("Task ID", value="")
    airflow_try = st.number_input("Try number", min_value=1, max_value=50, value=1, step=1)

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []


st.subheader("Chat")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input("Ask about DAGs, lineage, deployments, errors, or the codebase...")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages
        if m["role"] in {"user", "assistant"}
    ]

    payload = {
        "question": question,
        "history": history[-12:],
        "mode": mode,
        "include_repo_context": True,
    }

    if log_text.strip():
        payload["log_text"] = log_text

    if use_k8s and k8s_pod.strip():
        payload["k8s"] = {
            "namespace": k8s_namespace.strip() or "default",
            "pod": k8s_pod.strip(),
            "container": k8s_container.strip() or None,
            "tail_lines": int(k8s_tail),
            "timestamps": True,
            "mode": mode,
            "max_lines": 250,
        }

    if use_airflow and airflow_dag_id.strip() and airflow_dag_run_id.strip() and airflow_task_id.strip():
        payload["airflow"] = {
            "airflow_base_url": airflow_base_url.strip() or None,
            "dag_id": airflow_dag_id.strip(),
            "dag_run_id": airflow_dag_run_id.strip(),
            "task_id": airflow_task_id.strip(),
            "try_number": int(airflow_try),
            "mode": mode,
            "max_lines": 250,
        }

    with st.chat_message("assistant"):
        try:
            resp = requests.post(f"{st.session_state.backend_url}/chat", json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "(no answer)")
            st.markdown(answer)

            sources = data.get("sources", [])
            if sources:
                with st.expander("Sources & Retrieved Context"):
                    for s in sources[:8]:
                        src_type = s.get("type", "")
                        path = s.get("path", "")
                        relevance = s.get("relevance", "")
                        header = f"**[{src_type}]** {path}"
                        if relevance:
                            header += f" (relevance: {relevance})"
                        st.markdown(header)
                        st.code(s.get("snippet", ""), language="python")

            diagnostics = data.get("diagnostics")
            if diagnostics:
                with st.expander("Diagnostics"):
                    st.json(diagnostics)

            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            err = f"Request failed: {e}"
            st.error(err)
            st.session_state.messages.append({"role": "assistant", "content": err})
