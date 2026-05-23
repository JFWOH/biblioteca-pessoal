import pytest
from PyQt6.QtCore import Qt
from src.gui.library_view import LibraryView

@pytest.fixture
def library_view(qtbot):
    view = LibraryView()
    qtbot.addWidget(view)
    return view

def test_library_view_load_books(library_view):
    books = [
        {"id": 1, "title": "Book 1", "file_path": __file__},
        {"id": 2, "title": "Book 2", "file_path": __file__},
    ]
    library_view.load_books(books)
    
    assert len(library_view._cards) == 2
    assert library_view._count_label.text() == "2 livros"
    # Bulk bar deve estar invisível
    assert library_view._bulk_bar.isHidden()

def test_library_view_selection_and_bulk_bar(library_view, qtbot):
    books = [
        {"id": 1, "title": "Book 1", "file_path": __file__},
    ]
    library_view.load_books(books)
    
    # Seleciona via código para testar a barra
    library_view._toggle_selection(1)
    
    assert 1 in library_view._selected_ids
    assert not library_view._bulk_bar.isHidden()
    assert "1 livro selecionado" in library_view._sel_count_lbl.text()
    
    # Limpa seleção
    library_view._clear_selection()
    assert 1 not in library_view._selected_ids
    assert library_view._bulk_bar.isHidden()

def test_library_view_broken_filter(library_view):
    books = [
        {"id": 1, "title": "Book Real", "file_path": __file__},
        {"id": 2, "title": "Book Quebrado", "file_path": "/fake/path.epub"},
    ]
    library_view.load_books(books)
    
    # Ativa filtro
    library_view._on_broken_filter_toggled(True)
    assert len(library_view._cards) == 1
    assert library_view._cards[0]._book_id == 2
    
    # Desativa filtro
    library_view._on_broken_filter_toggled(False)
    assert len(library_view._cards) == 2

def test_library_view_select_all_broken(library_view):
    books = [
        {"id": 1, "title": "Book Real", "file_path": __file__},
        {"id": 2, "title": "Book Quebrado", "file_path": "/fake/path.epub"},
    ]
    library_view.load_books(books)
    
    library_view._select_all_broken()
    
    assert 1 not in library_view._selected_ids
    assert 2 in library_view._selected_ids
    assert not library_view._bulk_bar.isHidden()
