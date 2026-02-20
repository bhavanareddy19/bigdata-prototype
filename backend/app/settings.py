from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def get_llm_provider() -> str:
    # ollama | openai | none
    return os.getenv("LLM_PROVIDER", "ollama").strip().lower() or "ollama"


def get_ollama_base_url() -> str | None:
    url = os.getenv("OLLAMA_BASE_URL", "").strip()
    return url or None


def get_ollama_model() -> str | None:
    model = os.getenv("OLLAMA_MODEL", "").strip()
    return model or None


def get_openai_api_key() -> str | None:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return key or None


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
