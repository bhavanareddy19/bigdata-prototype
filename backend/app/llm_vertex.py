from google import genai
from google.genai.types import HttpOptions

from .settings import get_vertex_project_id, get_vertex_location

_client = None


def get_vertex_client():
    global _client
    if _client is None:
        project = get_vertex_project_id()
        location = get_vertex_location()
        if not project:
            raise RuntimeError(
                "VERTEX_PROJECT_ID is not set. "
                "Add it to your Cloud Run env vars or .env file."
            )
        _client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=HttpOptions(api_version="v1"),
        )
    return _client

def generate_text(prompt: str, model: str) -> str:
    client = get_vertex_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )
    return response.text or ""