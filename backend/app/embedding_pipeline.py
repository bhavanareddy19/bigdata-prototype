"""Embedding pipeline — chunks code, logs, DAG meta, lineage data
and indexes them into ChromaDB using sentence-transformers.

Model: all-MiniLM-L6-v2  (free, ~80 MB, runs on CPU)
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from sentence_transformers import SentenceTransformer

from .settings import get_embedding_model_name
from .vectordb_client import (
    COLL_CODE,
    COLL_DAG_META,
    COLL_LINEAGE,
    COLL_LOGS,
    collection_count,
    upsert_documents,
)

logger = logging.getLogger(__name__)

# Module-level singleton for the embedding model
_model: SentenceTransformer | None = None

_ALLOWED_CODE_EXTS = {".py", ".sql", ".yml", ".yaml", ".md", ".toml", ".json", ".sh", ".cfg", ".txt"}
_SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", ".chromadb", ".mypy_cache", ".pytest_cache"}


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        name = get_embedding_model_name()
        logger.info("Loading embedding model: %s", name)
        _model = SentenceTransformer(name)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts and return float vectors."""
    model = _get_model()
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]


def embed_single(text: str) -> list[float]:
    return embed_texts([text])[0]


# ── Code chunking ────────────────────────────────────────────


@dataclass
class CodeChunk:
    file_path: str
    chunk_index: int
    content: str
    start_line: int
    end_line: int
    metadata: dict[str, Any] = field(default_factory=dict)


def _chunk_file(file_path: str, rel_path: str, chunk_size: int = 60, overlap: int = 10) -> list[CodeChunk]:
    """Split a file into overlapping line-based chunks."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(500_000)  # cap at 500 KB
    except Exception:
        return []

    lines = text.replace("\r\n", "\n").split("\n")
    chunks: list[CodeChunk] = []
    idx = 0
    start = 0
    while start < len(lines):
        end = min(start + chunk_size, len(lines))
        content = "\n".join(lines[start:end])
        if content.strip():
            chunks.append(CodeChunk(
                file_path=rel_path,
                chunk_index=idx,
                content=content,
                start_line=start + 1,
                end_line=end,
                metadata={"file": rel_path, "chunk": idx, "start_line": start + 1, "end_line": end},
            ))
            idx += 1
        start += chunk_size - overlap
    return chunks


def index_codebase(root_dir: str, *, reset: bool = False) -> int:
    """Walk the codebase, chunk files, embed, and store in ChromaDB."""
    from .vectordb_client import reset_collection

    if reset:
        reset_collection(COLL_CODE)

    all_chunks: list[CodeChunk] = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for fname in filenames:
            _, ext = os.path.splitext(fname.lower())
            if ext not in _ALLOWED_CODE_EXTS:
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root_dir)
            if os.path.getsize(full) > 1_000_000:
                continue
            all_chunks.extend(_chunk_file(full, rel))

    if not all_chunks:
        logger.warning("No code chunks found in %s", root_dir)
        return 0

    # Batch embed + upsert
    batch_size = 64
    total = 0
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i : i + batch_size]
        texts = [c.content for c in batch]
        ids = [hashlib.md5(f"{c.file_path}::{c.chunk_index}".encode()).hexdigest() for c in batch]
        metas = [c.metadata for c in batch]
        embeddings = embed_texts(texts)
        upsert_documents(COLL_CODE, ids=ids, documents=texts, embeddings=embeddings, metadatas=metas)
        total += len(batch)

    logger.info("Indexed %d code chunks from %s", total, root_dir)
    return total


# ── Log indexing ─────────────────────────────────────────────


def index_log_entry(log_text: str, source: str = "unknown", metadata: dict[str, Any] | None = None) -> str:
    """Embed and store a single log block. Returns the document ID."""
    doc_id = hashlib.md5(log_text[:500].encode()).hexdigest()
    meta = {"source": source, **(metadata or {})}
    embedding = embed_single(log_text[:8000])
    upsert_documents(COLL_LOGS, ids=[doc_id], documents=[log_text[:8000]], embeddings=[embedding], metadatas=[meta])
    return doc_id


# ── DAG metadata indexing ────────────────────────────────────


def index_dag_metadata(dag_id: str, description: str, tasks: list[str], schedule: str | None = None) -> str:
    doc_id = hashlib.md5(dag_id.encode()).hexdigest()
    text = f"DAG: {dag_id}\nDescription: {description}\nTasks: {', '.join(tasks)}\nSchedule: {schedule or 'manual'}"
    meta = {"dag_id": dag_id, "task_count": len(tasks), "schedule": schedule or "manual"}
    embedding = embed_single(text)
    upsert_documents(COLL_DAG_META, ids=[doc_id], documents=[text], embeddings=[embedding], metadatas=[meta])
    return doc_id


# ── Lineage indexing ─────────────────────────────────────────


def index_lineage_event(run_id: str, job_name: str, event_type: str, inputs: list[str], outputs: list[str]) -> str:
    doc_id = hashlib.md5(f"{run_id}:{job_name}".encode()).hexdigest()
    text = (
        f"Lineage event: {event_type}\n"
        f"Job: {job_name}\n"
        f"Inputs: {', '.join(inputs)}\n"
        f"Outputs: {', '.join(outputs)}\n"
        f"Run ID: {run_id}"
    )
    meta = {"job_name": job_name, "event_type": event_type, "run_id": run_id}
    embedding = embed_single(text)
    upsert_documents(COLL_LINEAGE, ids=[doc_id], documents=[text], embeddings=[embedding], metadatas=[meta])
    return doc_id


# ── Stats ────────────────────────────────────────────────────


def get_index_stats() -> dict[str, int]:
    return {
        "code_chunks": collection_count(COLL_CODE),
        "log_entries": collection_count(COLL_LOGS),
        "dag_metadata": collection_count(COLL_DAG_META),
        "lineage_events": collection_count(COLL_LINEAGE),
    }
