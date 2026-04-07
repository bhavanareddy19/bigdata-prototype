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


def _build_context_block(chunks: list[RetrievedChunk], max_chars: int = 12000) -> str:
    """Build a context string from retrieved chunks."""
    if not chunks:
        return "(No indexed context available. Run `python scripts/index_codebase.py` to index the project.)"

    blocks: list[str] = []
    total = 0

    for c in chunks:
        label = c.collection.replace("_", " ").title()
        source = (
            c.metadata.get("file")
            or c.metadata.get("dag_id")
            or c.metadata.get("job_name")
            or ""
        )
        header = f"[{label}] {source}" if source else f"[{label}]"
        block = f"--- {header} (relevance: {1 - c.distance:.2f}) ---\n{c.document}\n"

        if total + len(block) > max_chars:
            break

        blocks.append(block)
        total += len(block)

    return "\n".join(blocks)


SYSTEM_PROMPT = """\
You are a senior SRE / data engineer chatbot for a Big Data platform.

The platform uses:
- Apache Airflow for DAG orchestration
- OpenLineage + Marquez for lineage tracking
- Cloud Run / FastAPI for backend services
- ChromaDB for vector retrieval
- Google Cloud services for storage and deployment

Rules:
- Answer concisely and practically using the provided context.
- If logs show an error: explain what happened, likely root cause, and concrete next steps.
- If asked about the project: answer using the retrieved context snippets.
- If you are unsure, say so. Do not fabricate information.
- Reference specific files when possible.
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