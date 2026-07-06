"""Testes do diálogo do Dossiê do Livro (Fase 4)."""
import pytest
from PyQt6.QtWidgets import QLabel, QPushButton

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore
from src.gui.dialogs.book_dossier_dialog import BookDossierDialog


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nenhum teste dispara o worker de síntese (rede)."""
    monkeypatch.setattr(BookDossierDialog, "_start_synthesis", lambda self: None)


def _book(db, title="Livro", path="/tmp/x.pdf", pages=4) -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf",
                       page_count=pages)


def _seed_graph(db, bid, other):
    store = GraphStore(db)
    shared = [("entropia", "Entropia", 0.9), ("calor", "Calor", 0.4)]
    store.add_mentions(bid, "page:1", shared, page=1)
    store.add_mentions(other, "page:1", shared, page=1)
    store.recompute_book_edges(bid)


def _all_label_text(dialog) -> str:
    return " | ".join(lbl.text() for lbl in dialog.findChildren(QLabel))


def test_renders_sections_with_data(qtbot, db):
    bid = _book(db, title="Calor e Caos", path="/tmp/a.pdf")
    other = _book(db, title="Física do Tempo", path="/tmp/b.pdf")
    _seed_graph(db, bid, other)
    db.add_annotation(bid, 2, content="A entropia sempre cresce.")
    db.update_reading_progress(bid, current_page=2, total_pages=4)

    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)
    text = _all_label_text(dialog)
    assert "Calor e Caos" in text
    assert "Entropia" in text and "Calor" in text          # mapa conceitual
    assert "25%" in text and "(1 de 4)" in text             # confiança
    assert "A entropia sempre cresce." in text              # anotações
    assert "Página 2 de 4" in text                          # progresso
    assert dialog._synthesis_label is not None
    assert "Gerando síntese" in dialog._synthesis_label.text()


def test_empty_graph_shows_notice(qtbot, db):
    bid = _book(db)
    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)
    text = _all_label_text(dialog)
    assert "ainda não foi processado pelo grafo" in text
    assert dialog._synthesis_label is None  # sem seção de síntese


def test_missing_book(qtbot, db):
    dialog = BookDossierDialog(db, 999)
    qtbot.addWidget(dialog)
    assert "Livro não encontrado" in _all_label_text(dialog)


def test_related_click_emits_and_closes(qtbot, db):
    bid = _book(db, title="A", path="/tmp/a.pdf")
    other = _book(db, title="B", path="/tmp/b.pdf")
    _seed_graph(db, bid, other)

    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)
    got = []
    dialog.open_book_requested.connect(got.append)
    rel_btns = [b for b in dialog.findChildren(QPushButton) if "B" in b.text()]
    assert len(rel_btns) == 1
    rel_btns[0].click()
    assert got == [other]


def test_synthesis_ready_updates_label(qtbot, db):
    bid = _book(db, title="A", path="/tmp/a.pdf")
    other = _book(db, title="B", path="/tmp/b.pdf")
    _seed_graph(db, bid, other)
    dialog = BookDossierDialog(db, bid)
    qtbot.addWidget(dialog)

    dialog._on_synthesis_ready("Este livro trata de entropia.")
    assert dialog._synthesis_label.text() == "Este livro trata de entropia."

    dialog._on_synthesis_failed("timeout")
    assert "indisponível" in dialog._synthesis_label.text()
