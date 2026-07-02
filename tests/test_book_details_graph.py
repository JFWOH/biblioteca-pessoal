"""Testes da seção de grafo (Conceitos / Livros relacionados) no BookDetails."""
import pytest
from PyQt6.QtWidgets import QPushButton

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore
from src.gui.book_details import BookDetails


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db, title="Livro", path="/tmp/x.pdf") -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf", page_count=5)


def test_section_hidden_without_graph_data(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    bid = _book(db)
    panel.show_book(db.get_book(bid))
    assert not panel._graph_section.isVisibleTo(panel)


def test_section_shows_concepts(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    bid = _book(db)
    GraphStore(db).add_mentions(
        bid, "page:1", [("entropia", "Entropia", 0.9), ("calor", "Calor", 0.4)], page=1)
    panel.show_book(db.get_book(bid))
    assert panel._graph_section.isVisibleTo(panel)
    assert "Entropia" in panel._concepts_label.text()
    assert "Calor" in panel._concepts_label.text()


def test_related_book_button_emits_signal(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    store = GraphStore(db)
    shared = [("x", "X", 1.0), ("y", "Y", 1.0)]
    store.add_mentions(b1, "page:1", shared, page=1)
    store.add_mentions(b2, "page:1", shared, page=1)
    store.recompute_book_edges(b1)

    got = []
    panel.related_book_clicked.connect(got.append)
    panel.show_book(db.get_book(b1))

    btns = [b for b in panel._graph_section.findChildren(QPushButton)]
    assert len(btns) == 1 and "B" in btns[0].text()
    btns[0].click()
    assert got == [b2]


def test_refresh_replaces_old_buttons(qtbot, db):
    """Trocar de livro não acumula botões de relacionados antigos."""
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    store = GraphStore(db)
    shared = [("x", "X", 1.0), ("y", "Y", 1.0)]
    store.add_mentions(b1, "page:1", shared, page=1)
    store.add_mentions(b2, "page:1", shared, page=1)
    store.recompute_book_edges(b1)

    panel.show_book(db.get_book(b1))
    panel.show_book(db.get_book(b1))  # refresh duplo
    assert panel._related_btns_lay.count() == 1


def test_clear_hides_section(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    bid = _book(db)
    GraphStore(db).add_mentions(bid, "page:1", [("tema", "Tema", 1.0)], page=1)
    panel.show_book(db.get_book(bid))
    panel.clear()
    assert not panel._graph_section.isVisibleTo(panel)
