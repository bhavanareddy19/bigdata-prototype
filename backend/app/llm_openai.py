from __future__ import annotations

import json
from typing import Any


def analyze_with_openai(*, api_key: str, model: str, prompt: str) -> dict[str, Any]:
    """Returns a JSON dict. Raises on hard failures."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    # Use Chat Completions for broad compatibility.
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a senior SRE/data engineer. You read logs and produce concise root-cause analysis. Output STRICT JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    content = (response.choices[0].message.content or "").strip()

    # Some models may wrap in ```json ... ```; handle that defensively.
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()

    return json.loads(content)
