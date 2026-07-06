"""Worker que transforma um insight em flashcard pergunta/resposta via Ollama.

Item 1 do backlog UX: o insight do proativo entrava como PERGUNTA do card com
o verso vazio. Este worker pede ao LLM um par pergunta/resposta destilado; se
o Ollama estiver indisponível ou a resposta for inválida, o chamador usa o
fallback (insight no verso, pergunta em branco) — ADR-005.
"""

import json
import logging
import urllib.request

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
                # Resolução na thread do worker (rede) — mesma preferência do grafo.
                from src.core.graph.concept_extractor import resolve_llm_model
                model = resolve_llm_model(self._ollama_url)
            if not model:
                self.failed.emit("nenhum modelo do Ollama disponível")
                return

            from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 512, "temperature": 0.2},
            }
            req = urllib.request.Request(
                f"{self._ollama_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                data = json.loads(resp.read())
            content = (data.get("message", {}) or {}).get("content", "")

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
