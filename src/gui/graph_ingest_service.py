"""Serviço de ingestão do grafo de conceitos (Fase 2) — camada GUI.

QObject que orquestra o GraphWorker (QThread): fila com prioridade, um worker
por vez (skip-if-busy, padrão do ProactiveReaderService), recompute de arestas
debounced e lote ocioso para livros ainda não tratados. A lógica pura vive em
``src/core/graph/**`` (ADR-006).

Prioridades: página do livro ativo > anotação nova > varredura de anotações
do livro (1× por sessão) > arestas > lote ocioso.
"""

import logging
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.gui.workers.graph_worker import GraphWorker

logger = logging.getLogger(__name__)

_PRIORITY = {"page": 0, "annotation": 1, "annotations_sweep": 2,
             "edges": 3, "idle_batch": 4}
_MAX_PENDING_PAGES = 3


class GraphIngestService(QObject):
    graph_updated = pyqtSignal(int)  # book_id com arestas/conceitos atualizados

    def __init__(self, db, rag_engine=None, config=None, parent=None):
        super().__init__(parent)
        self._db = db
        self._rag_engine = rag_engine
        self._config = config
        self._queue: list[dict] = []
        self._worker: GraphWorker | None = None
        self._dirty_books: set[int] = set()
        self._swept_books: set[int] = set()      # sweep de anotações 1× por sessão
        self._indexed_cache: set[int] = set()    # só cacheia positivos
        self._active_book_id: int | None = None
        self._last_activity = time.monotonic()
        self._idle_exhausted = False             # nada mais a processar em ocioso

        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._on_idle_tick)
        self._idle_timer.start(int(self._cfg("idle_interval_s", 60)) * 1000)

    # ── Config helpers ────────────────────────────────────────────────

    def _cfg(self, key: str, default):
        if self._config is None:
            return default
        return self._config.get(f"graph.{key}", default)

    def _enabled(self) -> bool:
        return bool(self._cfg("enabled", True)) and self._db is not None

    def _cfg_snapshot(self) -> dict:
        ollama_url = "http://localhost:11434"
        if self._config is not None:
            ollama_url = self._config.get("rag.ollama_url", ollama_url)
        return {
            "ollama_url": ollama_url,
            "use_llm_pages": self._cfg("use_llm_pages", False),
            "use_llm_annotations": self._cfg("use_llm_annotations", True),
            "use_llm_idle": self._cfg("use_llm_idle", False),
            "llm_model": self._cfg("llm_model", None),
            "llm_timeout_s": self._cfg("llm_timeout_s", 20),
            "max_concepts_per_page": self._cfg("max_concepts_per_page", 8),
            "max_concepts_per_annotation": self._cfg("max_concepts_per_annotation", 5),
            "idle_batch_pages": self._cfg("idle_batch_pages", 25),
            "edge_min_shared": self._cfg("edge_min_shared", 2),
            "edge_df_cap": self._cfg("edge_df_cap", 0.5),
        }

    # ── Slots (sinais da GUI) ─────────────────────────────────────────

    def on_page_context(self, book_id: int, title: str, page: int, page_text: str):
        """Virada de página do livro ativo (sinal reading_context_updated)."""
        self._last_activity = time.monotonic()
        self._active_book_id = book_id
        self._idle_exhausted = False
        if not self._enabled() or book_id <= 0 or page <= 0:
            return
        if not self._book_indexed(book_id):
            return
        try:
            from src.core.graph.graph_store import GraphStore
            if GraphStore(self._db).is_ingested(book_id, f"page:{page}"):
                return  # lookup por PK — barato o suficiente para o slot
        except Exception as exc:
            logger.debug("Grafo: dedup no slot falhou (segue): %s", exc)
        self._enqueue({"kind": "page", "book_id": book_id, "page": page,
                       "fallback_text": page_text or ""})
        if book_id not in self._swept_books:
            self._swept_books.add(book_id)
            self._enqueue({"kind": "annotations_sweep", "book_id": book_id})
        self._pump()

    def on_annotation_saved(self, book_id: int, annotation_id: int,
                            page: int, text: str):
        """Anotação recém-criada pelo usuário."""
        self._last_activity = time.monotonic()
        self._idle_exhausted = False
        if not self._enabled() or book_id <= 0 or not annotation_id:
            return
        self._enqueue({"kind": "annotation", "book_id": book_id,
                       "annotation_id": annotation_id, "page": page or None,
                       "text": text or ""})
        self._pump()

    # ── Fila / worker ─────────────────────────────────────────────────

    @staticmethod
    def _task_key(task: dict) -> tuple:
        kind = task["kind"]
        if kind == "page":
            return (kind, task["book_id"], task["page"])
        if kind == "annotation":
            return (kind, task["book_id"], task["annotation_id"])
        if kind in ("annotations_sweep",):
            return (kind, task["book_id"])
        if kind == "edges":
            return (kind, tuple(task.get("book_ids", [])))
        return (kind,)

    def _enqueue(self, task: dict):
        key = self._task_key(task)
        if any(self._task_key(t) == key for t in self._queue):
            return
        self._queue.append(task)
        self._queue.sort(key=lambda t: _PRIORITY.get(t["kind"], 9))  # estável: FIFO na prioridade
        # Teto de page-tasks: leitura rápida não acumula backlog (o idle recupera).
        pages = [t for t in self._queue if t["kind"] == "page"]
        while len(pages) > _MAX_PENDING_PAGES:
            oldest = pages.pop(0)
            self._queue.remove(oldest)

    def _pump(self):
        if self._worker is not None and self._worker.isRunning():
            return
        if not self._queue:
            if self._dirty_books:
                books = sorted(self._dirty_books)
                self._dirty_books.clear()
                self._enqueue({"kind": "edges", "book_ids": books})
            else:
                return
        task = self._queue.pop(0)
        self._worker = GraphWorker(task, self._db, self._rag_engine,
                                   self._cfg_snapshot(), parent=self)
        self._worker.finished_task.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_worker_finished(self, report: dict):
        kind = report.get("kind", "")
        book_id = report.get("book_id")
        if kind in ("page", "annotation") and book_id and report.get("mentions", 0) > 0:
            self._dirty_books.add(book_id)
        elif kind == "annotations_sweep" and book_id and report.get("annotations", 0) > 0:
            self._dirty_books.add(book_id)
        elif kind == "idle_batch":
            if book_id and (report.get("pages", 0) or report.get("annotations", 0)):
                self._dirty_books.add(book_id)
            if report.get("book_id") is None and report.get("exhausted"):
                self._idle_exhausted = True  # para de varrer até nova atividade
        elif kind == "edges":
            for bid in report.get("book_ids", []):
                self.graph_updated.emit(bid)
        self._worker = None
        self._pump()

    def _on_worker_error(self, msg: str):
        logger.warning("Grafo: worker falhou (ignorado): %s", msg)
        self._worker = None
        self._pump()

    # ── Ocioso ────────────────────────────────────────────────────────

    def _on_idle_tick(self):
        if not self._enabled() or not self._cfg("idle_enabled", True):
            return
        if self._idle_exhausted:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if self._queue:
            self._pump()
            return
        inactivity = time.monotonic() - self._last_activity
        if inactivity < float(self._cfg("idle_min_inactivity_s", 90)):
            return
        if self._dirty_books:
            self._pump()  # drena as arestas pendentes primeiro
            return
        self._enqueue({"kind": "idle_batch", "active_book_id": self._active_book_id})
        self._pump()

    # ── Auxiliares ────────────────────────────────────────────────────

    def _book_indexed(self, book_id: int) -> bool:
        """Página só entra no grafo após a indexação RAG (decisão da fase)."""
        if book_id in self._indexed_cache:
            return True
        try:
            status = self._db.get_indexing_status(book_id)
        except Exception:
            return False
        if status and status.get("status") == "indexed_ok":
            self._indexed_cache.add(book_id)  # só positivo: re-checa enquanto não indexa
            return True
        return False

    def shutdown(self):
        """Cancelamento cooperativo no fechamento do app."""
        self._idle_timer.stop()
        self._queue.clear()
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            try:
                self._worker.finished_task.disconnect(self._on_worker_finished)
            except (TypeError, RuntimeError):
                pass
            self._worker.wait(2000)
        self._worker = None
