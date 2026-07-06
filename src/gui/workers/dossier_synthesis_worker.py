"""Worker que gera a síntese em texto do dossiê do livro via Ollama.

Fase 4 do roadmap de grafo: o diálogo do dossiê abre instantâneo com os dados
estruturados; este worker entrega o parágrafo de síntese em background. Se o
Ollama estiver indisponível ou a resposta vier vazia, o chamador mantém o
dossiê sem síntese — ADR-005.
"""

import json
import logging
import urllib.request

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class DossierSynthesisWorker(QThread):
    generated = pyqtSignal(str)  # parágrafo da síntese
    failed = pyqtSignal(str)     # motivo (chamador degrada graciosamente)

    def __init__(self, prompt: str, ollama_url: str = "http://localhost:11434",
                 model: str | None = None, timeout_s: int = 120, parent=None):
        super().__init__(parent)
        self._prompt = prompt
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if not (self._prompt or "").strip():
                self.failed.emit("prompt vazio")
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
                "messages": [{"role": "user", "content": self._prompt}],
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                # gemma4 é modelo de raciocínio: consome tokens "pensando" antes
                # do content — teto folgado evita resposta vazia. Nunca think=False.
                "options": {"num_predict": 4096, "temperature": 0.2},
            }
            req = urllib.request.Request(
                f"{self._ollama_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
                data = json.loads(resp.read())
            content = ((data.get("message", {}) or {}).get("content") or "").strip()

            if self._cancelled:
                return
            if not content:
                self.failed.emit("resposta vazia do modelo")
                return
            self.generated.emit(content)
        except Exception as exc:  # ADR-005: falha vira fallback, nunca crash
            logger.warning("DossierSynthesisWorker falhou: %s", exc)
            if not self._cancelled:
                self.failed.emit(str(exc))
