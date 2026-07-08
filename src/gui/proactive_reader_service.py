"""Serviço de orquestração do Agente Proativo de Leitura (camada GUI).

Vive em ``src/gui/`` porque é um ``QObject`` que gerencia um ``QThread`` worker
e emite sinais Qt — uma responsabilidade de interface. A lógica pura (detecção
de hardware e heurística de disparo) permanece em ``src/core/`` (ADR-006: o core
não importa GUI/PyQt6).
"""

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.hardware_capability_service import HardwareCapabilityService
from src.core.proactive_trigger_engine import ProactiveTriggerEngine
from src.gui.workers.proactive_worker import ProactiveWorker


class ProactiveReaderService(QObject):
    observation_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, ollama_url: str = "http://localhost:11434", parent=None):
        super().__init__(parent)
        self.ollama_url = ollama_url
        self.hardware_service = HardwareCapabilityService()
        self.trigger_engine = ProactiveTriggerEngine()
        self.intensity = "Desligado"  # Desligado, Leve, Moderado, Estudo
        self._worker = None
        self._cross_ref_fn = None  # função injetada: page_text -> hits vetoriais
        self._observations_fn = None  # função injetada: (book_id, page=None) -> list[dict]
        self._dismissal_history_fn = None  # função injetada: () -> list[dict] (com dispensadas)

    def set_intensity(self, intensity: str):
        self.intensity = intensity
        self.trigger_engine.reset()

    def set_cross_reference(self, fn):
        """Injeta a busca vetorial usada para conectar a página a outros livros."""
        self._cross_ref_fn = fn

    def set_observations_provider(self, fn):
        """Injeta o acesso às observações persistidas (Fase 5 — continuidade).

        ``fn(book_id, page=None) -> list[dict]`` (não dispensadas, mais
        recentes primeiro). O acesso ao SQLite fica na GUI; a lógica do que
        fazer com as observações é pura (src/core/proactive_continuity).
        """
        self._observations_fn = fn

    def set_dismissal_history_provider(self, fn):
        """Injeta o histórico global de observações (Fase 6 — aprendizado).

        ``fn() -> list[dict]`` com ao menos ``kind`` e ``dismissed``, de todos
        os livros (a preferência é do leitor) e INCLUINDO as dispensadas — é
        delas que se aprende. A agregação/formatação é pura
        (src/core/proactive_learning).
        """
        self._dismissal_history_fn = fn

    def process_page_context(self, page_text: str, page_number: int, book_id=None):
        if self.intensity == "Desligado":
            return

        # Se uma observação ainda está sendo gerada, ignora este disparo. Isso
        # evita acúmulo de threads e substitui o antigo QThread.terminate() (que
        # podia corromper estado/derrubar o app). A heurística de cadência do
        # ProactiveTriggerEngine já limita o ritmo dos disparos.
        if self._worker is not None and self._worker.isRunning():
            return

        # Tier do hardware: vazio = máquina fraca → proativo desativado por padrão.
        tier_model = self.hardware_service.get_proactive_model_name()
        if not tier_model:
            return

        if not self.trigger_engine.should_trigger(page_text, page_number, self.intensity):
            return

        # Continuidade (Fase 5): página com observação viva não gera de novo
        # (nem entre sessões); as observações recentes do livro entram no
        # prompt para o agente não se repetir. Falha do provider → segue como
        # antes, sem memória (ADR-005).
        memory_block = ""
        if self._observations_fn is not None and book_id:
            from src.core.proactive_continuity import (
                already_observed_page, build_memory_block,
            )
            try:
                if already_observed_page(self._observations_fn(book_id, page_number)):
                    return
                memory_block = build_memory_block(self._observations_fn(book_id))
            except Exception:
                memory_block = ""

        # Aprendizado (Fase 6): os tipos que o leitor costuma dispensar entram
        # no prompt como orientação (nunca supressão). Falha do provider →
        # segue sem preferência (ADR-005).
        preference_block = ""
        if self._dismissal_history_fn is not None:
            from src.core.proactive_learning import build_preference_block
            try:
                preference_block = build_preference_block(self._dismissal_history_fn())
            except Exception:
                preference_block = ""

        model = self._resolve_model(tier_model)
        if not model:
            # Antes isso falhava em silêncio; agora avisamos o usuário.
            self.error_occurred.emit(
                "Agente proativo: nenhum modelo do Ollama disponível. "
                "Verifique se o Ollama está rodando e se há um modelo baixado."
            )
            return

        self._worker = ProactiveWorker(
            model, page_text, self.ollama_url,
            search_fn=self._cross_ref_fn, book_id=book_id,
            memory_block=memory_block, preference_block=preference_block,
        )
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _resolve_model(self, tier_model: str):
        """Escolhe um modelo instalado no Ollama para o proativo.

        O proativo é frequente e discreto, então favorece velocidade: tenta o
        modelo leve/rápido primeiro, depois o recomendado pelo tier, depois
        qualquer um instalado. Devolve None se nada estiver disponível.
        """
        installed = self._installed_models()
        if not installed:
            return None
        installed_bases: dict[str, str] = {}
        for name in installed:
            installed_bases.setdefault(name.split(":")[0], name)
        for pref in ("gemma4:e4b", tier_model, "gemma3:4b", "gemma2:2b"):
            if not pref:
                continue
            if pref in installed:
                return pref
            base = pref.split(":")[0]
            if base in installed_bases:
                return installed_bases[base]
        return installed[0]

    def _installed_models(self) -> list[str]:
        """Lista os nomes de modelos instalados no Ollama (vazio em caso de falha)."""
        try:
            import json
            import urllib.request
            req = urllib.request.Request(f"{self.ollama_url.rstrip('/')}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def _on_worker_finished(self, obs: dict):
        self.observation_ready.emit(obs)

    def _on_worker_error(self, msg: str):
        self.error_occurred.emit(f"Agente proativo: {msg}")

    def stop(self):
        """Cancelamento cooperativo (sem terminate): descarta o resultado pendente.

        Marca o worker como cancelado para que ele não emita, desconecta o sinal
        para evitar mutação tardia da UI e aguarda brevemente o término natural.
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            try:
                self._worker.finished.disconnect(self._on_worker_finished)
            except (TypeError, RuntimeError):
                pass
            self._worker.wait(2000)
        self._worker = None
