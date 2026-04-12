from __future__ import annotations

import re
from dataclasses import dataclass

from .llm_client import analyze_with_llm, llm_available
from .models import AnalyzeLogResponse, Evidence


@dataclass(frozen=True)
class _HeuristicResult:
    category: str
    signature: str
    summary: str
    suspected_root_cause: str
    next_actions: list[str]
    confidence: float
    evidence: Evidence


_ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("traceback", re.compile(r"Traceback \(most recent call last\):")),
    ("exception", re.compile(r"(Exception|Error|FAILED|FATAL|CRITICAL)")),
    ("timeout", re.compile(r"(timed out|timeout|ReadTimeout|ConnectTimeout)", re.IGNORECASE)),
    ("conn_refused", re.compile(r"(Connection refused|ECONNREFUSED)", re.IGNORECASE)),
    ("dns", re.compile(r"(Temporary failure in name resolution|NXDOMAIN|Name or service not known)", re.IGNORECASE)),
    ("auth", re.compile(r"(Permission denied|AccessDenied|Unauthorized|403|401)", re.IGNORECASE)),
    ("missing_column", re.compile(r"(column .* does not exist|missing column|schema mismatch)", re.IGNORECASE)),
    ("null", re.compile(r"(NULL value|not-null constraint|cannot be null)", re.IGNORECASE)),
    ("oom", re.compile(r"(OutOfMemory|Killed process|OOM)", re.IGNORECASE)),
    ("module_missing", re.compile(r"ModuleNotFoundError:|No module named", re.IGNORECASE)),
]


def _tail_lines(text: str, max_lines: int) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > max_lines:
        return lines[-max_lines:]
    return lines


def _extract_traceback(lines: list[str]) -> list[str]:
    last_tb_idx = None
    for i, line in enumerate(lines):
        if "Traceback (most recent call last):" in line:
            last_tb_idx = i

    if last_tb_idx is None:
        return []

    tb: list[str] = []
    for line in lines[last_tb_idx:]:
        tb.append(line)
        # Common end: blank line after exception or next log record prefix
        if len(tb) > 3 and (line.strip() == "" or re.match(r"^\d{4}-\d{2}-\d{2}", line)):
            break
    return tb


def _pick_signature(lines: list[str]) -> str:
    candidates: list[str] = []
    for line in lines:
        if re.search(r"(Exception|Error|FAILED|FATAL|CRITICAL)", line):
            candidates.append(line.strip())

    if candidates:
        return candidates[-1][:240]

    # fallback: last non-empty line
    for line in reversed(lines):
        if line.strip():
            return line.strip()[:240]
    return "(empty log)"


def _categorize(lines: list[str]) -> tuple[str, list[str]]:
    matched: list[str] = []
    text = "\n".join(lines)

    def hit(name: str) -> bool:
        for n, pat in _ERROR_PATTERNS:
            if n == name and pat.search(text):
                matched.append(n)
                return True
        return False

    if hit("missing_column") or hit("null"):
        return "DataQuality", matched

    if hit("timeout") or hit("conn_refused") or hit("dns") or hit("auth") or hit("oom"):
        return "Infrastructure", matched

    if hit("module_missing"):
        return "Infrastructure", matched

    if hit("traceback") or hit("exception"):
        return "CodeLogic", matched

    return "Unknown", matched


