"""Serviço de auto-indexação RAG em ocioso (camada GUI).

Detecta livros sem indexação concluída (`indexed_ok`) e os indexa em
background, UM por vez, apenas quando o app está ocioso — nunca no startup a
frio (indexação usa embeddings/GPU). Sinergia direta com o grafo de conceitos:
o idle do grafo só processa livros indexados, então cada livro auto-indexado
destrava o grafo para ele.

Gates (todos precisam passar):
- ``auto_index.enabled`` na config;
- RAGEngine disponível e SEM ``needs_reindex()`` pendente (coleção bloqueada
  por troca de modelo de embedding é assunto do reindex manual);
- nenhuma operação RAG manual em andamento (``busy_check``);
- nenhum worker próprio rodando;
- ≥ ``idle_min_inactivity_s`` sem atividade de leitura.

Livros que falham são marcados como tentados e não entram em loop de retry na
mesma sessão.
"""

import logging
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.gui.workers.auto_index_worker import AutoIndexWorker

logger = logging.getLogger(__name__)


class AutoIndexService(QObject):
    indexing_started = pyqtSignal(int, str)        # book_id, título
    indexing_finished = pyqtSignal(int, str, str)  # book_id, título, status final

    def __init__(self, db, rag_engine=None, config=None, busy_check=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._rag_engine = rag_engine
        self._config = config
        self._busy_check = busy_check  # ex.: RAGWorker manual em andamento
        self._worker: AutoIndexWorker | None = None
        self._attempted: set[int] = set()  # sem loop de retry na sessão
        self._current: tuple[int, str] | None = None  # (book_id, título) em curso
        self._last_activity = time.monotonic()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(int(self._cfg("idle_interval_s", 120)) * 1000)

    # ── Config / gates ────────────────────────────────────────────────

    def _cfg(self, key: str, default):
        if self._config is None:
            return default
        return self._config.get(f"auto_index.{key}", default)

    def on_activity(self, *args):
        """Marca atividade de leitura (conectado a reading_context_updated)."""
        self._last_activity = time.monotonic()

    # ── Ciclo ─────────────────────────────────────────────────────────

    def _on_tick(self):
        if not bool(self._cfg("enabled", True)):
            return
        if self._db is None or self._rag_engine is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if self._busy_check is not None:
            try:
                if self._busy_check():
                    return
            except Exception:
                return
        inactivity = time.monotonic() - self._last_activity
        if inactivity < float(self._cfg("idle_min_inactivity_s", 120)):
            return
        try:
            # Coleção bloqueada por troca de modelo → reindex manual resolve.
            if self._rag_engine.needs_reindex():
                logger.debug("Auto-index: needs_reindex pendente; aguardando reindex manual.")
                return
        except Exception:
            return

        book = self._pick_candidate()
        if book is None:
            return
        book_id, title = book["id"], book.get("title", "")
        self._attempted.add(book_id)
        self._current = (book_id, title)
        self._worker = AutoIndexWorker(book_id, self._db, self._rag_engine, parent=self)
        self._worker.finished_task.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
        logger.info("Auto-index: indexando '%s' (book_id=%s) em background", title, book_id)
        self.indexing_started.emit(book_id, title)

    def _pick_candidate(self) -> dict | None:
        try:
            candidates = self._db.get_unindexed_books()
        except Exception as exc:
            logger.debug("Auto-index: falha ao listar candidatos: %s", exc)
            return None
        for book in candidates:
            if book["id"] not in self._attempted:
                return book
        return None

    def _on_worker_finished(self, report: dict):
        self._worker = None
        book_id, title = self._current or (report.get("book_id"), "")
        self._current = None
        status = report.get("status", "unknown")
        if status == "indexed_ok":
            logger.info("Auto-index: '%s' indexado (%s chunks)", title, report.get("chunks"))
        else:
            logger.warning("Auto-index: '%s' terminou com status '%s'", title, status)
        self.indexing_finished.emit(book_id or 0, title, status)

    def _on_worker_error(self, msg: str):
        self._worker = None
        book_id, title = self._current or (0, "")
        self._current = None
        logger.warning("Auto-index: falha ao indexar '%s' (ignorado): %s", title, msg)
        self.indexing_finished.emit(book_id, title, "failed")

    def shutdown(self):
        """Cancelamento cooperativo no fechamento do app."""
        self._timer.stop()
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            try:
                self._worker.finished_task.disconnect(self._on_worker_finished)
            except (TypeError, RuntimeError):
                pass
            self._worker.wait(5000)  # indexação é pesada; espera um pouco mais
        self._worker = None
