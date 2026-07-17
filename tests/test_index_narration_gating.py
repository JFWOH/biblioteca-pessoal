"""Testes da rodada 2 de ajustes de TTS: indexação em ocioso não compete com
narração ativa, e ruído benigno do MuPDF é suprimido.

Escopo (ver AGENTS.md / prompt do executor F2):
1. ``ReaderView.is_narrating()`` encapsula corretamente o estado do worker
   de áudio privado.
2. ``MainWindow._is_narration_active()`` usa esse método com defesa contra
   ``_reader_view`` ainda inexistente.
3. ``AutoIndexService._on_tick`` trata "ocupado" (RAG manual OU narração,
   via ``busy_check``) como atividade recente — mantém o relógio de
   ociosidade fresco em vez de deixá-lo obsoleto.
4. ``AutoIndexWorker`` sempre inicia em prioridade baixa (best-effort).
5. ``PDFReader.open()`` suprime o DISPLAY de erros não-fatais do MuPDF.

Testes unitários e leves: evitam construir ``MainWindow``/``ReaderView``
reais (construtores pesados — DB, RAG engine, TTS router, widgets Qt) e, em
vez disso, exercitam os métodos reais via um objeto "dummy" mínimo que
empresta o método da classe real — testa o código de produção sem pagar o
custo de instanciar toda a árvore de widgets.
"""
import time
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QThread

from src.core.database import LibraryDB
from src.gui.auto_index_service import AutoIndexService
from src.gui.reader_view import ReaderView
from src.gui.main_window import MainWindow


class FakeEngine:
    def __init__(self, needs_reindex=False):
        self._needs = needs_reindex

    def needs_reindex(self):
        return self._needs


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db, title="Livro", path="/tmp/x.pdf") -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf")


# ── 1. ReaderView.is_narrating() ───────────────────────────────────────

def test_reader_view_is_narrating_false_without_worker():
    class _Dummy:
        is_narrating = ReaderView.is_narrating

    d = _Dummy()  # sem _audio_worker nunca setado
    assert d.is_narrating() is False


def test_reader_view_is_narrating_false_when_worker_stopped():
    class _Dummy:
        is_narrating = ReaderView.is_narrating

    d = _Dummy()
    d._audio_worker = MagicMock()
    d._audio_worker.isRunning.return_value = False
    assert d.is_narrating() is False


def test_reader_view_is_narrating_true_when_worker_running():
    class _Dummy:
        is_narrating = ReaderView.is_narrating

    d = _Dummy()
    d._audio_worker = MagicMock()
    d._audio_worker.isRunning.return_value = True
    assert d.is_narrating() is True


# ── 2. MainWindow._is_narration_active() ───────────────────────────────

def test_main_window_narration_active_false_without_reader_view():
    class _DummyWin:
        _is_narration_active = MainWindow._is_narration_active

    w = _DummyWin()  # _reader_view nunca setado (ex.: durante __init__)
    assert w._is_narration_active() is False


def test_main_window_narration_active_reflects_reader_view():
    class _DummyWin:
        _is_narration_active = MainWindow._is_narration_active

    w = _DummyWin()
    w._reader_view = MagicMock()
    w._reader_view.is_narrating.return_value = True
    assert w._is_narration_active() is True

    w._reader_view.is_narrating.return_value = False
    assert w._is_narration_active() is False


# ── 3. AutoIndexService: busy (incl. narração) conta como atividade ────

def test_busy_check_true_refreshes_last_activity(qtbot, db):
    """Antes da rodada 2: um busy_check==True não tocava _last_activity, que
    ficava obsoleto durante uma narração longa — ao terminar, a indexação
    retomava IMEDIATAMENTE em vez de aguardar um novo idle_min_inactivity_s.
    """
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=lambda: True)
    svc._last_activity = time.monotonic() - 9999  # bem obsoleto
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()
    # _last_activity foi renovado pelo tick (busy conta como atividade)
    assert time.monotonic() - svc._last_activity < 1.0
    svc.shutdown()


def test_busy_check_false_does_not_touch_last_activity(qtbot, db):
    """Quando não está ocupado, o tick segue seu caminho normal (não deve
    mexer em _last_activity antes da checagem de inatividade)."""
    _book(db)
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=lambda: False)
    stale = time.monotonic() - 9999
    svc._last_activity = stale
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc._on_tick()
        MockWorker.assert_called_once()  # ocioso há muito tempo -> indexa
    svc.shutdown()


def test_narration_active_blocks_new_indexing_via_busy_check(qtbot, db):
    """Integração leve: um busy_check equivalente ao que o MainWindow monta
    (RAG manual OU narração) bloqueia novo trabalho enquanto está narrando."""
    _book(db)
    reader_view = MagicMock()
    reader_view.is_narrating.return_value = True
    rag_worker = None  # nenhum RAG manual em andamento

    def busy_check():
        return bool(rag_worker) or reader_view.is_narrating()

    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=busy_check)
    svc._last_activity = time.monotonic() - 9999
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()  # narrando -> não inicia
    svc.shutdown()


# ── 4. AutoIndexWorker: prioridade baixa permanente ────────────────────

def test_auto_index_worker_starts_with_lowest_priority(qtbot, db):
    from src.gui.workers.auto_index_worker import AutoIndexWorker

    bid = _book(db)
    w = AutoIndexWorker(bid, db, FakeEngine())

    captured = {}

    def fake_start(self, priority=QThread.Priority.InheritPriority):
        captured["priority"] = priority

    with patch.object(QThread, "start", fake_start):
        w.start()

    assert captured["priority"] == QThread.Priority.LowestPriority


def test_auto_index_worker_start_allows_explicit_priority_override(qtbot, db):
    """O default é prioridade baixa, mas quem passar prioridade explícita
    ainda é respeitado (não há hardcode que ignore o argumento)."""
    from src.gui.workers.auto_index_worker import AutoIndexWorker

    bid = _book(db)
    w = AutoIndexWorker(bid, db, FakeEngine())

    captured = {}

    def fake_start(self, priority=QThread.Priority.InheritPriority):
        captured["priority"] = priority

    with patch.object(QThread, "start", fake_start):
        w.start(QThread.Priority.NormalPriority)

    assert captured["priority"] == QThread.Priority.NormalPriority


# ── 5. PDFReader.open(): silencia ruído benigno do MuPDF ───────────────

def test_pdf_reader_open_suppresses_mupdf_error_display(tmp_path):
    import fitz
    from src.readers.pdf_reader import PDFReader

    pdf_path = tmp_path / "min.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    with patch("fitz.TOOLS.mupdf_display_errors") as mock_suppress:
        reader = PDFReader(pdf_path)
        reader.open()
        mock_suppress.assert_called_once_with(False)
    reader.close()
