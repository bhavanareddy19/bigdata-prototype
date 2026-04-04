from __future__ import annotations

import json
import os
from typing import Any


OPS_FILE = os.getenv("OPS_SNAPSHOT_PATH", "/tmp/ops_latest_status.json")


def load_ops_snapshot() -> dict[str, Any]:
    if not os.path.exists(OPS_FILE):
        return {"generated_at": None, "dags": [], "recent_failures": []}
    try:
        with open(OPS_FILE) as f:
            return json.load(f)
    except Exception:
        return {"generated_at": None, "dags": [], "recent_failures": []}


def save_ops_snapshot(snapshot: dict[str, Any]) -> None:
    with open(OPS_FILE, "w") as f:
        json.dump(snapshot, f, indent=2)
