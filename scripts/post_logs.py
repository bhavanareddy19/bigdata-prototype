from __future__ import annotations

import argparse
import os

import requests
from dotenv import load_dotenv


load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description="Post a log file to the observability agent.")
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--mode", default="auto", choices=["auto", "heuristic", "llm"])
    parser.add_argument("--max-lines", type=int, default=250)
    parser.add_argument("--source", default="ci")
    parser.add_argument("--service", default=None)
    parser.add_argument("--env", dest="environment", default=None)
    parser.add_argument("log_file")
    args = parser.parse_args()

    with open(args.log_file, "r", encoding="utf-8", errors="replace") as f:
        log_text = f.read()

    payload = {
        "log_text": log_text,
        "mode": args.mode,
        "max_lines": args.max_lines,
        "source": args.source,
        "service": args.service,
        "environment": args.environment,
    }

    r = requests.post(f"{args.backend.rstrip('/')}/analyze-log", json=payload, timeout=120)
    r.raise_for_status()
    print(r.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
