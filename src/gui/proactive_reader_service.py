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

    def __init__(self, ollama_url: str = "http://localhost:11434", parent=None):
        super().__init__(parent)
        self.ollama_url = ollama_url
        self.hardware_service = HardwareCapabilityService()
        self.trigger_engine = ProactiveTriggerEngine()
        self.intensity = "Desligado"  # Desligado, Leve, Moderado, Estudo
        self._worker = None

    def set_intensity(self, intensity: str):
        self.intensity = intensity
        self.trigger_engine.reset()

    def process_page_context(self, page_text: str, page_number: int):
        if self.intensity == "Desligado":
            return

        # Se uma observação ainda está sendo gerada, ignora este disparo. Isso
        # evita acúmulo de threads e substitui o antigo QThread.terminate() (que
        # podia corromper estado/derrubar o app). A heurística de cadência do
        # ProactiveTriggerEngine já limita o ritmo dos disparos.
        if self._worker is not None and self._worker.isRunning():
            return

        model = self.hardware_service.get_proactive_model_name()
        if not model:
            return

        if self.trigger_engine.should_trigger(page_text, page_number, self.intensity):
            self._worker = ProactiveWorker(model, page_text, self.ollama_url)
            self._worker.finished.connect(self._on_worker_finished)
            self._worker.start()

    def _on_worker_finished(self, obs: dict):
        self.observation_ready.emit(obs)

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
