"""ChromaDB vector store client.

Supports two modes:
- local  : in-process persistent client (dev / single-node)
- server : HTTP client pointing at a ChromaDB container
"""
from __future__ import annotations

import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from .settings import get_chromadb_host, get_chromadb_mode, get_chromadb_persist_dir, get_chromadb_port

logger = logging.getLogger(__name__)

# Module-level singleton
_client: chromadb.ClientAPI | None = None

# Collection names
COLL_CODE = "code_embeddings"
COLL_LOGS = "log_embeddings"
COLL_DAG_META = "dag_metadata"
COLL_LINEAGE = "lineage_data"

ALL_COLLECTIONS = [COLL_CODE, COLL_LOGS, COLL_DAG_META, COLL_LINEAGE]


def get_client() -> chromadb.ClientAPI:
    """Return a shared ChromaDB client (created on first call)."""
    global _client
    if _client is not None:
        return _client

    mode = get_chromadb_mode()
    if mode == "server":
        logger.info("Connecting to ChromaDB server at %s:%s", get_chromadb_host(), get_chromadb_port())
        _client = chromadb.HttpClient(
            host=get_chromadb_host(),
            port=get_chromadb_port(),
        )
    else:
        persist_dir = get_chromadb_persist_dir()
        logger.info("Using local ChromaDB at %s", persist_dir)
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
    return _client


def get_or_create_collection(name: str) -> chromadb.Collection:
    client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_documents(
    collection_name: str,
    ids: list[str],
    documents: list[str],
    embeddings: list[list[float]],
    metadatas: list[dict[str, Any]] | None = None,
) -> None:
    coll = get_or_create_collection(collection_name)
    coll.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas or [{} for _ in ids],
    )
    logger.info("Upserted %d docs into '%s'", len(ids), collection_name)


def query_collection(
    collection_name: str,
    query_embedding: list[float],
    n_results: int = 5,
    where: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coll = get_or_create_collection(collection_name)
    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    return coll.query(**kwargs)


def collection_count(collection_name: str) -> int:
    coll = get_or_create_collection(collection_name)
    return coll.count()


def reset_collection(collection_name: str) -> None:
    client = get_client()
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    get_or_create_collection(collection_name)
    logger.info("Reset collection '%s'", collection_name)
