"""Basic tests for the FastAPI backend."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_analyze_log_heuristic():
    payload = {
        "log_text": "Traceback (most recent call last):\n  File 'app.py', line 10\nValueError: invalid literal",
        "mode": "heuristic",
        "max_lines": 100,
    }
    resp = client.post("/analyze-log", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] in ["Infrastructure", "CodeLogic", "DataQuality", "Unknown"]
    assert len(data["error_signature"]) > 0
    assert len(data["next_actions"]) > 0


def test_analyze_log_empty():
    payload = {
        "log_text": "Everything is fine\nNo errors here\nAll services healthy",
        "mode": "heuristic",
        "max_lines": 50,
    }
    resp = client.post("/analyze-log", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "Unknown"


def test_index_stats():
    resp = client.get("/index/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "code_chunks" in data
    assert "log_entries" in data
    assert "dag_metadata" in data
    assert "lineage_events" in data


def test_chat_heuristic_fallback():
    """When mode=heuristic, chat should work even without Ollama."""
    payload = {
        "question": "What DAGs does this project have?",
        "mode": "heuristic",
        "history": [],
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert len(data["answer"]) > 0
