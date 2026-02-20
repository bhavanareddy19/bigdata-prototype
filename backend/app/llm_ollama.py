from __future__ import annotations

import json
from typing import Any

import requests


def analyze_with_ollama(*, base_url: str, model: str, prompt: str, timeout: int = 60) -> dict[str, Any]:
    """Call a local Ollama server and return a parsed JSON dict.

    Uses Ollama's chat API. Expects the model to return STRICT JSON.
    """

    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior SRE/data engineer. Output STRICT JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.2},
    }

    r = requests.post(url, json=payload, timeout=timeout)
    r.raise_for_status()

    data = r.json()
    content = (data.get("message", {}) or {}).get("content", "")
    if not isinstance(content, str):
        raise ValueError("Unexpected Ollama response shape (missing message.content)")

    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()

    return json.loads(content)
