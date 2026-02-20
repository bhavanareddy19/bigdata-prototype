"""Index the project codebase into ChromaDB for RAG.

Usage:
    python scripts/index_codebase.py [--root /path/to/repo] [--reset]

This script walks the project files, chunks them, embeds them with
sentence-transformers (all-MiniLM-L6-v2), and stores in ChromaDB.
After indexing, the /chat endpoint uses RAG to answer questions.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Add project root to path so we can import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.embedding_pipeline import get_index_stats, index_codebase


def main():
    parser = argparse.ArgumentParser(description="Index codebase into ChromaDB for RAG")
    parser.add_argument(
        "--root",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        help="Root directory to index (default: project root)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and re-create the code_embeddings collection before indexing",
    )
    args = parser.parse_args()

    print(f"Indexing codebase: {args.root}")
    print(f"Reset collection: {args.reset}")
    print()

    start = time.time()
    count = index_codebase(args.root, reset=args.reset)
    elapsed = time.time() - start

    stats = get_index_stats()
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Indexed {count} code chunks")
    print(f"\nCollection stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
