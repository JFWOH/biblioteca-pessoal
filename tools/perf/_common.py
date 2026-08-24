"""Utilidades compartilhadas pelo harness de medição (Onda P — rodada UX ago/2026).

Nada aqui importa PyQt6: os scripts que precisam de Qt fazem isso por conta própria.
ADR-006 não se aplica a ``tools/`` (são ferramentas, não ``src/core``), mas manter
este módulo puro evita que um simples ``import`` já distorça a medição.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

# Raiz do projeto (worktree): tools/perf/_common.py -> parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def ensure_project_root_on_path() -> Path:
    """Garante que ``import src...`` funcione mesmo rodando o script de outro cwd."""
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return PROJECT_ROOT


def rss_mb() -> float | None:
    """RSS (working set) do processo ATUAL, em MB.

    Usa ``psutil`` quando disponível; senão cai para ``GetProcessMemoryInfo`` via
    ctypes (Windows). Devolve ``None`` quando nenhum dos dois funciona.
    """
    try:
        import psutil  # type: ignore

        return psutil.Process().memory_info().rss / (1024 * 1024)
    except Exception:
        pass

    try:
        import ctypes
        from ctypes import wintypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        ok = psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        )
        if not ok:
            return None
        return counters.WorkingSetSize / (1024 * 1024)
    except Exception:
        return None


def rss_source() -> str:
    """Qual implementação de RSS está em uso (para constar no relatório)."""
    try:
        import psutil  # noqa: F401

        return "psutil"
    except Exception:
        return "ctypes/GetProcessMemoryInfo"


def emit(key: str, value) -> None:
    """Imprime uma linha ``chave=valor`` (formato de saída de todo o harness)."""
    print(f"{key}={value}", flush=True)


def median(values: list[float]) -> float:
    return statistics.median(values)


def fmt(value: float, casas: int = 1) -> str:
    return f"{value:.{casas}f}"
