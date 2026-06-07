"""Serviço de Tradução Offline.

Orquestra traduções locais desacopladas para preservar o fluxo do leitor e o isolamento do Core AI.
"""
import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from src.core.translation_backends.nllb_backend import NLLBBackend
from src.core.config import ConfigManager

logger = logging.getLogger(__name__)

class TranslationWorker(QThread):
    """Worker assíncrono para não bloquear a UI principal durante a tradução."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, backend: NLLBBackend, text: str, src_lang: str, tgt_lang: str):
        super().__init__()
        self.backend = backend
        self.text = text
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang

    def run(self):
        try:
            result = self.backend.translate(self.text, self.src_lang, self.tgt_lang)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class TranslationService(QObject):
    """Serviço unificado para lidar com requisições de tradução vindas da UI."""
    
    _instance: Optional['TranslationService'] = None

    @classmethod
    def get_instance(cls) -> 'TranslationService':
        if cls._instance is None:
            cls._instance = TranslationService()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.config = ConfigManager().get("translation", {})
        
        # Padrões definidos pela configuração ou fallback
        model_id = self.config.get("model", "facebook/nllb-200-distilled-600M")
        self.default_src = self.config.get("default_src", "en")
        self.default_tgt = self.config.get("default_tgt", "pt")
        
        self.backend = NLLBBackend(model_id=model_id)
        self._active_workers = []

    def translate_async(self, text: str, src_lang: str = None, tgt_lang: str = None, 
                        on_success=None, on_error=None):
        """
        Dispara uma tradução em background (worker).
        """
        src = src_lang or self.default_src
        tgt = tgt_lang or self.default_tgt
        
        worker = TranslationWorker(self.backend, text, src, tgt)
        
        if on_success:
            worker.finished.connect(on_success)
        if on_error:
            worker.error.connect(on_error)
            
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        worker.error.connect(lambda: self._cleanup_worker(worker))
        
        self._active_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        worker.deleteLater()
