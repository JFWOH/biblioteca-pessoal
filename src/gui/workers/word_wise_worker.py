"""Worker que gera a definição rápida (Word Wise) de um termo selecionado.

Tarefa 3.4: seleção curta (palavra/termo) → LLM 'fast' (``think=False``,
resposta curta) → definição contextual em PT-BR. Mesmo padrão do
FlashcardQAWorker (tarefa rápida/estruturada — resolve o modelo 'fast' do
hardware e chama o Ollama sem streaming).
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.study_prompts import build_word_wise_prompt

logger = logging.getLogger(__name__)


class WordWiseWorker(QThread):
    """Gera a definição curta de um termo via LLM (``think=False``)."""

    definition_ready = pyqtSignal(str, str)  # term, definition
    failed = pyqtSignal(str)                 # motivo (chamador mostra erro no popover)

    def __init__(self, term: str, context: str = "",
                 ollama_url: str = "http://localhost:11434",
                 model: str | None = None, timeout_s: int = 20, parent=None):
        super().__init__(parent)
        self._term = term
        self._context = context
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            prompt = build_word_wise_prompt(self._term, self._context)
            if not prompt:
                self.failed.emit("termo vazio")
                return

            model = self._model
            if not model:
                # Resolução na thread do worker (rede). Definição rápida é
                # tarefa 'fast' — mesmo critério do FlashcardQAWorker.
                from src.core.graph.concept_extractor import resolve_llm_model
                from src.core.hardware_capability_service import HardwareCapabilityService
                model = resolve_llm_model(
                    self._ollama_url,
                    preferred=HardwareCapabilityService().get_model_for_task("fast"))
            if not model:
                self.failed.emit("nenhum modelo do Ollama disponível")
                return

            from src.core import ollama_client
            # think=False: definição de 1-2 frases não precisa de raciocínio
            # (mesma lógica de custo/latência do FlashcardQAWorker).
            content = ollama_client.chat_once(
                self._ollama_url, model, [{"role": "user", "content": prompt}],
                temperature=0.2, num_predict=200,
                timeout_s=self._timeout_s, think=False,
            )
            content = (content or "").strip()
            if self._cancelled:
                return
            if not content:
                self.failed.emit("resposta do modelo vazia")
                return
            self.definition_ready.emit(self._term, content)
        except Exception as exc:  # ADR-005: falha vira aviso no popover, nunca crash
            logger.warning("WordWiseWorker falhou: %s", exc)
            if not self._cancelled:
                self.failed.emit(str(exc))
