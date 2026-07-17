"""Testes do scroll na área informativa do BookDetails.

Sintoma corrigido (teste real do usuário): com "🔗 Livros relacionados"
populado, o conteúdo do painel excedia a altura disponível e o Qt comprimia
os widgets uns sobre os outros — botões de ação cortados/sobrepostos e título
sobre a capa. A correção envolve a parte informativa (capa..grafo) num
QScrollArea e mantém os botões de ação FIXOS abaixo, fora do scroll.
"""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore
from src.gui.book_details import BookDetails


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db, title="Livro", path="/tmp/x.pdf") -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf", page_count=5)


def test_info_scroll_area_exists_and_is_configured(qtbot, db):
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)

    assert isinstance(panel._info_scroll, QScrollArea)
    assert panel._info_scroll.widgetResizable() is True
    # Nunca scroll horizontal — conteúdo se adapta à largura do painel.
    assert (
        panel._info_scroll.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert panel._info_scroll.frameShape() == QScrollArea.Shape.NoFrame
    # minimumHeight sane — painel não colapsa a zero.
    assert panel._info_scroll.minimumHeight() > 0


def test_informative_widgets_are_inside_scroll_area(qtbot, db):
    """Capa, título, autor e a seção do grafo ficam DENTRO do scroll."""
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    scroll_widget = panel._info_scroll.widget()

    assert scroll_widget is not None
    assert scroll_widget.isAncestorOf(panel._cover)
    assert scroll_widget.isAncestorOf(panel._title)
    assert scroll_widget.isAncestorOf(panel._author)
    assert scroll_widget.isAncestorOf(panel._desc)
    assert scroll_widget.isAncestorOf(panel._graph_section)


def test_action_buttons_are_fixed_outside_scroll_area(qtbot, db):
    """Os botões de ação NUNCA rolam — ficam sempre visíveis abaixo do scroll."""
    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    scroll_widget = panel._info_scroll.widget()

    for btn in (
        panel._open_btn,
        panel._dossier_btn,
        panel._fav_btn,
        panel._col_btn,
        panel._meta_btn,
        panel._remove_col_btn,
        panel._del_btn,
    ):
        assert not scroll_widget.isAncestorOf(btn), (
            f"{btn.text()!r} não deveria estar dentro da área rolável"
        )
        # E devem ser descendentes do painel (ainda visíveis na hierarquia).
        assert panel.isAncestorOf(btn)


def test_show_book_with_populated_related_books_still_works(qtbot, db):
    """Reprodução do sintoma: grafo populado com relacionados não quebra a UI."""
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    store = GraphStore(db)
    shared = [("x", "X", 1.0), ("y", "Y", 1.0), ("z", "Z", 1.0)]
    store.add_mentions(b1, "page:1", shared, page=1)
    store.add_mentions(b2, "page:1", shared, page=1)
    store.recompute_book_edges(b1)

    panel = BookDetails(db=db)
    qtbot.addWidget(panel)
    panel.show_book(db.get_book(b1))

    assert panel._graph_section.isVisibleTo(panel)
    # Botões de ação continuam presentes e fora do scroll mesmo com o grafo
    # populado (é justamente o cenário que sobrepunha antes da correção).
    scroll_widget = panel._info_scroll.widget()
    assert not scroll_widget.isAncestorOf(panel._open_btn)
    assert panel._open_btn.isVisibleTo(panel)
