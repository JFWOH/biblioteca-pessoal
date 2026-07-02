"""Testes da auto-indexação em ocioso (item 8 do backlog UX)."""
import time

import pytest
from unittest.mock import MagicMock, patch

from src.core.database import LibraryDB
from src.gui.auto_index_service import AutoIndexService


class FakeConfig:
    def __init__(self, overrides=None):
        self._data = overrides or {}

    def get(self, key, default=None):
        return self._data.get(key, default)


class FakeEngine:
    def __init__(self, needs_reindex=False):
        self._needs = needs_reindex

    def needs_reindex(self):
        return self._needs


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db, title="Livro", path="/tmp/x.pdf", status=None) -> int:
    bid = db.add_book(title=title, file_path=path, file_format="pdf")
    if status:
        db.set_indexing_status(bid, status)
    return bid


def _idle_svc(db, engine=None, config=None, busy_check=None) -> AutoIndexService:
    svc = AutoIndexService(db=db, rag_engine=engine or FakeEngine(),
                           config=config, busy_check=busy_check)
    svc._last_activity = time.monotonic() - 9999  # ocioso há muito tempo
    return svc


# ── get_unindexed_books ───────────────────────────────────────────────

def test_get_unindexed_books(db):
    b1 = _book(db, "Sem estado", "/tmp/a.pdf")
    b2 = _book(db, "Falhou", "/tmp/b.pdf", status="failed")
    b3 = _book(db, "Pendente", "/tmp/c.pdf", status="pending")
    _book(db, "Indexado", "/tmp/d.pdf", status="indexed_ok")
    ids = {b["id"] for b in db.get_unindexed_books()}
    assert ids == {b1, b2, b3}


# ── Gates do serviço ──────────────────────────────────────────────────

def test_disabled_by_config(qtbot, db):
    _book(db)
    svc = _idle_svc(db, config=FakeConfig({"auto_index.enabled": False}))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


def test_requires_inactivity(qtbot, db):
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine())  # atividade recente
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


def test_busy_check_blocks(qtbot, db):
    _book(db)
    svc = _idle_svc(db, busy_check=lambda: True)  # RAG manual em andamento
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


def test_needs_reindex_blocks(qtbot, db):
    _book(db)
    svc = _idle_svc(db, engine=FakeEngine(needs_reindex=True))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


def test_no_engine_blocks(qtbot, db):
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=None)
    svc._last_activity = time.monotonic() - 9999
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


# ── Fluxo feliz + retry guard ─────────────────────────────────────────

def test_picks_unindexed_book_and_emits(qtbot, db):
    bid = _book(db, "Não indexado")
    _book(db, "Já indexado", "/tmp/ok.pdf", status="indexed_ok")
    svc = _idle_svc(db)
    started = []
    svc.indexing_started.connect(lambda b, t: started.append((b, t)))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc._on_tick()
        MockWorker.assert_called_once()
        assert MockWorker.call_args[0][0] == bid  # 1º arg = book_id
        assert started == [(bid, "Não indexado")]
    svc.shutdown()


def test_one_worker_at_a_time(qtbot, db):
    _book(db, "A", "/tmp/a.pdf")
    _book(db, "B", "/tmp/b.pdf")
    svc = _idle_svc(db)
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc._on_tick()
        svc._on_tick()  # worker rodando → não cria outro
        assert MockWorker.call_count == 1
    svc.shutdown()


def test_failed_book_not_retried_in_session(qtbot, db):
    b1 = _book(db, "Problemático", "/tmp/a.pdf")
    b2 = _book(db, "Próximo", "/tmp/b.pdf")
    svc = _idle_svc(db)
    finished = []
    svc.indexing_finished.connect(lambda b, t, s: finished.append((b, s)))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        svc._on_tick()
        assert MockWorker.call_args[0][0] == b1
        svc._on_worker_error("arquivo corrompido")
        assert finished == [(b1, "failed")]
        # Próximo tick: pula o problemático (tentado) e vai ao seguinte
        svc._on_tick()
        assert MockWorker.call_args[0][0] == b2
        # Todos tentados → nada mais a fazer
        svc._on_worker_error("outro erro")
        svc._on_tick()
        assert MockWorker.call_count == 2
    svc.shutdown()


def test_finished_ok_emits_status(qtbot, db):
    bid = _book(db, "Livro X")
    svc = _idle_svc(db)
    finished = []
    svc.indexing_finished.connect(lambda b, t, s: finished.append((b, t, s)))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        svc._on_tick()
        svc._on_worker_finished({"book_id": bid, "chunks": 42, "status": "indexed_ok"})
    assert finished == [(bid, "Livro X", "indexed_ok")]
    svc.shutdown()


def test_on_activity_defers_idle(qtbot, db):
    _book(db)
    svc = _idle_svc(db)
    svc.on_activity(1, "T", 5, "texto")  # leitura ativa agora
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


# ── Worker ────────────────────────────────────────────────────────────

def test_worker_reports_final_status(qtbot, db):
    from src.gui.workers.auto_index_worker import AutoIndexWorker

    bid = _book(db, "Livro")
    fake_indexer = MagicMock()
    fake_indexer.index_book.return_value = 7
    db.set_indexing_status(bid, "indexed_ok", 7)

    with patch("src.core.document_indexer_service.DocumentIndexerService",
               return_value=fake_indexer):
        w = AutoIndexWorker(bid, db, FakeEngine())
        got = []
        w.finished_task.connect(got.append)
        w.run()  # síncrono no teste
    assert got == [{"book_id": bid, "chunks": 7, "status": "indexed_ok"}]
    fake_indexer.index_book.assert_called_once_with(bid)


def test_worker_error_emits(qtbot, db):
    from src.gui.workers.auto_index_worker import AutoIndexWorker

    bid = _book(db)
    fake_indexer = MagicMock()
    fake_indexer.index_book.side_effect = RuntimeError("sem GPU")
    with patch("src.core.document_indexer_service.DocumentIndexerService",
               return_value=fake_indexer):
        w = AutoIndexWorker(bid, db, FakeEngine())
        fails = []
        w.error.connect(fails.append)
        w.run()
    assert fails == ["sem GPU"]
