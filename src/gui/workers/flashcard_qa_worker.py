"""Worker que transforma um insight em flashcard pergunta/resposta via Ollama.

Item 1 do backlog UX: o insight do proativo entrava como PERGUNTA do card com
o verso vazio. Este worker pede ao LLM um par pergunta/resposta destilado; se
o Ollama estiver indisponível ou a resposta for inválida, o chamador usa o
fallback (insight no verso, pergunta em branco) — ADR-005.
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.study_prompts import build_flashcard_qa_prompt, parse_flashcard_qa

logger = logging.getLogger(__name__)


class FlashcardQAWorker(QThread):
    generated = pyqtSignal(str, str)  # front (pergunta), back (resposta)
    failed = pyqtSignal(str)          # motivo (chamador aplica o fallback)

    def __init__(self, text: str, ollama_url: str = "http://localhost:11434",
                 model: str | None = None, timeout_s: int = 30, parent=None):
        super().__init__(parent)
        self._text = text
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            prompt = build_flashcard_qa_prompt(self._text)
            if not prompt:
                self.failed.emit("insight vazio")
                return

            model = self._model
            if not model:
                # Resolução na thread do worker (rede). Flashcard P/R é tarefa
                # rápida/estruturada (§1.3 da revisão de engenharia).
                from src.core.graph.concept_extractor import resolve_llm_model
                from src.core.hardware_capability_service import HardwareCapabilityService
                model = resolve_llm_model(
                    self._ollama_url,
                    preferred=HardwareCapabilityService().get_model_for_task("fast"))
            if not model:
                self.failed.emit("nenhum modelo do Ollama disponível")
                return

            from src.core import ollama_client
            # think=False: reformatar um insight em P/R não precisa de
            # raciocínio — benchmark 2026-07-06: 9,8s → 3,3s no e4b.
            content = ollama_client.chat_once(
                self._ollama_url, model, [{"role": "user", "content": prompt}],
                response_format="json", temperature=0.2, num_predict=512,
                timeout_s=self._timeout_s, think=False,
            )

            qa = parse_flashcard_qa(content)
            if self._cancelled:
                return
            if qa is None:
                self.failed.emit("resposta do modelo inválida")
                return
            self.generated.emit(qa[0], qa[1])
        except Exception as exc:  # ADR-005: falha vira fallback, nunca crash
            logger.warning("FlashcardQAWorker falhou: %s", exc)
            if not self._cancelled:
                self.failed.emit(str(exc))
