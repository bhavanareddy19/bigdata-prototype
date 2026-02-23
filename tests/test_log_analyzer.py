"""Tests for the heuristic log analyzer."""
from __future__ import annotations

from backend.app.log_analyzer import analyze_logs


def test_traceback_detection():
    log = """
2025-01-15 10:30:00 INFO Starting pipeline...
2025-01-15 10:30:05 ERROR Pipeline failed
Traceback (most recent call last):
  File "/opt/app/main.py", line 42, in run
    result = process_data(df)
  File "/opt/app/transform.py", line 18, in process_data
    raise ValueError("Column 'revenue' not found")
ValueError: Column 'revenue' not found
"""
    result = analyze_logs(log_text=log, max_lines=100, mode="heuristic")
    assert result.category == "CodeLogic"
    assert "ValueError" in result.error_signature
    assert result.confidence > 0.4


def test_infrastructure_timeout():
    log = """
2025-01-15 10:30:00 ERROR Connection to database timed out
2025-01-15 10:30:01 FATAL ReadTimeout: connection to postgres:5432 timed out after 30s
"""
    result = analyze_logs(log_text=log, max_lines=100, mode="heuristic")
    assert result.category == "Infrastructure"
    assert result.confidence > 0.5


def test_data_quality_missing_column():
    log = """
2025-01-15 10:30:00 ERROR schema mismatch detected
column 'user_email' does not exist in source table
"""
    result = analyze_logs(log_text=log, max_lines=100, mode="heuristic")
    assert result.category == "DataQuality"
    assert result.confidence > 0.5


def test_oom_detection():
    log = """
2025-01-15 10:30:00 CRITICAL OutOfMemory: Java heap space
2025-01-15 10:30:00 FATAL Killed process 1234 (java) total-vm:8192000kB
"""
    result = analyze_logs(log_text=log, max_lines=100, mode="heuristic")
    assert result.category == "Infrastructure"
    assert "oom" in result.evidence.matched_patterns


def test_clean_logs():
    log = """
2025-01-15 10:30:00 INFO Application started successfully
2025-01-15 10:30:01 INFO Health check passed
2025-01-15 10:30:02 INFO Ready to serve requests
"""
    result = analyze_logs(log_text=log, max_lines=100, mode="heuristic")
    assert result.category == "Unknown"
    assert result.confidence < 0.5


def test_module_not_found():
    log = """
ModuleNotFoundError: No module named 'pandas'
"""
    result = analyze_logs(log_text=log, max_lines=100, mode="heuristic")
    assert result.category == "Infrastructure"
    assert "module_missing" in result.evidence.matched_patterns
