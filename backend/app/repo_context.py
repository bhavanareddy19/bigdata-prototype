from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RepoSnippet:
    path: str
    snippet: str
    score: int


_ALLOWED_EXTS = {".py", ".sql", ".yml", ".yaml", ".md", ".txt", ".toml", ".json"}


def _is_text_candidate(path: str) -> bool:
    _, ext = os.path.splitext(path.lower())
    return ext in _ALLOWED_EXTS


def search_repo_snippets(
    *,
    root_dir: str,
    query: str,
    max_files: int = 8,
    max_chars_per_file: int = 12000,
    context_lines: int = 6,
) -> list[RepoSnippet]:
    """Lightweight repo search for chatbot grounding.

    This is intentionally simple (no embeddings DB). It searches workspace files for query tokens,
    then returns short snippets around the best matches.
    """

    query = (query or "").strip()
    if not query:
        return []

    tokens = [t for t in query.lower().split() if len(t) >= 3]
    if not tokens:
        tokens = [query.lower()]

    candidates: list[RepoSnippet] = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip common noise
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {".git", ".venv", "__pycache__", "node_modules"} and not d.startswith(".")
        ]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            if not _is_text_candidate(full_path):
                continue
            if os.path.getsize(full_path) > 2_000_000:
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read(max_chars_per_file)
            except Exception:
                continue

            lower = text.lower()
            score = sum(lower.count(t) for t in tokens)
            if score <= 0:
                continue

            lines = text.replace("\r\n", "\n").split("\n")
            best_line = 0
            best_line_score = -1
            for i, line in enumerate(lines):
                line_lower = line.lower()
                line_score = sum(1 for t in tokens if t in line_lower)
                if line_score > best_line_score:
                    best_line_score = line_score
                    best_line = i

            start = max(0, best_line - context_lines)
            end = min(len(lines), best_line + context_lines + 1)
            snippet = "\n".join(lines[start:end]).strip()

            candidates.append(RepoSnippet(path=rel_path, snippet=snippet, score=score))

    candidates.sort(key=lambda s: s.score, reverse=True)
    return candidates[:max_files]
