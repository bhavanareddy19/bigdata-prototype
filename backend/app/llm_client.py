from __future__ import annotations

import os
import json
import logging
from typing import Any

import requests

from .settings import (
    get_llm_provider,
    get_ollama_base_url,
    get_ollama_model,
    get_vertex_model,
)
from .llm_vertex import generate_text as vertex_generate_text

logger = logging.getLogger(__name__)


def llm_available() -> bool:
    provider = get_llm_provider()
    if provider == "vertex":
        return True
    if provider == "ollama":
        try:
            r = requests.get(f"{get_ollama_base_url().rstrip('/')}/api/tags", timeout=5)
            return r.ok
        except Exception:
            return False
    return False


def generate_text(prompt: str) -> str:
    provider = get_llm_provider()
    if provider == "vertex":
        return vertex_generate_text(prompt, get_vertex_model())
    if provider == "ollama":
        return call_ollama_chat(
            messages=[{"role": "user", "content": prompt}],
            model=get_ollama_model(),
        )
    raise RuntimeError(f"Unsupported LLM provider: {provider}")


def call_ollama_chat(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.2,
    timeout: int = 300,
) -> str:
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
    provider = get_llm_provider()

    json_instruction = "\n\nIMPORTANT: Respond with ONLY valid JSON. No markdown, no backticks, no explanation."

    if provider == "vertex":
        content = generate_text(prompt + json_instruction)
    else:
        content = call_ollama_chat(
            messages=[
                {"role": "system", "content": "You are a senior SRE/data engineer. Output STRICT JSON only. No markdown."},
                {"role": "user", "content": prompt},
            ],
        )

    # Strip markdown code fences if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    content = content.strip()

    return json.loads(content)