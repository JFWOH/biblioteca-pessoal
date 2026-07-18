"""Ajustes pós-teste (jul/2026) — fast path de recarga da grade da biblioteca.

``LibraryView.load_books`` ganhou um atalho: quando a lista enriquecida é
IDÊNTICA (por valor, mesma ordem) à última renderizada, os cards NÃO são
destruídos/recriados — reconstrução completa custa ~1 ms/card (medida em
``tools/profile_transitions.py``) e era paga à toa nas transições que voltam
à biblioteca sem mudança de dados. ``_refresh_grid`` também passou a suspender
repaints (``setUpdatesEnabled``) durante a reconstrução.

Rodada 4 (perf/gui): quando a lista MUDA, ``_refresh_grid`` RECICLA os cards
in-place (``BookCard.update_book`` por posição, criando/removendo só o delta
de tamanho) em vez de destruir/recriar todos — os testes de "lista mudou"
agora afirmam a reciclagem (mesmo objeto, conteúdo novo).

Estes testes são FUNCIONAIS (identidade de objetos, estados visuais) — nunca
de tempo: medição de tempo fica fora da suíte, no script de profiling.
"""
import pytest

from src.gui.library_view import LibraryView


@pytest.fixture
def view(qtbot):
    v = LibraryView()
    qtbot.addWidget(v)
    return v


def _book(book_id, title="Livro", **extra):
    return {"id": book_id, "title": title, "file_path": __file__, **extra}


# ── Atalho: lista idêntica não reconstrói ───────────────────────────────────

def test_reload_identical_list_reuses_cards(view):
    books = [_book(1), _book(2)]
    view.load_books(books)
    before = list(view._cards)

    # Cópias por VALOR (dicts novos, mesmo conteúdo) — como um _load_library
    # real, que sempre monta dicts novos a partir do banco.
    view.load_books([dict(b) for b in books])

    assert view._cards == before, "lista idêntica não deve recriar os cards"


def test_reload_identical_with_same_progress_map_reuses_cards(view):
    books = [_book(1), _book(2)]
    view.load_books(books, progress_map={1: 40.0})
    before = list(view._cards)

    view.load_books([dict(b) for b in books], progress_map={1: 40.0})

    assert view._cards == before


def test_reload_with_changed_title_recycles_card_in_place(view):
    """Rodada 4 (perf/gui): título mudou → o MESMO BookCard é reconfigurado
    (update_book), não destruído/recriado."""
    view.load_books([_book(1, title="Original")])
    before = list(view._cards)

    view.load_books([_book(1, title="Renomeado")])

    assert view._cards[0] is before[0], "card deve ser reciclado, não recriado"
    assert view._cards[0].book_data["title"] == "Renomeado"


def test_reload_with_changed_progress_recycles_card_in_place(view):
    view.load_books([_book(1)], progress_map={1: 10.0})
    before = list(view._cards)

    view.load_books([_book(1)], progress_map={1: 20.0})

    assert view._cards[0] is before[0], "card deve ser reciclado, não recriado"
    assert view._cards[0].book_data["percentage"] == 20.0


def test_reload_with_different_list_shrinks_by_delta(view):
    view.load_books([_book(1), _book(2)])
    first_card = view._cards[0]
    view.load_books([_book(1)])
    assert len(view._cards) == 1
    assert view._cards[0] is first_card  # posição 0 reciclada; só o delta saiu
    assert view._count_label.text().startswith("1 ")


def test_reload_with_longer_list_grows_by_delta(view):
    view.load_books([_book(1)])
    first_card = view._cards[0]
    view.load_books([_book(1), _book(2)])
    assert len(view._cards) == 2
    assert view._cards[0] is first_card  # existente reciclado
    assert view._cards[1]._book_id == 2  # só o delta foi criado


def test_recycled_card_shows_new_book_everywhere(view):
    """A reciclagem reconfigura TODO o conteúdo do card: id, broken e progresso."""
    view.load_books([_book(1, title="Um")])
    card = view._cards[0]

    view.load_books(
        [{"id": 9, "title": "Outro", "file_path": "/caminho/fantasma.epub"}],
        progress_map={9: 60.0},
    )

    assert view._cards[0] is card
    assert card._book_id == 9
    assert card.is_broken is True
    assert card._progress_bar is not None
    assert card._progress_bar.value() == 60


def test_recycled_card_resets_selection_visual(view):
    """Card selecionado que recebe OUTRO livro não pode continuar com o visual
    de seleção (a view já limpou _selected_ids no load_books)."""
    view.load_books([_book(1), _book(2)])
    view._toggle_selection(1)
    assert view._cards[0].is_selected

    view.load_books([_book(3), _book(4)])  # lista diferente → recicla

    assert view._selected_ids == set()
    assert all(not c.is_selected for c in view._cards)


# ── Atalho preserva a semântica de seleção e dos estados vazios ─────────────

def test_reload_identical_clears_selection(view):
    books = [_book(1), _book(2)]
    view.load_books(books)
    view._toggle_selection(1)
    assert not view._bulk_bar.isHidden()

    view.load_books([dict(b) for b in books])  # atalho (lista idêntica)

    assert view._selected_ids == set()
    assert view._bulk_bar.isHidden()
    assert all(not c.is_selected for c in view._cards)


def test_empty_list_never_uses_fast_path(view):
    """Lista vazia sempre re-renderiza: o widget de estado vazio depende de
    ``is_search``, que pode mudar entre chamadas com a mesma lista ([])."""
    view.load_books([], is_search=True)
    assert not view._search_empty_widget.isHidden()

    view.load_books([])  # mesma lista vazia, semântica diferente

    assert not view._empty_widget.isHidden()
    assert view._search_empty_widget.isHidden()


# ── setUpdatesEnabled: sempre reativado ────────────────────────────────────

def test_updates_reenabled_after_refresh(view):
    view.load_books([_book(1)])
    assert view.updatesEnabled()

    view.load_books([])  # caminho do early-return (lista vazia)
    assert view.updatesEnabled()


# ── Filtro de quebrados continua reconstruindo (sem atalho) ────────────────

def test_broken_filter_roundtrip_unaffected_by_fast_path(view):
    books = [
        _book(1, title="Real"),
        {"id": 2, "title": "Quebrado", "file_path": "/caminho/fantasma.epub"},
    ]
    view.load_books(books)

    view._on_broken_filter_toggled(True)
    assert [c._book_id for c in view._cards] == [2]

    view._on_broken_filter_toggled(False)
    assert len(view._cards) == 2

    # Um load_books idêntico ao original DEPOIS do rebuild do filtro ainda
    # usa o atalho (a última renderização foi exatamente essa lista).
    before = list(view._cards)
    view.load_books([dict(b) for b in books])
    assert view._cards == before
