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
        self.intensity = "Desligado" # Desligado, Leve, Moderado, Estudo
        self._worker = None
        
    def set_intensity(self, intensity: str):
        self.intensity = intensity
        self.trigger_engine.reset()
        
    def process_page_context(self, page_text: str, page_number: int):
        if self.intensity == "Desligado":
            return
            
        model = self.hardware_service.get_proactive_model_name()
        if not model:
            return
            
        if self.trigger_engine.should_trigger(page_text, page_number, self.intensity):
            if self._worker and self._worker.isRunning():
                self._worker.terminate()
                
            self._worker = ProactiveWorker(model, page_text, self.ollama_url)
            self._worker.finished.connect(self._on_worker_finished)
            self._worker.start()
            
    def _on_worker_finished(self, obs: dict):
        self.observation_ready.emit(obs)
        
    def stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
