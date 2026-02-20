from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv


load_dotenv()


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a command, capture its logs, and if it fails post the logs to the observability agent. "
            "This is the easiest way to make log analysis automatic in a deployment environment."
        )
    )
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--mode", default="auto", choices=["auto", "heuristic", "llm"])
    parser.add_argument("--max-lines", type=int, default=400)
    parser.add_argument("--source", default="deployment")
    parser.add_argument("--service", default=None)
    parser.add_argument("--env", dest="environment", default=None)
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional path to write full logs. If omitted, writes to ./deploy-<timestamp>.log",
    )
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run (prefix with --).")
    args = parser.parse_args()

    if not args.cmd or args.cmd[0] != "--":
        print("Usage: python scripts/analyze_command.py [options] -- <your command>")
        return 2

    cmd = args.cmd[1:]
    log_file = args.log_file or f"deploy-{_now_stamp()}.log"

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    with open(log_file, "w", encoding="utf-8", errors="replace") as f:
        f.write(proc.stdout or "")

    # Always print command output so CI logs still show it.
    if proc.stdout:
        sys.stdout.write(proc.stdout)

    if proc.returncode == 0:
        return 0

    payload = {
        "log_text": proc.stdout or "",
        "mode": args.mode,
        "max_lines": args.max_lines,
        "source": args.source,
        "service": args.service,
        "environment": args.environment,
    }

    try:
        r = requests.post(f"{args.backend.rstrip('/')}/analyze-log", json=payload, timeout=180)
        r.raise_for_status()
        analysis = r.json()

        print("\n--- Observability Agent Summary ---")
        print(f"Category: {analysis.get('category')}")
        print(f"Signature: {analysis.get('error_signature')}")
        print(f"Summary: {analysis.get('summary')}")
        print(f"Root cause: {analysis.get('suspected_root_cause')}")
        print("Next actions:")
        for item in analysis.get("next_actions", []):
            print(f"- {item}")
        print(f"(Full logs saved to {log_file})")

    except Exception as e:
        print(f"\n[agent] Failed to analyze logs: {e}")
        print(f"(Full logs saved to {log_file})")

    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
