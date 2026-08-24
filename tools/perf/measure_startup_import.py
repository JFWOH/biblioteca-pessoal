"""Mede o custo de ``import src.gui.main_window`` (Onda P — rodada UX ago/2026).

Por que subprocesso: o processo que roda a medição já teria os módulos em
``sys.modules``; só um interpretador novo mede o custo real de import. Cada
rodada é um ``sys.executable -c <linha>`` limpo, com o mesmo conteúdo da linha
usada no baseline de julho, acrescida de RSS.

Baseline jul/2026 (para comparação):
    import_ms=2418  modulos=1362  torch_carregado=True  rss_mb=513.4

Uso:
    venv\\Scripts\\python.exe tools/perf/measure_startup_import.py [-n 4]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.perf._common import (  # noqa: E402
    PROJECT_ROOT,
    emit,
    fmt,
    median,
    rss_source,
)

# Código executado no interpretador FILHO. Mesma semântica da linha do baseline
# de julho (perf_counter ao redor do import, len(sys.modules), 'torch' in
# sys.modules), com RSS medido logo após o import.
CHILD_CODE = r"""
import sys, time, os
sys.path.insert(0, PROJECT_ROOT_PLACEHOLDER)
from tools.perf._common import rss_mb
t = time.perf_counter()
import src.gui.main_window  # noqa: F401
ms = (time.perf_counter() - t) * 1000.0
rss = rss_mb()
print("import_ms=%.1f" % ms)
print("modulos=%d" % len(sys.modules))
print("torch_carregado=%s" % ("torch" in sys.modules))
print("rss_mb=%s" % ("%.1f" % rss if rss is not None else "indisponivel"))
"""


def _run_once(timeout: float) -> dict[str, str]:
    """Roda uma medição em interpretador novo e devolve as chaves lidas."""
    code = CHILD_CODE.replace("PROJECT_ROOT_PLACEHOLDER", repr(str(PROJECT_ROOT)))
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"subprocesso falhou (rc={proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    if "import_ms" not in out:
        raise RuntimeError(f"saída inesperada do subprocesso:\n{proc.stdout[-2000:]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-n", "--rodadas", type=int, default=4,
                    help="rodadas totais; a 1ª é descartada (I/O frio). Padrão: 4")
    ap.add_argument("--timeout", type=float, default=300.0,
                    help="timeout por rodada, em segundos. Padrão: 300")
    args = ap.parse_args()

    if args.rodadas < 2:
        print("erro: são necessárias ao menos 2 rodadas (a 1ª é descartada)",
              file=sys.stderr)
        return 2

    resultados: list[dict[str, str]] = []
    for i in range(args.rodadas):
        r = _run_once(args.timeout)
        resultados.append(r)
        rotulo = "descartada" if i == 0 else "válida"
        print(f"# rodada {i + 1}/{args.rodadas} ({rotulo}): "
              f"import_ms={r['import_ms']} rss_mb={r.get('rss_mb')}", flush=True)

    validas = resultados[1:]
    imports = [float(r["import_ms"]) for r in validas]
    modulos = [int(r["modulos"]) for r in validas]
    rss = [float(r["rss_mb"]) for r in validas if r.get("rss_mb", "").replace(".", "", 1).isdigit()]

    print("---")
    emit("medicao", "startup_import")
    emit("rodadas_totais", args.rodadas)
    emit("rodadas_validas", len(validas))
    emit("import_ms", fmt(median(imports)))
    emit("import_ms_todas", ",".join(fmt(v) for v in imports))
    emit("modulos", int(median(modulos)))
    emit("torch_carregado", validas[-1]["torch_carregado"])
    emit("rss_mb", fmt(median(rss)) if rss else "indisponivel")
    emit("rss_fonte", rss_source())
    emit("baseline_jul_import_ms", "2418")
    emit("baseline_jul_modulos", "1362")
    emit("baseline_jul_rss_mb", "513.4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
