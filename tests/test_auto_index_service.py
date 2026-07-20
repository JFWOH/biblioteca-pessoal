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
    svc._created_at = time.monotonic() - 9999      # já passou a carência de startup (B0)
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


def test_startup_grace_blocks_initial_indexing(qtbot, db):
    """Achado B0: nos primeiros N s após o launch a indexação NÃO dispara,
    mesmo com o app aparentemente ocioso (sem leitura ativa). Sem isso, ~2 min
    após abrir o app o indexador competia por CPU/IO com a sessão e o TTS."""
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(),
                           config=FakeConfig({"auto_index.startup_grace_s": 300}))
    svc._last_activity = time.monotonic() - 9999  # ocioso, mas...
    # _created_at é "agora" (recém-criado) → dentro da carência de 300 s.
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()  # carência bloqueia
    # Passada a carência, com o app ocioso, volta a indexar.
    svc._created_at = time.monotonic() - 9999
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc._on_tick()
        MockWorker.assert_called_once()
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


# ── Kick pós-importação (débito 5.1, rodada B4) ───────────────────────

def test_kick_bypasses_grace_and_inactivity_fts_only(qtbot, db):
    """Importação explícita: tick imediato SÓ-FTS (extração leve, sem
    embeddings), dispensando carência de startup e ociosidade UMA vez —
    o livro novo entra na busca de conteúdo sem esperar ocioso."""
    bid = _book(db)  # recém-importado: sem FTS e sem RAG
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(),
                           config=FakeConfig({"auto_index.startup_grace_s": 300}))
    # atividade AGORA e dentro da carência — os dois gates que o kick dispensa
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._kick_once = True
        svc._on_tick()
        MockWorker.assert_called_once()
        assert MockWorker.call_args.args[0] == bid
        assert MockWorker.call_args.kwargs["fts_only"] is True
    svc.shutdown()


def test_kick_respects_busy_check(qtbot, db):
    """Narração/RAG manual em andamento continua bloqueando mesmo o kick."""
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(),
                           busy_check=lambda: True)
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._kick_once = True
        svc._on_tick()
        MockWorker.assert_not_called()
    svc.shutdown()


def test_kick_is_consumed_once(qtbot, db):
    """O kick dispensa os gates UMA vez; o tick seguinte volta ao regime
    normal (carência/ociosidade bloqueiam de novo)."""
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(),
                           config=FakeConfig({"auto_index.startup_grace_s": 300}))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._kick_once = True
        svc._on_tick()
        MockWorker.assert_called_once()
        svc._worker = None  # isola o gate de worker-em-curso
        svc._on_tick()      # sem kick: carência + atividade recente bloqueiam
        MockWorker.assert_called_once()
    svc.shutdown()


def test_kick_after_import_schedules_immediate_tick(qtbot, db):
    """kick_after_import agenda o tick via singleShot(0) — comprovado com o
    event loop real do qtbot."""
    bid = _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(),
                           config=FakeConfig({"auto_index.startup_grace_s": 300}))
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc.kick_after_import()
        qtbot.wait(80)  # processa o singleShot(0)
        MockWorker.assert_called_once()
        assert MockWorker.call_args.args[0] == bid
        assert MockWorker.call_args.kwargs["fts_only"] is True
    svc.shutdown()
