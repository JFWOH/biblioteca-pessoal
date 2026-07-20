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
        # Backfill do FTS de conteúdo (Tarefa 5.1): livros já indexados no RAG
        # mas sem busca por conteúdo. Conjunto próprio para não misturar com o
        # retry-guard da indexação RAG e evitar re-tentar livros sem texto.
        self._fts_attempted: set[int] = set()
        self._current: tuple[int, str] | None = None  # (book_id, título) em curso
        self._fts_only_current = False  # o trabalho em curso é backfill de FTS?
        self._last_activity = time.monotonic()
        # Carência de startup (achado B0): momento de criação do serviço (≈ o
        # launch do app). A indexação não dispara enquanto (now - _created_at)
        # < startup_grace_s — protege a sessão interativa inicial e o TTS da
        # contenção de CPU/IO da indexação. Ver _on_tick.
        self._created_at = time.monotonic()

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
        if self._busy_check is not None:
            try:
                busy = bool(self._busy_check())
            except Exception:
                return
            if busy:
                # RAG manual em andamento OU narração TTS ativa (rodada 2 de
                # ajustes de TTS — cf. MainWindow._is_narration_active).
                # Conta como atividade e mantém o relógio de ociosidade
                # fresco: o ReaderView não expõe hoje um sinal de início/fim
                # de narração fora de si mesmo (só o worker de áudio privado,
                # recriado a cada narração), então sem isto uma narração
                # longa deixaria ``_last_activity`` obsoleto e a
                # auto-indexação retomaria IMEDIATAMENTE ao fim da narração
                # em vez de aguardar um novo período de folga
                # (idle_min_inactivity_s) — voltando a competir por CPU bem
                # na cauda do áudio.
                self._last_activity = time.monotonic()
                return
        # Carência de startup (achado B0): não INICIAR indexação nos primeiros N
        # s após o launch, mesmo sem leitura ativa (navegar na grade não conta
        # como atividade). Vem DEPOIS do busy_check para não atrapalhar o
        # refresh do relógio de ociosidade durante uma narração. Evita que o
        # indexador comece ~2 min após abrir o app e compita por CPU/IO com a
        # sessão interativa e o TTS (TTFB do Kokoro estourando o SLO).
        if (time.monotonic() - self._created_at) < float(
                self._cfg("startup_grace_s", 300)):
            return
        if self._worker is not None and self._worker.isRunning():
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

        # Prioridade: indexar livros sem RAG; só depois fazer backfill do FTS
        # de conteúdo (mais barato) dos que já têm RAG mas não têm busca por
        # conteúdo. Um trabalho por tick, sempre 1 livro por vez.
        book = self._pick_candidate()
        fts_only = False
        if book is None:
            book = self._pick_fts_backfill_candidate()
            fts_only = True
        if book is None:
            return
        book_id, title = book["id"], book.get("title", "")
        if fts_only:
            self._fts_attempted.add(book_id)
        else:
            self._attempted.add(book_id)
        self._current = (book_id, title)
        self._fts_only_current = fts_only
        self._worker = AutoIndexWorker(
            book_id, self._db, self._rag_engine, fts_only=fts_only, parent=self)
        self._worker.finished_task.connect(self._on_worker_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
        if fts_only:
            logger.info(
                "Auto-index: backfill FTS de conteúdo de '%s' (book_id=%s)", title, book_id)
        else:
            logger.info(
                "Auto-index: indexando '%s' (book_id=%s) em background", title, book_id)
        self.indexing_started.emit(book_id, title)

    def cancel_active(self) -> None:
        """Cancela IMEDIATAMENTE a indexação em ocioso em andamento, se houver.

        Gatilho (rodada 3 de ajustes de TTS): início real da narração TTS
        (ReaderView.narration_started, via MainWindow). Complementa — não
        substitui — o gating por ``busy_check``: aquele só impede que um NOVO
        job comece durante a narração; este interrompe um job JÁ em curso,
        porque a contenção de CPU/GPU dos embeddings elevava o TTFB do Kokoro
        (24,92s medidos com 900 chunks concorrentes) e disparava um fallback
        indevido para o Piper.

        Cancelamento COOPERATIVO e NÃO-bloqueante: apenas sinaliza o worker
        (que checa o flag nos loops de OCR — por página — e de embeddings —
        entre lotes de ~50 chunks) e retorna. Roda na thread da GUI, então
        NUNCA faz ``wait()`` aqui. Cobre tanto a indexação RAG completa quanto
        o backfill de FTS (``fts_only``): ambos usam o mesmo
        ``AutoIndexWorker.cancel()``. O job re-entra naturalmente pelo
        agendador de ocioso quando a narração terminar — o gating por narração
        (rodada 2) impede o reinício enquanto ela dura.

        Idempotente/seguro: no-op quando não há worker ativo.
        """
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        title = self._current[1] if self._current else "?"
        logger.info(
            "Auto-index: narração iniciou — cancelando indexação ativa de '%s'.",
            title)
        try:
            worker.cancel()
        except Exception as exc:  # ADR-005: cancelar nunca derruba o app
            logger.debug("Auto-index: falha ao cancelar worker ativo: %s", exc)

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

    def _pick_fts_backfill_candidate(self) -> dict | None:
        """Livro já indexado no RAG (indexed_ok) mas ainda SEM FTS de conteúdo.

        ``_fts_attempted`` evita loop em livros que não geram nenhuma página
        (ex.: PDF só-imagem sem OCR) — que ficariam para sempre "sem FTS".
        """
        try:
            candidates = self._db.get_books_by_indexing_status("indexed_ok")
        except Exception as exc:
            logger.debug("Auto-index: falha ao listar backfill FTS: %s", exc)
            return None
        for book in candidates:
            bid = book["id"]
            if bid in self._fts_attempted:
                continue
            try:
                if not self._db.fts_is_indexed(bid):
                    return book
            except Exception:
                return None
        return None

    def _on_worker_finished(self, report: dict):
        self._worker = None
        book_id, title = self._current or (report.get("book_id"), "")
        self._current = None
        status = report.get("status", "unknown")
        self._fts_only_current = False
        if status == "indexed_ok":
            logger.info("Auto-index: '%s' indexado (%s chunks)", title, report.get("chunks"))
        elif status == "fts_indexed":
            logger.info(
                "Auto-index: backfill FTS de '%s' concluído (%s páginas)",
                title, report.get("chunks"))
        else:
            logger.warning("Auto-index: '%s' terminou com status '%s'", title, status)
        self.indexing_finished.emit(book_id or 0, title, status)

    def _on_worker_error(self, msg: str):
        self._worker = None
        book_id, title = self._current or (0, "")
        self._current = None
        self._fts_only_current = False
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
