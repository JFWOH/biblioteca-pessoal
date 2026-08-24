"""
Hardware Capability Service
Detects system capabilities to decide if we can run Gemma 4 12B or just E4B or fallback.
"""
import logging
import os
import platform
import ctypes

logger = logging.getLogger(__name__)

_TORCH_NAO_TENTADO = object()
_torch_mod = _TORCH_NAO_TENTADO


def get_torch():
    """Módulo ``torch``, ou ``None`` se indisponível (import tardio, com cache).

    Substitui a antiga constante ``HAS_TORCH``: este módulo está na cadeia de
    import da janela principal, e importar o torch no topo cobrava ~1,9s e
    ~450MB de RSS em TODA abertura do app, mesmo sem ninguém usar GPU. Torch
    ausente/quebrado (DLL CUDA incompatível) continua sendo degradação
    graciosa, não erro (ADR-005).
    """
    global _torch_mod
    if _torch_mod is _TORCH_NAO_TENTADO:
        try:
            import torch
            _torch_mod = torch
        except (ImportError, OSError) as e:
            logger.debug(f"torch indisponível ({e}); seguindo sem detecção de GPU.")
            _torch_mod = None
    return _torch_mod


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
            torch = get_torch()
            if torch is not None and torch.cuda.is_available():
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

    # Modelo de tarefa rápida que COEXISTE com o de chat na VRAM (rodada UX
    # ago/2026, onda Q).
    #
    # Problema: chat e tarefa rápida usam pesos diferentes e o Ollama só
    # mantém residente o que cabe. Alternar chat ↔ FAST_TASK_MODEL numa GPU de
    # 16GB força descarregar um para carregar o outro — ~8GB de recarga a cada
    # ida e volta (ver a nota de troca de modelo no orchestrator), que o
    # usuário sente como "a IA travou" no meio da leitura.
    #
    # qwen3.5:4b ocupa ~3,4GB e cabe AO LADO do modelo de chat (12b, ~8GB) nos
    # 16GB: as duas cargas convivem, o Ollama para de fazer swap e a troca sai
    # de segundos para ~zero. Só é usado quando JÁ está instalado no Ollama
    # local (ver ``fast_task_model_available``); nada é baixado automaticamente
    # e, sem ele, o comportamento é exatamente o de antes.
    FAST_TASK_COEXIST_MODEL = "qwen3.5:4b"

    # Cache da sonda de disponibilidade, por URL do Ollama: {url: (ts, bool)}.
    # É atributo de CLASSE porque os chamadores instanciam o serviço a cada
    # uso (``HardwareCapabilityService().get_model_for_task("fast")``) — cache
    # de instância não sobreviveria e cada tarefa rápida pagaria um HTTP.
    _coexist_probe_cache: dict[str, tuple[float, bool]] = {}
    # TTL curto o bastante para o app perceber, ainda na mesma sessão, que o
    # usuário instalou o modelo; longo o bastante para não sondar toda hora.
    _COEXIST_PROBE_TTL_S = 10 * 60.0

    @classmethod
    def reset_fast_task_probe(cls) -> None:
        """Esquece o resultado da sonda (usado em testes e após um pull)."""
        cls._coexist_probe_cache.clear()

    @classmethod
    def fast_task_model_available(cls, ollama_url: str = "http://localhost:11434",
                                  timeout_s: float = 2.0) -> bool:
        """``True`` se ``FAST_TASK_COEXIST_MODEL`` está instalado no Ollama.

        Consulta ``/api/tags`` com timeout curto e guarda o resultado em cache
        (TTL de ``_COEXIST_PROBE_TTL_S``). Qualquer falha — daemon fora do ar,
        rede, JSON inesperado — devolve ``False``, ou seja, mantém o modelo
        atual (ADR-005: a otimização degrada para o comportamento de sempre).

        Exige TAG EXATO: outro tag da mesma base (ex.: ``qwen3.5:14b``) não
        caberia junto do modelo de chat e traria a recarga de volta.
        """
        import json
        import time
        import urllib.request

        url = ollama_url.rstrip("/")
        now = time.monotonic()
        cached = cls._coexist_probe_cache.get(url)
        if cached is not None and (now - cached[0]) < cls._COEXIST_PROBE_TTL_S:
            return cached[1]

        available = False
        try:
            req = urllib.request.Request(f"{url}/api/tags")
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                data = json.loads(resp.read())
            names = {m.get("name", "") for m in data.get("models", [])}
            available = cls.FAST_TASK_COEXIST_MODEL in names
        except Exception as e:
            logger.debug(f"Sonda de modelos do Ollama falhou ({e}); "
                         f"mantendo {cls.FAST_TASK_MODEL} nas tarefas rápidas.")
        cls._coexist_probe_cache[url] = (now, available)
        return available

    def get_model_for_task(self, task: str,
                           ollama_url: str = "http://localhost:11434") -> str:
        """Modelo preferido por perfil de tarefa: ``"fast"`` ou ``"deep"``.

        ``"deep"`` (padrão) cobre ações que exigem raciocínio — explicar
        página, síntese do dossiê, chat RAG — e usa o mesmo modelo do
        assistente principal (por tier de hardware). ``"fast"`` cobre ações
        rápidas/estruturadas: prefere o modelo que COEXISTE com o de chat na
        VRAM quando ele está instalado, senão mantém ``FAST_TASK_MODEL``.
        Chamadores com seu próprio mecanismo de override (ex.: config
        ``graph.llm_model``, parâmetro ``model=`` do worker) continuam tendo
        prioridade — isto só decide o padrão quando nada foi configurado
        explicitamente.
        """
        if task == "fast":
            if self.fast_task_model_available(ollama_url):
                return self.FAST_TASK_COEXIST_MODEL
            return self.FAST_TASK_MODEL
        return self.get_recommended_llm_model()
