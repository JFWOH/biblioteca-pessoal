import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def main() -> int:
    # Executa apenas a suíte rápida: tests/test_rag_orchestrator.py -q
    # Evita estourar o timeout de 30s do hook pós-edição
    command = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_rag_orchestrator.py",
        "-q",
    ]
    
    print(f"[run_automated_tests] Rodando testes rápidos do RAG: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=25,  # Limite interno para caber no timeout de 30s do hook
        )
        print(result.stdout)
        return result.returncode
    except subprocess.TimeoutExpired:
        print("[run_automated_tests] Erro: Tempo limite esgotado para execução dos testes.")
        return 1
    except Exception as exc:
        print(f"[run_automated_tests] Erro inesperado ao rodar os testes: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())