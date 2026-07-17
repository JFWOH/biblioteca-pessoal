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

    def __init__(self, backend: NLLBBackend, text: str, src_lang: str, tgt_lang: str,
                 revise: bool = True):
        super().__init__()
        self.backend = backend
        self.text = text
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.revise = revise

    def run(self):
        try:
            result = self.backend.translate(self.text, self.src_lang, self.tgt_lang)
            # Pós-edição pelo agente principal (gemma4): corrige trechos não
            # traduzidos, repetições e lacunas do NLLB. Falha na revisão →
            # mantém o rascunho (nunca piora; ADR-005).
            if self.revise and (result or "").strip():
                try:
                    from src.core.translation_backends.translation_reviser import (
                        revise_translation,
                    )
                    revised = revise_translation(self.text, result)
                    if revised:
                        result = revised
                except Exception as exc:
                    logger.debug(f"Revisão da tradução indisponível: {exc}")
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

    @classmethod
    def reset_instance(cls) -> None:
        """Descarta o singleton COM os workers já finalizados (uso em testes).

        Largar ``_instance = None`` com um ``TranslationWorker`` ainda vivo
        deixa o QThread ser destruído pelo GC com a thread do SO rodando —
        abort nativo ("QThread: Destroyed while thread is still running").
        Era a causa do SIGABRT recorrente do CI em
        ``test_translation_service.py`` (faulthandler, PR #32: 3/3 tentativas
        no mesmo teste). Sempre espere os workers antes de soltar a instância.
        """
        inst = cls._instance
        if inst is not None:
            inst.wait_for_workers()
        cls._instance = None

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
        revise = bool(self.config.get("revise_with_llm", True))

        worker = TranslationWorker(self.backend, text, src, tgt, revise=revise)
        
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
        # ``finished``/``error`` são emitidos DENTRO de run(): quando este slot
        # roda (fila do event loop da thread principal), a thread do SO pode
        # ainda não ter saído de run(). deleteLater() sem wait() abre a janela
        # do abort nativo "QThread: Destroyed while thread is still running"
        # (flake do CI capturado por faulthandler). O wait() aqui retorna em
        # microssegundos — o emit é a última instrução de run().
        worker.wait()
        worker.deleteLater()

    def wait_for_workers(self, timeout_ms: int = 5000) -> None:
        """Aguarda todos os workers ativos terminarem (encerramento/testes)."""
        for worker in list(self._active_workers):
            try:
                worker.wait(timeout_ms)
            except RuntimeError:
                # Worker já destruído pelo Qt — nada a esperar (ADR-005).
                pass
        self._active_workers.clear()
