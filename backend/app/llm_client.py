from __future__ import annotations

from typing import Any

from .settings import (
    get_llm_provider,
    get_ollama_base_url,
    get_ollama_model,
    get_openai_api_key,
    get_openai_model,
)


class LlmNotConfiguredError(RuntimeError):
    pass


def llm_available() -> bool:
    provider = get_llm_provider()
    if provider == "ollama":
        return bool(get_ollama_base_url()) and bool(get_ollama_model())
    if provider == "openai":
        return get_openai_api_key() is not None
    return False


def analyze_with_llm(*, prompt: str) -> dict[str, Any]:
    provider = get_llm_provider()

    if provider == "ollama":
        from .llm_ollama import analyze_with_ollama

        base_url = get_ollama_base_url()
        model = get_ollama_model()
        if not base_url or not model:
            raise LlmNotConfiguredError("OLLAMA_BASE_URL/OLLAMA_MODEL not set")
        return analyze_with_ollama(base_url=base_url, model=model, prompt=prompt)

    if provider == "openai":
        from .llm_openai import analyze_with_openai

        api_key = get_openai_api_key()
        if api_key is None:
            raise LlmNotConfiguredError("OPENAI_API_KEY not set")
        model = get_openai_model()
        return analyze_with_openai(api_key=api_key, model=model, prompt=prompt)

    raise LlmNotConfiguredError("LLM_PROVIDER is set to 'none'")
