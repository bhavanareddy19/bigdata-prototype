from google import genai
from google.genai.types import HttpOptions
from .settings import get_vertex_project_id, get_vertex_location
import os
import time

_client = None

def get_vertex_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
        if api_key:
            # Google AI Studio API key — uses generativelanguage.googleapis.com
            # NOT vertexai=True which uses aiplatform.googleapis.com
            _client = genai.Client(api_key=api_key)
        else:
            project = get_vertex_project_id()
            location = get_vertex_location()
            if not project:
                raise RuntimeError("VERTEX_PROJECT_ID not set.")
            _client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
                http_options=HttpOptions(api_version="v1beta1"),
            )
    return _client

def generate_text(prompt: str, model: str) -> str:
    client = get_vertex_client()
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
            )
            return response.text or ""
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                if attempt < 2:
                    wait = 30 * (attempt + 1)
                    print(f"Rate limited. Waiting {wait}s before retry {attempt+1}/2...")
                    time.sleep(wait)
                    continue
                raise RuntimeError(
                    "AI model is temporarily rate-limited. "
                    "Please wait a minute and try again."
                )
            raise
    return ""