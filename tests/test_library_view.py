import pytest
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


# ── Rodada A1 — débito Onda 2 "filtro-quebrados-após-busca" (mesma classe
# de bug do estado vazio de busca, Tarefa 2.6): o toggle "Mostrar quebrados"
# ficava marcado (checked) mesmo depois de ``load_books`` trocar os dados
# por baixo dele (nova busca, troca de seção, reordenação) — a grade
# passava a mostrar a lista CHEIA enquanto o botão continuava indicando
# "só quebrados". ────────────────────────────────────────────────────────

def test_broken_filter_unchecked_when_new_load_books_arrives(library_view):
    # setChecked (não a chamada direta do handler) simula o clique real do
    # usuário — dispara o sinal ``toggled`` conectado a
    # ``_on_broken_filter_toggled``, o mesmo caminho usado em produção.
    books = [
        {"id": 1, "title": "Book Real", "file_path": __file__},
        {"id": 2, "title": "Book Quebrado", "file_path": "/fake/path.epub"},
    ]
    library_view.load_books(books)
    library_view._broken_btn.setChecked(True)
    assert library_view._broken_btn.isChecked()
    assert len(library_view._cards) == 1  # só o quebrado

    # Nova carga por baixo do toggle (ex.: uma busca, ou troca de seção) —
    # o botão não pode continuar marcado enquanto a grade mostra tudo.
    library_view.load_books(books)
    assert not library_view._broken_btn.isChecked()
    assert len(library_view._cards) == 2  # lista cheia, consistente com o botão


def test_broken_filter_reset_does_not_corrupt_is_search_flag(library_view):
    """O reset usa blockSignals para não disparar _on_broken_filter_toggled,
    que reescreveria _is_search_result para False mesmo numa busca ativa
    (regressão sutil: cascata do handler sobrescreveria o valor que
    load_books acabou de setar corretamente logo acima)."""
    library_view.load_books([{"id": 1, "title": "Livro", "file_path": __file__}])
    library_view._broken_btn.setChecked(True)
    assert library_view._broken_btn.isChecked()

    # Busca ativa que não encontrou nada (is_search=True, lista vazia) —
    # deve mostrar o estado "sem resultado da busca", não "biblioteca vazia".
    library_view.load_books([], is_search=True)
    assert not library_view._broken_btn.isChecked()
    assert library_view._is_search_result is True
    assert library_view._empty_widget.isHidden()
    assert not library_view._search_empty_widget.isHidden()


def test_broken_filter_toggle_still_works_after_reset(library_view):
    """O botão continua funcional (não fica "travado" desmarcado) depois de
    um reset — o usuário pode reativar o filtro sobre os dados novos."""
    books = [
        {"id": 1, "title": "Book Real", "file_path": __file__},
        {"id": 2, "title": "Book Quebrado", "file_path": "/fake/path.epub"},
    ]
    library_view.load_books(books)
    library_view._broken_btn.setChecked(True)
    library_view.load_books(books)  # reseta o toggle (débito Onda 2)
    assert not library_view._broken_btn.isChecked()

    library_view._broken_btn.setChecked(True)
    assert library_view._broken_btn.isChecked()
    assert len(library_view._cards) == 1
    assert library_view._cards[0]._book_id == 2
