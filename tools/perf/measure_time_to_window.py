"""Proxy do "tempo até a janela visível" (Onda P — rodada UX ago/2026).

Roda o caminho de partida do app (``src/main.py``) num interpretador NOVO, com
``QT_QPA_PLATFORM=offscreen``, e cronometra as fases:

    prep_ms       AA_ShareOpenGLContexts + import do QtWebEngine (pré-requisitos
                  que ``main.py`` faz antes de instanciar o QApplication)
    import_ms     ``import src.gui.main_window``
    qapp_ms       ``QApplication(...)`` + nome/versão/fonte padrão
    construct_ms  ``MainWindow()``
    show_ms       ``show()`` + ``processEvents()`` até pintar uma vez
    total_ms      t0 → janela pintada

O splash screen do ``main.py`` é omitido de propósito: ele existe para dar
feedback DURANTE essa espera, não faz parte do custo que se quer reduzir.

Ao final o filho chama ``os._exit(0)``: o teardown de Qt+torch no mesmo processo
é a origem do crash instável já documentado no ``conftest`` do projeto, e ele
contaminaria o código de saída da medição.

Uso:
    venv\\Scripts\\python.exe tools/perf/measure_time_to_window.py [--rodadas 3]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.perf._common import PROJECT_ROOT, emit, fmt, median, rss_mb  # noqa: E402

_fase_atual = "inicio"


def _watchdog(limite_s: float) -> None:
    """Mata o filho se alguma fase travar, dizendo ONDE travou."""
    import threading

    def _estourou() -> None:
        print("abortado=timeout", flush=True)
        print(f"abortado_fase={_fase_atual}", flush=True)
        print(f"abortado_apos_s={limite_s:.0f}", flush=True)
        os._exit(3)

    t = threading.Timer(limite_s, _estourou)
    t.daemon = True
    t.start()


def executar_filho(limite_s: float) -> int:
    """Medição propriamente dita — roda no interpretador recém-criado."""
    global _fase_atual
    _watchdog(limite_s)

    t0 = time.perf_counter()

    _fase_atual = "prep"
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import QApplication

    # WebEngine exige isso ANTES do QApplication (igual a src/main.py).
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    from PyQt6.QtWebEngineWidgets import QWebEngineView  # noqa: F401
    prep_ms = (time.perf_counter() - t0) * 1000.0

    _fase_atual = "import_main_window"
    t = time.perf_counter()
    from src.gui.main_window import MainWindow
    import_ms = (time.perf_counter() - t) * 1000.0

    _fase_atual = "qapplication"
    t = time.perf_counter()
    app = QApplication(sys.argv)
    app.setApplicationName("Biblioteca Pessoal")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("BibliotecaPessoal")
    app.setFont(QFont("Segoe UI", 10))
    qapp_ms = (time.perf_counter() - t) * 1000.0

    _fase_atual = "mainwindow_init"
    t = time.perf_counter()
    janela = MainWindow()
    construct_ms = (time.perf_counter() - t) * 1000.0

    _fase_atual = "show"
    t = time.perf_counter()
    janela.show()
    app.processEvents()
    show_ms = (time.perf_counter() - t) * 1000.0

    total_ms = (time.perf_counter() - t0) * 1000.0
    rss = rss_mb()

    print(f"prep_ms={prep_ms:.1f}", flush=True)
    print(f"import_ms={import_ms:.1f}", flush=True)
    print(f"qapp_ms={qapp_ms:.1f}", flush=True)
    print(f"construct_ms={construct_ms:.1f}", flush=True)
    print(f"show_ms={show_ms:.1f}", flush=True)
    print(f"total_ms={total_ms:.1f}", flush=True)
    print(f"rss_mb={rss:.1f}" if rss is not None else "rss_mb=indisponivel", flush=True)
    sys.stdout.flush()
    # Sai sem teardown de Qt/torch (ver docstring).
    os._exit(0)


def _rodada(limite_s: float) -> dict[str, str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--filho",
         "--timeout", str(limite_s)],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=limite_s + 60,
    )
    dados: dict[str, str] = {}
    for linha in proc.stdout.splitlines():
        if "=" in linha and not linha.startswith("#"):
            k, _, v = linha.partition("=")
            dados[k.strip()] = v.strip()
    if "total_ms" not in dados:
        detalhe = dados.get("abortado_fase")
        if detalhe:
            raise RuntimeError(f"medição abortada por timeout na fase '{detalhe}'")
        raise RuntimeError(
            f"subprocesso não produziu medição (rc={proc.returncode}).\n"
            f"stdout:\n{proc.stdout[-1500:]}\nstderr:\n{proc.stderr[-1500:]}"
        )
    return dados


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--filho", action="store_true",
                    help="uso interno: executa a medição neste processo")
    ap.add_argument("--rodadas", type=int, default=3,
                    help="rodadas totais; a 1ª é descartada (I/O frio). Padrão: 3")
    ap.add_argument("--timeout", type=float, default=120.0,
                    help="limite por rodada, em segundos. Padrão: 120")
    args = ap.parse_args()

    if args.filho:
        return executar_filho(args.timeout)

    if args.rodadas < 2:
        print("erro: são necessárias ao menos 2 rodadas (a 1ª é descartada)",
              file=sys.stderr)
        return 2

    resultados = []
    for i in range(args.rodadas):
        r = _rodada(args.timeout)
        resultados.append(r)
        rotulo = "descartada" if i == 0 else "válida"
        print(f"# rodada {i + 1}/{args.rodadas} ({rotulo}): "
              f"total_ms={r['total_ms']}", flush=True)

    validas = resultados[1:]
    print("---")
    emit("medicao", "time_to_window")
    emit("rodadas_totais", args.rodadas)
    emit("rodadas_validas", len(validas))
    for chave in ("prep_ms", "import_ms", "qapp_ms", "construct_ms", "show_ms",
                  "total_ms", "rss_mb"):
        valores = [float(r[chave]) for r in validas
                   if r.get(chave, "").replace(".", "", 1).isdigit()]
        if valores:
            emit(chave, fmt(median(valores)))
            if chave == "total_ms":
                emit("total_ms_todas", ",".join(fmt(v) for v in valores))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