def analyze_logs_heuristic(*, log_text: str, max_lines: int) -> _HeuristicResult:
    lines = _tail_lines(log_text, max_lines)
    tb = _extract_traceback(lines)
    signature = _pick_signature(tb or lines)
    category, matched = _categorize(tb or lines)

    important: list[str] = []
    for line in reversed(tb or lines):
        if len(important) >= 12:
            break
        if any(k in line for k in ["ERROR", "CRITICAL", "FATAL", "Traceback", "Exception", "FAILED"]):
            important.append(line.strip())
    important.reverse()

    if category == "Infrastructure":
        suspected = "The failure looks environment/infrastructure related (connectivity, auth, resources, or missing dependency)."
        next_actions = [
            "Check service health (DB, network, credentials) and retry.",
            "Verify secrets/ENV vars used during deployment.",
            "If dependency-related, confirm the runtime image includes required packages.",
        ]
        conf = 0.7 if matched else 0.55
    elif category == "DataQuality":
        suspected = "The failure looks data/schema related (missing column, constraint violation, or schema mismatch)."
        next_actions = [
            "Validate source data/schema; confirm expected columns exist.",
            "Check recent upstream schema changes and update transformation queries.",
            "Add a guardrail check (schema validation) before running the job.",
        ]
        conf = 0.75 if matched else 0.6
    elif category == "CodeLogic":
        suspected = "The failure looks like a code/runtime exception in the application logic."
        next_actions = [
            "Locate the stack trace frame referencing your code and inspect that line.",
            "Reproduce with the same inputs/config locally.",
            "Add input validation and better exception handling around the failing section.",
        ]
        conf = 0.65 if tb else 0.5
    else:
        suspected = "Not enough signal to classify; need more log context."
        next_actions = [
            "Send more logs around the failure (200-500 lines).",
            "Include the command that was running and its exit code.",
        ]
        conf = 0.4

    summary = f"Detected category: {category}. Signature: {signature}"

    return _HeuristicResult(
        category=category,
        signature=signature,
        summary=summary,
        suspected_root_cause=suspected,
        next_actions=next_actions,
        confidence=conf,
        evidence=Evidence(important_lines=important, traceback=tb, matched_patterns=matched),
    )


def analyze_logs(*, log_text: str, max_lines: int, mode: str) -> AnalyzeLogResponse:
    heuristic = analyze_logs_heuristic(log_text=log_text, max_lines=max_lines)

    use_llm = mode == "llm" or (mode == "auto" and llm_available())
    if not use_llm:
        return AnalyzeLogResponse(
            category=heuristic.category,  # type: ignore[arg-type]
            error_signature=heuristic.signature,
            summary=heuristic.summary,
            suspected_root_cause=heuristic.suspected_root_cause,
            next_actions=heuristic.next_actions,
            confidence=heuristic.confidence,
            evidence=heuristic.evidence,
        )

    lines = _tail_lines(log_text, max_lines)
    tb = _extract_traceback(lines)
    focused = "\n".join(tb or lines)

    prompt = (
        "Analyze the following deployment/runtime logs.\n\n"
        "Return STRICT JSON with these keys:\n"
        "category: one of [Infrastructure, CodeLogic, DataQuality, Unknown]\n"
        "error_signature: short string\n"
        "summary: 1-3 sentences\n"
        "suspected_root_cause: 1-2 sentences\n"
        "next_actions: array of 3-6 short bullet-like strings\n"
        "confidence: number 0..1\n\n"
        "Logs:\n"
        f"{focused}\n"
    )

    try:
        raw = analyze_with_llm(prompt=prompt)
        return AnalyzeLogResponse(
            category=raw.get("category", heuristic.category),
            error_signature=raw.get("error_signature", heuristic.signature),
            summary=raw.get("summary", heuristic.summary),
            suspected_root_cause=raw.get("suspected_root_cause", heuristic.suspected_root_cause),
            next_actions=list(raw.get("next_actions", heuristic.next_actions)),
            confidence=float(raw.get("confidence", heuristic.confidence)),
            evidence=heuristic.evidence,
            raw=raw,
        )
    except Exception as llm_err:
        import logging; logging.getLogger(__name__).error(f"LLM failed: {llm_err}")
        # Don’t fail the pipeline because the LLM failed.
        return AnalyzeLogResponse(
            category=heuristic.category,  # type: ignore[arg-type]
            error_signature=heuristic.signature,
            summary=heuristic.summary + " (LLM failed; using heuristic)",
            suspected_root_cause=heuristic.suspected_root_cause,
            next_actions=heuristic.next_actions,
            confidence=heuristic.confidence,
            evidence=heuristic.evidence,
        )
