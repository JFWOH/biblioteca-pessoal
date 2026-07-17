"""Worker de auto-indexação: indexa UM livro em background (QThread).

Encapsula o DocumentIndexerService (core) fora da thread da GUI. O serviço
core já gerencia o ciclo de status (pending → indexed_ok | failed) e a
degradação graciosa (Ollama fora → status failed, sem crash).
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class AutoIndexWorker(QThread):
    finished_task = pyqtSignal(dict)  # {"book_id", "chunks", "status"}
    error = pyqtSignal(str)

    def __init__(self, book_id: int, db, rag_engine, fts_only: bool = False, parent=None):
        super().__init__(parent)
        self._book_id = book_id
        self._db = db
        self._rag_engine = rag_engine
        # fts_only=True: só faz backfill do FTS de conteúdo (Tarefa 5.1) — extrai
        # o texto e alimenta o índice full-text, SEM embeddings/Chroma. Usado
        # para livros antigos já indexados no RAG mas sem busca por conteúdo.
        self._fts_only = fts_only
        self._indexer = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._indexer is not None:
            try:
                self._indexer.cancel()
            except Exception:
                pass

    def run(self):
        try:
            from src.core.document_indexer_service import DocumentIndexerService

            self._indexer = DocumentIndexerService(self._db, self._rag_engine)
            if self._fts_only:
                pages = self._indexer.backfill_content_fts(self._book_id)
                if not self._cancelled:
                    self.finished_task.emit({
                        "book_id": self._book_id,
                        "chunks": int(pages or 0),
                        "status": "fts_indexed",
                    })
                return
            chunks = self._indexer.index_book(self._book_id)
            status_row = self._db.get_indexing_status(self._book_id)
            status = (status_row or {}).get("status", "unknown")
            if not self._cancelled:
                self.finished_task.emit({
                    "book_id": self._book_id,
                    "chunks": int(chunks or 0),
                    "status": status,
                })
        except Exception as exc:  # ADR-005: falha vira aviso, nunca crash
            logger.warning("AutoIndexWorker falhou (book_id=%s): %s",
                           self._book_id, exc)
            if not self._cancelled:
                self.error.emit(str(exc))
