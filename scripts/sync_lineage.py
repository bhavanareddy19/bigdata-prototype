"""Sync lineage data from Marquez into ChromaDB for RAG queries.

Usage:
    python scripts/sync_lineage.py [--namespace default]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.embedding_pipeline import get_index_stats
from backend.app.lineage_client import sync_lineage_to_vectordb


def main():
    parser = argparse.ArgumentParser(description="Sync Marquez lineage into ChromaDB")
    parser.add_argument("--namespace", default="default", help="Marquez namespace")
    args = parser.parse_args()

    print(f"Syncing lineage from Marquez (namespace={args.namespace})...")
    count = sync_lineage_to_vectordb(args.namespace)
    print(f"Synced {count} lineage events")

    stats = get_index_stats()
    print(f"\nCollection stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
