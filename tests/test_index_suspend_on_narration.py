"""Rodada 3 de ajustes de TTS — Tarefa A: o INÍCIO da narração suspende
IMEDIATAMENTE a auto-indexação em ocioso já em andamento.

Contexto: o gating por ``busy_check`` (rodada 2) só impede que um NOVO job de
indexação COMECE durante a narração. Mas um job JÁ em curso continuava rodando
e sua contenção de CPU/GPU (embeddings, bge-m3) elevava o TTFB do Kokoro (24,92s
medidos com 900 chunks concorrentes → SLO de 3s violado → fallback indevido p/
Piper). Agora o ReaderView emite ``narration_started`` quando o áudio começa de
fato e o MainWindow o conecta a ``AutoIndexService.cancel_active()``.

Testes unitários e leves (padrão de test_index_narration_gating.py): evitam
construir ``MainWindow``/``ReaderView`` reais (construtores pesados) e exercitam
os métodos reais via objetos "dummy" mínimos que emprestam o método da classe
real, além de uma checagem estática da fiação de sinais.
"""
import inspect
from unittest.mock import MagicMock

import pytest

from src.core.database import LibraryDB
from src.gui.auto_index_service import AutoIndexService
from src.gui.reader_view import ReaderView
from src.gui.main_window import MainWindow


class FakeEngine:
    def needs_reindex(self):
        return False


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


# ── 1. AutoIndexService.cancel_active() ────────────────────────────────

def test_cancel_active_cancels_running_worker(qtbot, db):
    """Com um worker em andamento, cancel_active() o cancela cooperativamente."""
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=lambda: False)
    worker = MagicMock()
    worker.isRunning.return_value = True
    svc._worker = worker
    svc._current = (1, "Livro X")

    svc.cancel_active()

    worker.cancel.assert_called_once()
    # Não-bloqueante: NUNCA faz wait() (roda na thread da GUI).
    worker.wait.assert_not_called()
    svc._worker = None  # evita que shutdown() mexa no mock
    svc.shutdown()


def test_cancel_active_noop_without_worker(qtbot, db):
    """Idempotente/seguro: sem worker ativo, é um no-op silencioso."""
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=lambda: False)
    assert svc._worker is None
    svc.cancel_active()  # não deve levantar
    svc.shutdown()


def test_cancel_active_noop_when_worker_not_running(qtbot, db):
    """Worker existente mas já parado → não chama cancel()."""
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=lambda: False)
    worker = MagicMock()
    worker.isRunning.return_value = False
    svc._worker = worker

    svc.cancel_active()

    worker.cancel.assert_not_called()
    svc._worker = None
    svc.shutdown()


def test_cancel_active_swallows_worker_cancel_errors(qtbot, db):
    """ADR-005: um erro ao cancelar nunca derruba o app."""
    svc = AutoIndexService(db=db, rag_engine=FakeEngine(), busy_check=lambda: False)
    worker = MagicMock()
    worker.isRunning.return_value = True
    worker.cancel.side_effect = RuntimeError("boom")
    svc._worker = worker

    svc.cancel_active()  # não deve propagar

    worker.cancel.assert_called_once()
    svc._worker = None
    svc.shutdown()


# ── 2. ReaderView emite narration_started quando o áudio começa ────────

def test_on_audio_started_emits_narration_started():
    """_on_audio_started (único ponto de início real, normal e pré-síntese)
    emite narration_started."""
    class _Dummy:
        _on_audio_started = ReaderView._on_audio_started

    d = _Dummy()
    d._audio_paused = True
    d._translating_for_audio = True
    d._set_audio_button_state = MagicMock()
    d._act_audio_stop = MagicMock()
    d.narration_started = MagicMock()
    d._maybe_presynthesize_next = MagicMock()

    d._on_audio_started()

    d.narration_started.emit.assert_called_once()


def test_reader_view_declares_narration_started_signal():
    from PyQt6.QtCore import pyqtSignal
    # O atributo de classe é o descritor do sinal (não o bound signal).
    assert isinstance(ReaderView.narration_started, pyqtSignal)


# ── 3. Fiação estática MainWindow → AutoIndexService ───────────────────

def test_main_window_wires_narration_started_to_cancel_active():
    """Checagem estática: o MainWindow conecta narration_started ao
    cancel_active do serviço de auto-indexação (fiação por checagem estática,
    para não instanciar a árvore de widgets inteira)."""
    src = inspect.getsource(MainWindow)
    assert (
        "narration_started.connect(self._auto_index_service.cancel_active)"
        in src
    )


def test_reader_view_source_emits_signal_in_on_audio_started():
    src = inspect.getsource(ReaderView._on_audio_started)
    assert "self.narration_started.emit()" in src
