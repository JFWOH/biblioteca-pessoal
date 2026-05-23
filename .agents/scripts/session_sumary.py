import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAX_OUTPUT_CHARS = 4000


def run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=8,
        )
        return result.returncode, result.stdout or ""
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def main() -> int:
    print("[session_summary] session finished")
    print("[session_summary] required final report:")
    print("- files changed")
    print("- tests executed")
    print("- test results")
    print("- ADRs consulted")
    print("- known risks or skipped checks")

    code, output = run(["git", "status", "--short"])

    if code == 0:
        print("[session_summary] git status:")
        print(output[-MAX_OUTPUT_CHARS:] if output else "clean")
    else:
        print("[session_summary] git status unavailable:")
        print(output[-MAX_OUTPUT_CHARS:])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())