"""
Hardware Capability Service
Detects system capabilities to decide if we can run Gemma 4 12B or just E4B or fallback.
"""
import logging
import os
import platform
import ctypes

try:
    import torch
    HAS_TORCH = True
except (ImportError, OSError):
    HAS_TORCH = False

logger = logging.getLogger(__name__)


class HardwareCapabilityService:
    def __init__(self):
        self._cached_tier = None

    @staticmethod
    def _get_total_ram_gb() -> float | None:
        """RAM física total em GB — multiplataforma, sem dependências novas.

        Windows: GlobalMemoryStatusEx via ctypes. Linux/macOS: os.sysconf
        (SC_PHYS_PAGES × SC_PAGE_SIZE). Falha → None (chamador assume tier
        padrão; degradação graciosa, ADR-005).
        """
        try:
            if platform.system() == "Windows":
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                return stat.ullTotalPhys / (1024 ** 3)
            # Linux e macOS expõem estes nomes no CPython.
            names = getattr(os, "sysconf_names", {})
            if "SC_PHYS_PAGES" in names and "SC_PAGE_SIZE" in names:
                pages = os.sysconf("SC_PHYS_PAGES")
                page_size = os.sysconf("SC_PAGE_SIZE")
                if pages > 0 and page_size > 0:
                    return (pages * page_size) / (1024 ** 3)
        except Exception as e:
            logger.warning(f"Falha ao detectar RAM total: {e}")
        return None

    def get_recommended_tier(self) -> str:
        if self._cached_tier is not None:
            return self._cached_tier

        tier = "Tier B"  # Default

        try:
            if HAS_TORCH and torch.cuda.is_available():
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram_gb > 10.0:
                    tier = "Tier A"
                else:
                    tier = "Tier B"
            else:
                # Sem GPU: decide pela RAM física (qualquer plataforma).
                ram_gb = self._get_total_ram_gb()
                if ram_gb is not None and ram_gb < 8.0:
                    tier = "Tier C"

        except Exception as e:
            logger.warning(f"Erro ao detectar capability: {e}. Usando Tier B (E4B).")

        self._cached_tier = tier
        return tier

    def get_proactive_model_name(self) -> str:
        tier = self.get_recommended_tier()
        if tier == "Tier A":
            return "gemma4:12b"
        elif tier == "Tier B":
            return "gemma4:e4b"
        else:
            return ""

    def get_recommended_llm_model(self) -> str:
        """Modelo LLM padrão para o assistente RAG, adequado ao hardware.

        gemma4:e4b (leve) é o padrão universal — roda até em notebook básico.
        O 12B só é recomendado quando a GPU comporta (Tier A). Diferente do
        proativo, o assistente NUNCA fica sem modelo: Tier C também usa o e4b
        (mais lento em CPU fraca, mas funcional).
        """
        return "gemma4:12b" if self.get_recommended_tier() == "Tier A" else "gemma4:e4b"

    # Modelo de embeddings do RAG — obrigatório para indexação/busca vetorial.
    EMBED_MODEL = "bge-m3"

    # Tarefas rápidas/estruturadas (flashcard P/R, refino de conceitos do
    # grafo) não precisam do raciocínio do gemma4 — o custo dominante é a
    # fase de thinking, não o tamanho do modelo (benchmark 2026-07-06:
    # e4b 9,8s→3,3s com think=false; 12b 65s→3,9s; gemma3:4b 3,3s).
    # Mantém a MESMA família do padrão do app (e4b roda em qualquer tier)
    # e os chamadores desligam o thinking via ollama_client (think=False).
    FAST_TASK_MODEL = "gemma4:e4b"

    def get_model_for_task(self, task: str) -> str:
        """Modelo preferido por perfil de tarefa: ``"fast"`` ou ``"deep"``.

        ``"deep"`` (padrão) cobre ações que exigem raciocínio — explicar
        página, síntese do dossiê, chat RAG — e usa o mesmo modelo do
        assistente principal (por tier de hardware). ``"fast"`` cobre ações
        rápidas/estruturadas. Chamadores com seu próprio mecanismo de
        override (ex.: config ``graph.llm_model``, parâmetro ``model=`` do
        worker) continuam tendo prioridade — isto só decide o padrão
        quando nada foi configurado explicitamente.
        """
        if task == "fast":
            return self.FAST_TASK_MODEL
        return self.get_recommended_llm_model()
