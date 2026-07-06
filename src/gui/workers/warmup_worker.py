"""Worker que pré-aquece os modelos do Ollama no startup.

Revisão de engenharia 2026-07-05 §1.1: sem warmup, a PRIMEIRA ação de IA da
sessão paga o carregamento do modelo na VRAM (segundos) antes do raciocínio
começar. Este worker dispara em background, alguns segundos após a janela
abrir, um load do LLM (/api/generate sem prompt) e do modelo de embeddings
(/api/embed com input mínimo) — ambos com keep_alive para ficarem residentes.

Totalmente gracioso (ADR-005): Ollama fora do ar ou modelo ausente viram um
log debug, nunca erro visível — o warmup é uma otimização, não um requisito.
"""

import json
import logging
import urllib.request

from PyQt6.QtCore import QThread

from src.core.ollama_defaults import OLLAMA_KEEP_ALIVE

logger = logging.getLogger(__name__)


class WarmupWorker(QThread):
    def __init__(self, ollama_url: str = "http://localhost:11434",
                 llm_model: str | None = None, embed_model: str | None = None,
                 timeout_s: int = 60, parent=None):
        super().__init__(parent)
        self._ollama_url = ollama_url.rstrip("/")
        self._llm_model = llm_model
        self._embed_model = embed_model
        self._timeout_s = timeout_s

    def _post(self, endpoint: str, payload: dict) -> None:
        req = urllib.request.Request(
            f"{self._ollama_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self._timeout_s) as resp:
            resp.read()

    def run(self):
        # /api/generate sem prompt só carrega o modelo (não gera nada).
        if self._llm_model:
            try:
                self._post("/api/generate", {
                    "model": self._llm_model, "keep_alive": OLLAMA_KEEP_ALIVE})
                logger.info("Warmup do LLM '%s' concluído.", self._llm_model)
            except Exception as exc:
                logger.debug("Warmup do LLM ignorado: %s", exc)
        if self._embed_model:
            try:
                self._post("/api/embed", {
                    "model": self._embed_model, "input": "warmup",
                    "keep_alive": OLLAMA_KEEP_ALIVE})
                logger.info("Warmup dos embeddings '%s' concluído.", self._embed_model)
            except Exception as exc:
                logger.debug("Warmup dos embeddings ignorado: %s", exc)
