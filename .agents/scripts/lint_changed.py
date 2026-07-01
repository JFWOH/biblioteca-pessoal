"""Hook PostToolUse (Claude Code): lint advisory do ARQUIVO recém-editado.

Lê o JSON do hook no stdin, extrai tool_input.file_path e roda `ruff check`
apenas nesse arquivo (.py), com o python do venv. É ADVISORY: sempre retorna 0
(nunca bloqueia a edição); só imprime os problemas do arquivo tocado, evitando
o ruído do lint do repositório inteiro.
"""
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_file_path() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    try:
        raw = (sys.stdin.read() or "").lstrip("﻿").strip()
        data = json.loads(raw or "{}")
    except Exception:
        return ""
    tool_input = data.get("tool_input") or {}
    return tool_input.get("file_path") or ""


def main() -> int:
    file_path = _read_file_path()
    if not file_path or not file_path.endswith(".py"):
        return 0

    py = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if not py.exists():
        return 0  # venv ausente: nao atrapalha o fluxo

    try:
        result = subprocess.run(
            [str(py), "-m", "ruff", "check", file_path],
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
        if result.returncode != 0 and (result.stdout or "").strip():
            print(f"[lint] ruff em {Path(file_path).name}:")
            print(result.stdout[-3000:])
    except Exception as exc:
        print(f"[lint] ignorado ({type(exc).__name__})")
    return 0  # advisory: nunca bloqueia


if __name__ == "__main__":
    raise SystemExit(main())
