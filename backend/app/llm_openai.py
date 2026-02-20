# This module is deprecated. The platform uses Ollama only (100% free & open-source).
# Kept as a placeholder — all LLM calls go through llm_client.py → Ollama.
raise ImportError("OpenAI is not used. Configure Ollama instead: ollama pull llama3.1:8b")
