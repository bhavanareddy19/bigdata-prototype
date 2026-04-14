"""RAG Engine — Retrieval-Augmented Generation.

Flow:
1. Encode user query with sentence-transformers
2. Search ChromaDB collections (code, logs, DAG metadata, lineage)
3. Assemble retrieved context
4. Build prompt with context + user question
5. Send prompt to the configured LLM provider
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .embedding_pipeline import embed_single
from .llm_client import generate_text
from .vectordb_client import (
    COLL_CODE,
    COLL_DAG_META,
    COLL_LINEAGE,
    COLL_LOGS,
    collection_count,
    query_collection,
)

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    collection: str
    document: str
    metadata: dict[str, Any]
    distance: float


@dataclass
class RAGResult:
    answer: str
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    prompt_tokens_approx: int = 0


def _search_collection(
    collection_name: str,
    query_embedding: list[float],
    n_results: int = 5,
) -> list[RetrievedChunk]:
    """Search a single collection and return typed chunks."""
    try:
        count = collection_count(collection_name)
        if count == 0:
            return []
    except Exception:
        return []

    result = query_collection(
        collection_name,
        query_embedding=query_embedding,
        n_results=n_results,
    )

    chunks: list[RetrievedChunk] = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]

    for doc, meta, dist in zip(docs, metas, dists):
        chunks.append(
            RetrievedChunk(
                collection=collection_name,
                document=doc,
                metadata=meta or {},
                distance=dist,
            )
        )
    return chunks


def retrieve(
    query: str,
    *,
    n_code: int = 5,
    n_logs: int = 3,
    n_dag: int = 3,
    n_lineage: int = 3,
    distance_threshold: float = 1.5,
) -> list[RetrievedChunk]:
    """Retrieve relevant chunks from all collections."""
    query_embedding = embed_single(query)

    all_chunks: list[RetrievedChunk] = []

    for coll_name, n in [
        (COLL_CODE, n_code),
        (COLL_LOGS, n_logs),
        (COLL_DAG_META, n_dag),
        (COLL_LINEAGE, n_lineage),
    ]:
        chunks = _search_collection(coll_name, query_embedding, n_results=n)
        all_chunks.extend(chunks)

    filtered = [c for c in all_chunks if c.distance <= distance_threshold]
    filtered.sort(key=lambda c: c.distance)

    logger.info(
        "Retrieved %d chunks (from %d raw) for query: %s...",
        len(filtered),
        len(all_chunks),
        query[:60],
    )
    return filtered


_INTERNAL_FILE_PREFIXES = (
    "backend/app/",
    "backend\\app\\",
    "app/",
)


def _is_internal_backend_file(file_path: str) -> bool:
    """Return True for internal backend source files that users shouldn't see cited."""
    if not file_path:
        return False
    norm = file_path.replace("\\", "/")
    return any(norm.startswith(p) for p in ("backend/app/", "app/")) and norm.endswith(".py")


def _build_context_block(chunks: list[RetrievedChunk], max_chars: int = 12000) -> str:
    """Build a context string from retrieved chunks."""
    if not chunks:
        return "(No indexed context available. Run `python scripts/index_codebase.py` to index the project.)"

    blocks: list[str] = []
    total = 0

    for c in chunks:
        file_path = (
            c.metadata.get("file")
            or c.metadata.get("dag_id")
            or c.metadata.get("job_name")
            or ""
        )

        # Skip internal backend Python files — users should never see these cited
        if _is_internal_backend_file(file_path):
            continue

        label = c.collection.replace("_", " ").title()
        header = f"[{label}] {file_path}" if file_path else f"[{label}]"
        block = f"--- {header} (relevance: {1 - c.distance:.2f}) ---\n{c.document}\n"

        if total + len(block) > max_chars:
            break

        blocks.append(block)
        total += len(block)

    if not blocks:
        return "(No user-relevant indexed context found for this query.)"

    return "\n".join(blocks)


SYSTEM_PROMPT = """\
You are a senior SRE / data engineer assistant for a Big Data platform. You help engineers understand the platform, debug issues, and make sense of pipeline failures.

The platform uses:
- Apache Airflow for DAG orchestration (pipelines: data_ingestion, data_transformation, data_quality_checks, ml_pipeline, demo_observability_dag)
- OpenLineage + Marquez for data lineage tracking
- FastAPI backend with RAG-powered chat for ops visibility
- ChromaDB for vector search over logs and pipeline metadata
- Google Cloud Storage, BigQuery, and GKE for infrastructure

When answering:
- Be thorough and descriptive. Explain the "what", "why", and "how" — not just a one-liner.
- For pipeline/DAG questions: describe what the DAG does, what each task does, what data flows through it, and what to check if something fails.
- For error/log questions: explain what the error means, why it likely happened, what impact it has, and give step-by-step next actions.
- For general platform questions: give a full picture with context, not just bullet points. Use examples from the actual DAGs and tasks in this project.
- Use clear headings or bullet structure when the answer has multiple parts.
- If you are unsure about something, say so rather than guessing.
- Never mention internal backend source files (e.g. backend/app/*.py), internal function names, or implementation details the user does not need to act on.
- Keep the answer user-facing: focus on pipelines, tasks, data, and operational steps.
"""


def _build_prompt(
    *,
    question: str,
    context_block: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    history_block = ""
    if history:
        history_lines: list[str] = []
        for msg in history[-10:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_lines.append(f"{role.upper()}: {content}")
        history_block = "\n".join(history_lines)

    parts = [
        SYSTEM_PROMPT,
        "",
        "Retrieved context:",
        context_block,
    ]

    if history_block:
        parts.extend(["", "Recent conversation history:", history_block])

    parts.extend(
        [
            "",
            f"User question: {question}",
            "",
            "Answer clearly and concisely.",
        ]
    )

    return "\n".join(parts)


def rag_query(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    extra_context: str = "",
    n_code: int = 5,
    n_logs: int = 3,
    n_dag: int = 3,
    n_lineage: int = 3,
) -> RAGResult:
    """Full RAG pipeline: retrieve → build prompt → call LLM → return answer."""

    chunks = retrieve(
        question,
        n_code=n_code,
        n_logs=n_logs,
        n_dag=n_dag,
        n_lineage=n_lineage,
    )

    context_block = _build_context_block(chunks)
    if extra_context:
        context_block = f"{extra_context}\n\n{context_block}"

    prompt = _build_prompt(
        question=question,
        context_block=context_block,
        history=history,
    )

    answer = generate_text(prompt)

    return RAGResult(
        answer=answer,
        retrieved_chunks=chunks,
        prompt_tokens_approx=len(prompt) // 4,
    )