"""Tarefa 2.6 — estado "busca sem resultado" != "biblioteca vazia".

``LibraryView.load_books(books, is_search=...)`` decide qual estado vazio
mostrar quando ``books`` é uma lista vazia: o convite de importação
(biblioteca realmente vazia) ou o aviso "sem resultado" (busca/filtro sem
match, mas a biblioteca tem livros). Cobre também o merge de
``progress_map`` (Tarefa 2.1) feito dentro de ``load_books``.
"""
import pytest

from src.gui.library_view import LibraryView


@pytest.fixture
def view(qtbot):
    v = LibraryView()
    qtbot.addWidget(v)
    return v


def _book(book_id, title="Livro"):
    return {"id": book_id, "title": title, "file_path": __file__}


# ── Biblioteca genuinamente vazia (comportamento pré-existente) ────────────

def test_empty_library_shows_import_invite_by_default(view):
    view.load_books([])
    assert not view._empty_widget.isHidden()
    assert view._search_empty_widget.isHidden()


def test_empty_library_after_loading_books_then_clearing(view):
    view.load_books([_book(1)])
    view.load_books([])  # ex.: todos os livros removidos, sem ser busca
    assert not view._empty_widget.isHidden()
    assert view._search_empty_widget.isHidden()


# ── Busca sem resultado (Tarefa 2.6) ────────────────────────────────────────

def test_search_no_results_shows_search_empty_state(view):
    view.load_books([_book(1)])  # biblioteca tem 1 livro
    view.load_books([], is_search=True)  # busca não encontrou nada

    assert view._empty_widget.isHidden()
    assert not view._search_empty_widget.isHidden()


def test_search_empty_state_has_no_import_button_text(view):
    view.load_books([], is_search=True)
    # O widget de busca-sem-resultado não deve conter o convite de importação
    # do estado de biblioteca vazia.
    assert "Nenhum resultado" in _all_labels_text(view._search_empty_widget)
    assert "Importe" not in _all_labels_text(view._search_empty_widget)


def test_search_with_results_shows_neither_empty_state(view):
    view.load_books([_book(1)], is_search=True)
    assert view._empty_widget.isHidden()
    assert view._search_empty_widget.isHidden()


def test_clearing_search_restores_library_empty_semantics(view):
    """Depois de uma busca vazia, um load_books "normal" (is_search=False,
    ex.: busca foi limpa) volta a exibir o estado de biblioteca vazia."""
    view.load_books([], is_search=True)
    assert not view._search_empty_widget.isHidden()

    view.load_books([])  # is_search default = False
    assert not view._empty_widget.isHidden()
    assert view._search_empty_widget.isHidden()


# ── progress_map: merge feito em load_books (Tarefa 2.1) ──────────────────

def test_load_books_merges_progress_map_into_cards(view):
    view.load_books([_book(1), _book(2)], progress_map={1: 55.0})
    by_id = {c._book_id: c for c in view._cards}
    assert by_id[1].book_data["percentage"] == 55.0
    assert by_id[2].book_data.get("percentage", 0) == 0


def test_load_books_without_progress_map_is_backward_compatible(view):
    """progress_map é opcional — chamadas antigas (só a lista de livros)
    continuam funcionando sem erro."""
    view.load_books([_book(1)])
    assert len(view._cards) == 1


def _all_labels_text(widget) -> str:
    from PyQt6.QtWidgets import QLabel
    return " ".join(lbl.text() for lbl in widget.findChildren(QLabel))
