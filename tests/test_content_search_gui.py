"""Testes de GUI da busca no conteúdo (Tarefa 5.1).

Cobre o toggle "No conteúdo" da barra de busca, o painel de resultados
(``ContentSearchResults``) — populamento, contagem, estado vazio, rodapé de
pendentes, escape de HTML no snippet e ativação por clique — e a seleção de
candidato do backfill FTS no auto-indexador em ocioso.
"""

import time
from unittest.mock import patch

from PyQt6.QtWidgets import QLabel

from src.core.database import LibraryDB
from src.core.fts_search import SNIPPET_CLOSE, SNIPPET_OPEN
from src.gui.auto_index_service import AutoIndexService
from src.gui.search_bar import SearchBar
from src.gui.widgets.content_search_results import ContentSearchResults, _ResultRow


# ── Barra de busca: toggle "No conteúdo" ───────────────────────────────

def test_search_bar_content_toggle_sets_flag(qtbot):
    bar = SearchBar()
    qtbot.addWidget(bar)
    captured = []
    bar.search_changed.connect(lambda q, f: captured.append((q, f)))
    bar._input.setText("gato")
    bar._content_toggle.setChecked(True)
    bar._emit_search()
    q, f = captured[-1]
    assert q == "gato"
    assert f.get("content") is True
    assert bar.is_content_mode()


def test_search_bar_content_off_has_no_flag(qtbot):
    bar = SearchBar()
    qtbot.addWidget(bar)
    captured = []
    bar.search_changed.connect(lambda q, f: captured.append((q, f)))
    bar._input.setText("gato")
    bar._emit_search()
    _, f = captured[-1]
    assert "content" not in f


def test_search_bar_clear_resets_toggle(qtbot):
    bar = SearchBar()
    qtbot.addWidget(bar)
    bar._content_toggle.setChecked(True)
    bar.clear()
    assert not bar.is_content_mode()


# ── Painel de resultados ───────────────────────────────────────────────

def _sample():
    return [
        {"book_id": 7, "page_number": 4,
         "snippet": f"antes {SNIPPET_OPEN}gato{SNIPPET_CLOSE} depois", "title": "Meu Livro"},
        {"book_id": 9, "page_number": 0,
         "snippet": "outra ocorrência", "title": "Outro Livro"},
    ]


def test_results_populate_and_count(qtbot):
    w = ContentSearchResults()
    qtbot.addWidget(w)
    w.show_results("gato", _sample(), pending_count=3)
    assert "2 resultados" in w._count.text()
    rows = w._container.findChildren(_ResultRow)
    assert len(rows) == 2
    # rodapé de pendentes aparece
    assert not w._footer.isHidden()
    assert "3 livro" in w._footer.text()


def test_results_singular_count(qtbot):
    w = ContentSearchResults()
    qtbot.addWidget(w)
    w.show_results("gato", _sample()[:1], pending_count=0)
    assert "1 resultado" in w._count.text() and "resultados" not in w._count.text()
    assert w._footer.isHidden()  # sem pendentes → rodapé escondido


def test_results_empty_state(qtbot):
    w = ContentSearchResults()
    qtbot.addWidget(w)
    w.show_results("inexistente", [], pending_count=0)
    assert "Nenhum resultado" in w._count.text()
    empties = [lbl for lbl in w._container.findChildren(QLabel)
               if lbl.objectName() == "contentSearchEmpty"]
    assert empties and "Nenhuma página encontrada" in empties[0].text()
    assert 'inexistente' in empties[0].text()


def test_result_click_emits_activation(qtbot):
    w = ContentSearchResults()
    qtbot.addWidget(w)
    w.show_results("gato", _sample())
    activated = []
    w.result_activated.connect(lambda bid, pg: activated.append((bid, pg)))
    rows = w._container.findChildren(_ResultRow)
    rows[0].clicked.emit()  # o mesmo sinal que o mousePressEvent dispara
    assert activated == [(7, 4)]  # book_id + page_number (0-based)


def test_snippet_escapes_html_and_highlights(qtbot):
    w = ContentSearchResults()
    qtbot.addWidget(w)
    out = w._render_snippet(f"a < b & c {SNIPPET_OPEN}alvo{SNIPPET_CLOSE}")
    assert "&lt;" in out and "&amp;" in out       # HTML do livro escapado
    assert "<span" in out and "</span>" in out     # marcadores viram destaque
    assert SNIPPET_OPEN not in out and SNIPPET_CLOSE not in out


def test_show_results_replaces_previous(qtbot):
    w = ContentSearchResults()
    qtbot.addWidget(w)
    w.show_results("gato", _sample())
    w.show_results("cão", _sample()[:1])
    rows = w._container.findChildren(_ResultRow)
    assert len(rows) == 1  # não acumulou linhas da busca anterior


# ── Backfill FTS no auto-indexador em ocioso ───────────────────────────

class _FakeEngine:
    def needs_reindex(self):
        return False


def test_idle_backfills_rag_ok_without_fts(qtbot, tmp_path):
    db = LibraryDB(tmp_path / "lib.db")
    bid = db.add_book(title="Antigo", file_path="/tmp/a.pdf", file_format="pdf")
    db.set_indexing_status(bid, "indexed_ok")  # já no RAG, mas sem FTS
    svc = AutoIndexService(db=db, rag_engine=_FakeEngine())
    svc._last_activity = time.monotonic() - 9999
    svc._created_at = time.monotonic() - 9999  # já passou a carência de startup (B0)
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        svc._on_tick()
        MockWorker.assert_called_once()
        assert MockWorker.call_args[0][0] == bid
        assert MockWorker.call_args.kwargs.get("fts_only") is True
    svc.shutdown()


def test_idle_skips_book_already_in_fts(qtbot, tmp_path):
    db = LibraryDB(tmp_path / "lib.db")
    bid = db.add_book(title="Coberto", file_path="/tmp/b.pdf", file_format="pdf")
    db.set_indexing_status(bid, "indexed_ok")
    db.fts_index_book(bid, [(0, "conteúdo já indexado")])  # já tem FTS
    svc = AutoIndexService(db=db, rag_engine=_FakeEngine())
    svc._last_activity = time.monotonic() - 9999
    with patch("src.gui.auto_index_service.AutoIndexWorker") as MockWorker:
        svc._on_tick()
        MockWorker.assert_not_called()  # nada a indexar nem a backfill
    svc.shutdown()
