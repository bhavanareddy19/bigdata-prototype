from __future__ import annotations

import argparse
import os

import requests
from dotenv import load_dotenv


load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Kubernetes pod logs via the agent backend.")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--pod", required=True)
    parser.add_argument("--container", default=None)
    parser.add_argument("--tail-lines", type=int, default=500)
    parser.add_argument("--timestamps", action="store_true", default=True)
    parser.add_argument("--no-timestamps", dest="timestamps", action="store_false")
    parser.add_argument("--mode", default="auto", choices=["auto", "heuristic", "llm"])
    parser.add_argument("--max-lines", type=int, default=250)
    args = parser.parse_args()

    payload = {
        "namespace": args.namespace,
        "pod": args.pod,
        "container": args.container,
        "tail_lines": args.tail_lines,
        "timestamps": bool(args.timestamps),
        "mode": args.mode,
        "max_lines": args.max_lines,
    }

    r = requests.post(f"{args.backend.rstrip('/')}/analyze-k8s-pod", json=payload, timeout=180)
    r.raise_for_status()
    print(r.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
