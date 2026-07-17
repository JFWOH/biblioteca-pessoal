"""Testes do painel X-Ray (Tarefa 3.2).

O widget ``XRayPanel`` é instanciável com pytest-qt. A fiação em
``reader_view.py`` e ``main_window.py`` (que importam QtWebEngine e não podem ser
instanciados depois de existir uma QApplication) é verificada por checagem
ESTÁTICA do código-fonte — padrão de test_book_dossier_wiring.py.
"""

from pathlib import Path

from src.gui.widgets.xray_panel import XRayPanel

_ROOT = Path(__file__).resolve().parent.parent
_READER_VIEW = (_ROOT / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")
_MAIN_WINDOW = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")


class _FakeStore:
    """GraphStore falso (duck-typed) para as tools graph_book_concepts /
    graph_concept_lookup."""

    def __init__(self, book_concepts=None, concept_books=None):
        self._bc = book_concepts or {}   # book_id -> [{display_name, weight, mentions}]
        self._cb = concept_books or {}   # nome normalizado -> [{title, book_id, mentions, pages}]

    def get_book_concepts(self, book_id, limit=10):
        return self._bc.get(book_id, [])

    def get_concept_books(self, name, limit=10):
        return self._cb.get(name, [])


# ── Widget XRayPanel (pytest-qt) ───────────────────────────────────────────

def test_populates_matched_concepts(qtbot):
    store = _FakeStore(book_concepts={1: [
        {"display_name": "Entropia", "weight": 1.0, "mentions": 3},
        {"display_name": "Fotossíntese", "weight": 0.5, "mentions": 1},
    ]})
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)

    panel.update_context(1, 0, "A entropia do sistema aumenta sempre.")
    assert panel._stack.currentWidget() is panel._tree
    assert panel._tree.topLevelItemCount() == 1
    assert panel._tree.topLevelItem(0).text(0) == "Entropia"


def test_empty_state_when_book_not_ingested(qtbot):
    store = _FakeStore(book_concepts={})  # livro 2 sem conceitos no grafo
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)

    panel.update_context(2, 0, "qualquer texto")
    assert panel._stack.currentWidget() is panel._empty
    assert "grafo" in panel._empty.text().lower()


def test_empty_state_when_no_concept_on_page(qtbot):
    store = _FakeStore(book_concepts={1: [
        {"display_name": "Entropia", "weight": 1.0, "mentions": 3},
    ]})
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)

    panel.update_context(1, 4, "página sobre um assunto totalmente distinto")
    assert panel._stack.currentWidget() is panel._empty


def test_degradation_without_store(qtbot):
    panel = XRayPanel(graph_store=None)
    qtbot.addWidget(panel)
    panel.update_context(1, 0, "entropia e mais")
    assert panel._stack.currentWidget() is panel._empty


def test_expand_loads_related_books_excluding_current(qtbot):
    store = _FakeStore(
        book_concepts={1: [{"display_name": "Entropia", "weight": 1.0, "mentions": 2}]},
        concept_books={"entropia": [
            {"title": "Livro A", "book_id": 1, "mentions": 2, "pages": [1]},   # atual
            {"title": "Livro B", "book_id": 7, "mentions": 5, "pages": [3]},
        ]},
    )
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)
    panel.update_context(1, 0, "aqui a entropia aparece")

    concept_item = panel._tree.topLevelItem(0)
    concept_item.setExpanded(True)  # dispara o lazy-load (itemExpanded)
    # O livro atual (book_id=1) é excluído — sobra só o Livro B.
    assert concept_item.childCount() == 1
    assert "Livro B" in concept_item.child(0).text(0)


def test_click_related_book_emits_open(qtbot):
    store = _FakeStore(
        book_concepts={1: [{"display_name": "Entropia", "weight": 1.0, "mentions": 2}]},
        concept_books={"entropia": [
            {"title": "Livro B", "book_id": 7, "mentions": 5, "pages": [3]},
        ]},
    )
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)
    panel.update_context(1, 0, "entropia presente")

    concept_item = panel._tree.topLevelItem(0)
    concept_item.setExpanded(True)
    book_item = concept_item.child(0)

    got = []
    panel.open_book_requested.connect(got.append)
    panel._on_item_clicked(book_item)
    assert got == [7]


def test_click_concept_toggles_expansion(qtbot):
    store = _FakeStore(
        book_concepts={1: [{"display_name": "Entropia", "weight": 1.0, "mentions": 2}]},
        concept_books={"entropia": []},
    )
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)
    panel.update_context(1, 0, "entropia presente")

    concept_item = panel._tree.topLevelItem(0)
    assert not concept_item.isExpanded()
    panel._on_item_clicked(concept_item)
    assert concept_item.isExpanded()


def test_concepts_cached_per_book(qtbot):
    calls = {"n": 0}

    class CountingStore(_FakeStore):
        def get_book_concepts(self, book_id, limit=10):
            calls["n"] += 1
            return super().get_book_concepts(book_id, limit)

    store = CountingStore(book_concepts={1: [
        {"display_name": "Entropia", "weight": 1.0, "mentions": 2}]})
    panel = XRayPanel(graph_store=store)
    qtbot.addWidget(panel)

    panel.update_context(1, 0, "entropia")
    panel.update_context(1, 1, "entropia de novo")
    panel.update_context(1, 2, "mais entropia")
    assert calls["n"] == 1  # busca de conceitos do livro é 1x (cache)


# ── Fiação estática em reader_view.py ──────────────────────────────────────

def test_reader_view_adds_xray_tab():
    assert 'self._side_panel_tabs.addTab(self._xray_panel, "X-Ray")' in _READER_VIEW
    assert "XRayPanel(" in _READER_VIEW


def test_reader_view_updates_xray_on_page():
    assert "self._xray_panel.update_context(" in _READER_VIEW


# ── Fiação estática em main_window.py ──────────────────────────────────────

def test_main_window_wires_xray_open_book():
    assert ("self._reader_view._xray_panel.open_book_requested.connect(self._on_book_open)"
            in _MAIN_WINDOW)


def test_main_window_wires_source_clicked():
    assert "self._rag_panel.source_clicked.connect(self._on_rag_source_clicked)" in _MAIN_WINDOW
    assert "set_books_provider(self._db.get_all_books)" in _MAIN_WINDOW


def test_main_window_has_source_clicked_handler():
    assert "def _on_rag_source_clicked(self, book_id: int, page: int)" in _MAIN_WINDOW
    assert "self._reader_view._go_to_page(max(0, int(page)))" in _MAIN_WINDOW
