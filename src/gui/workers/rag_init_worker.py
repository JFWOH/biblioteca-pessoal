"""Worker de inicialização/sonda do motor RAG (rodada E1 — startup adiado).

Construir o RAGEngine importa chromadb e abre o client persistente — ~27 s
em disco frio (medições no plano de empacotamento, docs/agents/
packaging_plan_2026-07.md). Feito no ``__init__`` da MainWindow, congelava a
janela antes de ela aparecer. Este worker (mesmo padrão do TTSInitWorker,
achado B0) faz o trabalho pesado fora da GUI thread e também sonda o Ollama
(HTTP bloqueante) e o índice — a thread da UI nunca espera disco nem rede.

Reutilizado nas re-checagens (abrir o painel do assistente): recebendo um
``engine`` já existente, pula a construção e só re-sonda o estado.
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class RagInitWorker(QThread):
    """Constrói (se preciso) o RAGEngine e sonda Ollama/índice em background."""

    # engine (RAGEngine | None), ollama disponível, modelos instalados,
    # chunks indexados. Engine None = chroma indisponível (fluxo gracioso).
    ready = pyqtSignal(object, bool, list, int)

    def __init__(self, db_path, chroma_path, ollama_url, embed_model,
                 llm_model, engine=None, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._chroma_path = chroma_path
        self._ollama_url = ollama_url
        self._embed_model = embed_model
        self._llm_model = llm_model
        self._engine = engine

    def run(self) -> None:
        engine = self._engine
        try:
            if engine is None:
                from src.core.rag_engine import RAGEngine
                engine = RAGEngine(
                    db_path=self._db_path,
                    chroma_path=self._chroma_path,
                    ollama_url=self._ollama_url,
                    embed_model=self._embed_model,
                    llm_model=self._llm_model,
                )
        except Exception:
            logger.exception("Falha ao inicializar o motor RAG (seguindo sem IA)")
            self.ready.emit(None, False, [], 0)
            return

        available = False
        models: list = []
        try:
            available = bool(engine.is_ollama_available())
            if available:
                models = engine.list_local_models()
        except Exception as exc:  # ADR-005: sonda nunca derruba o startup
            logger.debug("Sonda do Ollama falhou: %s", exc)
            available = False

        try:
            indexed_count = int(engine.get_indexed_count())
        except Exception:
            indexed_count = 0

        self.ready.emit(engine, available, models, indexed_count)
