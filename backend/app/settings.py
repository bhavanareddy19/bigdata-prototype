from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

# ── LLM (Ollama only — free & open-source) ───────────────


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip()


def get_ollama_embed_model() -> str:
    """Ollama embedding model for RAG (pulled separately)."""
    return os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip()


# ── ChromaDB / VectorDB ──────────────────────────────────


def get_chromadb_host() -> str:
    return os.getenv("CHROMADB_HOST", "localhost").strip()


def get_chromadb_port() -> int:
    return int(os.getenv("CHROMADB_PORT", "8100"))


def get_chromadb_persist_dir() -> str:
    """Local fallback path when running ChromaDB in-process."""
    return os.getenv("CHROMADB_PERSIST_DIR", os.path.join(_workspace_root(), ".chromadb"))


def get_chromadb_mode() -> str:
    """'local' = in-process persistent, 'server' = remote HTTP client."""
    return os.getenv("CHROMADB_MODE", "local").strip().lower()


# ── Marquez / OpenLineage ─────────────────────────────────


def get_marquez_url() -> str:
    return os.getenv("MARQUEZ_URL", "http://localhost:5000").strip()


# ── Airflow ───────────────────────────────────────────────


def get_airflow_base_url() -> str:
    return os.getenv("AIRFLOW_BASE_URL", "http://localhost:8080").strip()


# ── Embedding model (sentence-transformers — free) ────────


def get_embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip()


# ── Helpers ───────────────────────────────────────────────


def _workspace_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))
