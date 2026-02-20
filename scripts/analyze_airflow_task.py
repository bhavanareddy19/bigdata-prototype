from __future__ import annotations

import argparse
import os

import requests
from dotenv import load_dotenv


load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Airflow task logs via the agent backend.")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--airflow-base-url", default=os.getenv("AIRFLOW_BASE_URL", None))
    parser.add_argument("--dag-id", required=True)
    parser.add_argument("--dag-run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--try-number", type=int, default=1)
    parser.add_argument("--mode", default="auto", choices=["auto", "heuristic", "llm"])
    parser.add_argument("--max-lines", type=int, default=250)
    args = parser.parse_args()

    payload = {
        "airflow_base_url": args.airflow_base_url,
        "dag_id": args.dag_id,
        "dag_run_id": args.dag_run_id,
        "task_id": args.task_id,
        "try_number": args.try_number,
        "mode": args.mode,
        "max_lines": args.max_lines,
    }

    r = requests.post(f"{args.backend.rstrip('/')}/analyze-airflow-task", json=payload, timeout=180)
    r.raise_for_status()
    print(r.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
