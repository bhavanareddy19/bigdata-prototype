from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


# ── App / Environment ─────────────────────────────────────

def get_app_env() -> str:
    return os.getenv("APP_ENV", "dev").strip().lower()


def get_backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000").strip()


def get_frontend_url() -> str:
    return os.getenv("FRONTEND_URL", "http://localhost:8501").strip()


# ── LLM Provider ──────────────────────────────────────────

def get_llm_provider() -> str:
    """
    Supported:
      - ollama  -> local development
      - vertex  -> GCP deployment
    """
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower()


def get_ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()


def get_ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.2:1b").strip()


def get_ollama_embed_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip()


def get_vertex_project_id() -> str:
    return os.getenv("VERTEX_PROJECT_ID", "").strip()


def get_vertex_location() -> str:
    return os.getenv("VERTEX_LOCATION", "us-central1").strip()


def get_vertex_model() -> str:
    return os.getenv("VERTEX_MODEL", "gemini-1.5-flash").strip()


# ── Database / Vector Store ───────────────────────────────

def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def get_vector_store_provider() -> str:
    """
    Supported:
      - chroma_local
      - chroma_server
      - pgvector
    """
    return os.getenv("VECTOR_STORE_PROVIDER", "chroma_local").strip().lower()


# Backward-compatible Chroma settings for local dev
def get_chromadb_host() -> str:
    return os.getenv("CHROMADB_HOST", "localhost").strip()


def get_chromadb_port() -> int:
    return int(os.getenv("CHROMADB_PORT", "8100"))


def get_chromadb_persist_dir() -> str:
    return os.getenv("CHROMADB_PERSIST_DIR", os.path.join(_workspace_root(), ".chromadb"))


def get_chromadb_mode() -> str:
    return os.getenv("CHROMADB_MODE", "local").strip().lower()


# ── Marquez / OpenLineage ─────────────────────────────────

def get_marquez_url() -> str:
    return os.getenv("MARQUEZ_URL", "").strip()


def get_pipeline_namespace() -> str:
    return os.getenv("PIPELINE_NAMESPACE", "bigdata-platform").strip()


# ── Airflow / Composer ────────────────────────────────────

def get_airflow_base_url() -> str:
    return os.getenv("AIRFLOW_BASE_URL", "").strip()


def get_airflow_username() -> str:
    return os.getenv("AIRFLOW_USERNAME", "").strip()


def get_airflow_password() -> str:
    return os.getenv("AIRFLOW_PASSWORD", "").strip()


# ── Storage ───────────────────────────────────────────────

def get_gcs_data_bucket() -> str:
    return os.getenv("GCS_DATA_BUCKET", "").strip()


def get_gcs_landing_prefix() -> str:
    return os.getenv("GCS_LANDING_PREFIX", "landing/").strip()


def get_gcs_raw_prefix() -> str:
    return os.getenv("GCS_RAW_PREFIX", "raw/").strip()


def get_gcs_staging_prefix() -> str:
    return os.getenv("GCS_STAGING_PREFIX", "staging/").strip()


def get_gcs_processed_prefix() -> str:
    return os.getenv("GCS_PROCESSED_PREFIX", "processed/").strip()


# ── Embeddings ────────────────────────────────────────────

def get_embedding_model_name() -> str:
    return os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip()


# ── Helpers ───────────────────────────────────────────────

def _workspace_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, "..", ".."))