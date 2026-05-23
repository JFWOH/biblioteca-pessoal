import json
import re
import sys
from typing import Any


DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+(/|\*|\.|~|\$HOME)",
    r"\brm\s+-fr\s+(/|\*|\.|~|\$HOME)",
    r"\brmdir\s+/s\b",
    r"\bdel\s+/s\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bgit\s+push\s+.*--force\b",
    r"\bgit\s+push\s+.*-f\b",
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
    r"\btruncate\s+table\b",
    r"\bdelete\s+from\b",
    r"\bupdate\s+.*\s+set\s+.*\s+where\s+1\s*=\s*1\b",
    r"\bchmod\s+-R\s+777\b",
    r"\bchown\s+-R\b",
    r"\bmkfs\b",
    r"\bdd\s+if=.*\s+of=/dev/",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bpoweroff\b",
    r"\bformat\s+[A-Za-z]:",
    r"\bRemove-Item\b.*\b-Recurse\b.*\b-Force\b",
    r"\bdata/chroma_db\b.*\brm\s+-rf\b",
    r"\brm\s+-rf\b.*\bdata/chroma_db\b",
    r"\b\.env\b.*\b(cat|type|more)\b",
    r"\b(cat|type|more)\b.*\b\.env\b",
]


SENSITIVE_PATH_PATTERNS = [
    r"\.env",
    r"id_rsa",
    r"id_ed25519",
    r"credentials",
    r"secrets?",
    r"token",
    r"private[_-]?key",
]


def read_input() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def collect_strings(value: Any) -> list[str]:
    collected: list[str] = []

    if isinstance(value, str):
        collected.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            collected.extend(collect_strings(item))
    elif isinstance(value, list):
        for item in value:
            collected.extend(collect_strings(item))

    return collected


def extract_text(raw: str) -> str:
    fragments = [raw]

    try:
        parsed = json.loads(raw)
        fragments.extend(collect_strings(parsed))
    except Exception:
        pass

    fragments.extend(sys.argv[1:])

    return "\n".join(fragment for fragment in fragments if fragment)


def matches_any(patterns: list[str], text: str) -> str | None:
    normalized = text.replace("\\", "/")
    for pattern in patterns:
        if re.search(pattern, normalized, flags=re.IGNORECASE | re.MULTILINE):
            return pattern
    return None


def main() -> int:
    raw = read_input()
    text = extract_text(raw)

    if not text.strip():
        print("[safety_gate] no command payload detected; allowing execution")
        return 0

    dangerous_match = matches_any(DANGEROUS_PATTERNS, text)
    if dangerous_match:
        print("[safety_gate] BLOCKED: potentially destructive command detected")
        print(f"[safety_gate] matched_pattern={dangerous_match}")
        return 2

    sensitive_match = matches_any(SENSITIVE_PATH_PATTERNS, text)
    if sensitive_match and re.search(r"\b(cat|type|more|print|echo|copy|cp|curl|wget)\b", text, flags=re.IGNORECASE):
        print("[safety_gate] BLOCKED: possible secret exposure command detected")
        print(f"[safety_gate] matched_pattern={sensitive_match}")
        return 2

    print("[safety_gate] allowed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())