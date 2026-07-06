"""Worker do grafo de conceitos (Fase 2) — executa tasks fora da thread da GUI.

Padrão do ProactiveWorker: QThread com cancelamento cooperativo; toda a lógica
pesada vive no core puro (src/core/graph/**, ADR-006). O SQLite é seguro aqui
porque o LibraryDB usa conexão thread-local + write lock; o Chroma é lido
apenas (read-only).
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class GraphWorker(QThread):
    """Executa UMA task do grafo e termina (o serviço agenda a próxima).

    Task kinds (dict ``task``):
    - ``page``: {kind, book_id, page, fallback_text}
    - ``annotation``: {kind, book_id, annotation_id, page, text}
    - ``annotations_sweep``: {kind, book_id}
    - ``idle_batch``: {kind, active_book_id}
    - ``edges``: {kind, book_ids: list[int]}
    """

    finished_task = pyqtSignal(dict)   # relatório: {"kind", "book_id", ...}
    error = pyqtSignal(str)

    def __init__(self, task: dict, db, rag_engine, cfg: dict, parent=None):
        super().__init__(parent)
        self._task = task
        self._db = db
        self._rag_engine = rag_engine
        self._cfg = cfg  # snapshot do bloco "graph" da config
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    # ── Execução ──────────────────────────────────────────────────────

    def run(self):
        try:
            report = self._execute()
            if not self._cancelled:
                self.finished_task.emit(report)
        except Exception as exc:  # ADR-005: nunca derrubar o app
            logger.warning("GraphWorker falhou (%s): %s",
                           self._task.get("kind"), exc)
            if not self._cancelled:
                self.error.emit(str(exc))

    def _execute(self) -> dict:
        from src.core.graph.graph_store import GraphStore
        from src.core.graph.concept_extractor import ConceptExtractor, resolve_llm_model
        from src.core.graph import ingest

        task = self._task
        kind = task["kind"]
        store = GraphStore(self._db)
        collection = getattr(self._rag_engine, "_collection", None)

        llm_model = None
        needs_llm = (
            (kind in ("annotation", "annotations_sweep") and self._cfg.get("use_llm_annotations", True))
            or (kind == "page" and self._cfg.get("use_llm_pages", False))
            or (kind == "idle_batch" and self._cfg.get("use_llm_idle", False))
        )
        if needs_llm:
            # Resolução na thread do worker (rede) — nunca na thread da GUI.
            llm_model = resolve_llm_model(
                self._cfg.get("ollama_url", "http://localhost:11434"),
                preferred=self._cfg.get("llm_model"))
        extractor = ConceptExtractor(
            ollama_url=self._cfg.get("ollama_url", "http://localhost:11434"),
            llm_model=llm_model,
            llm_timeout_s=int(self._cfg.get("llm_timeout_s", 20)),
        )
        use_llm = needs_llm and llm_model is not None

        if kind == "page":
            book_id, page = task["book_id"], task["page"]
            text = ""
            if collection is not None:
                try:
                    pages = ingest.get_book_pages_from_chroma(collection, book_id)
                    text = pages.get(page, "")
                except Exception as exc:
                    logger.debug("Chroma indisponível p/ page-task: %s", exc)
            if not text:
                text = task.get("fallback_text", "")
            mentions = ingest.ingest_page(
                store, extractor, book_id, page, text, use_llm=use_llm,
                max_concepts=int(self._cfg.get("max_concepts_per_page", 8)))
            return {"kind": kind, "book_id": book_id, "page": page,
                    "mentions": mentions}

        if kind == "annotation":
            book_id = task["book_id"]
            mentions = ingest.ingest_annotation(
                store, extractor, book_id, task["annotation_id"],
                task.get("text", ""), page=task.get("page"), use_llm=use_llm,
                max_concepts=int(self._cfg.get("max_concepts_per_annotation", 5)))
            return {"kind": kind, "book_id": book_id, "mentions": mentions}

        if kind == "annotations_sweep":
            book_id = task["book_id"]
            processed = ingest.sweep_annotations(
                self._db, store, extractor, book_id, use_llm=use_llm,
                max_concepts=int(self._cfg.get("max_concepts_per_annotation", 5)))
            return {"kind": kind, "book_id": book_id, "annotations": processed}

        if kind == "idle_batch":
            if collection is None:
                return {"kind": kind, "book_id": None, "pages": 0,
                        "annotations": 0, "exhausted": True}
            report = ingest.process_idle_batch(
                self._db, store, extractor, collection,
                batch_pages=int(self._cfg.get("idle_batch_pages", 25)),
                use_llm=use_llm,
                active_book_id=task.get("active_book_id"),
                max_concepts=int(self._cfg.get("max_concepts_per_page", 8)),
                should_cancel=lambda: self._cancelled)
            report["kind"] = kind
            return report

        if kind == "edges":
            written = 0
            for book_id in task.get("book_ids", []):
                if self._cancelled:
                    break
                written += store.recompute_book_edges(
                    book_id,
                    min_shared=int(self._cfg.get("edge_min_shared", 2)),
                    df_cap_ratio=float(self._cfg.get("edge_df_cap", 0.5)))
            return {"kind": kind, "book_ids": task.get("book_ids", []),
                    "edges": written}

        raise ValueError(f"Task desconhecida: {kind}")
