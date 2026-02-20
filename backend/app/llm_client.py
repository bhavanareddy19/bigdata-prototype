"""LLM client — Ollama only (100 % free & open-source).

Uses Ollama HTTP API for both structured-JSON analysis and free-form chat.
Recommended model: llama3.1:8b  (pull with `ollama pull llama3.1:8b`)
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests

from .settings import get_ollama_base_url, get_ollama_model

logger = logging.getLogger(__name__)


class LlmNotConfiguredError(RuntimeError):
    pass


def llm_available() -> bool:
    """Return True if Ollama is reachable."""
    try:
        r = requests.get(f"{get_ollama_base_url()}/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def call_ollama_chat(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    timeout: int = 120,
) -> str:
    """Generic Ollama chat call — returns the assistant text."""
    base_url = get_ollama_base_url()
    mdl = model or get_ollama_model()
    url = f"{base_url.rstrip('/')}/api/chat"
    payload = {
        "model": mdl,
        "stream": False,
        "messages": messages,
        "options": {"temperature": temperature},
    }
    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return (data.get("message", {}) or {}).get("content", "").strip()


def analyze_with_llm(*, prompt: str) -> dict[str, Any]:
    """Call Ollama expecting STRICT JSON back (for log analysis)."""
    content = call_ollama_chat(
        messages=[
            {"role": "system", "content": "You are a senior SRE/data engineer. Output STRICT JSON only."},
            {"role": "user", "content": prompt},
        ],
    )

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()

    return json.loads(content)
