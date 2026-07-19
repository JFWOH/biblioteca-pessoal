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

Rodada A4 (perf/gui): a reciclagem passou a CASAR os cards por ``book_id``
antes de reposicionar — em REORDENAÇÃO/filtro o card do MESMO livro é
reutilizado (curto-circuita ``update_book``, a CAPA não recarrega do disco);
só os livros novos pegam cards órfãos/novos. Os testes de resort afirmam a
identidade por id e a AUSÊNCIA de reconstrução de conteúdo.

Estes testes são FUNCIONAIS (identidade de objetos, estados visuais) — nunca
de tempo: medição de tempo fica fora da suíte, no script de profiling.
"""
import pytest

from src.gui.library_view import LibraryView
from src.gui.widgets.book_card import BookCard


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

def test_broken_filter_clears_selection_before_recycling(view):
    """Auditoria B4: o filtro de quebrados espelha o clear do load_books —
    sem isso a bulk bar ficaria armada ("Excluir selecionados") apontando
    para cards reciclados que não parecem selecionados."""
    books = [
        _book(1, title="Real"),
        {"id": 2, "title": "Quebrado", "file_path": "/caminho/fantasma.epub"},
    ]
    view.load_books(books)
    view._toggle_selection(1)
    assert not view._bulk_bar.isHidden()

    view._on_broken_filter_toggled(True)  # recicla para a lista filtrada

    assert view._selected_ids == set()
    assert view._bulk_bar.isHidden()
    assert all(not c.is_selected for c in view._cards)


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


# ── Rodada A4: casamento por book_id (capas sobrevivem ao resort) ───────────

def test_resort_preserves_card_identity_by_id(view):
    """Reordenar os MESMOS livros reutiliza o card de cada livro (mesmo objeto),
    apenas reposicionado — não recria/reconfigura por posição."""
    books = [_book(1), _book(2), _book(3)]
    view.load_books(books)
    by_id = {c._book_id: c for c in view._cards}

    view.load_books([dict(b) for b in reversed(books)])  # ordem 3, 2, 1

    assert [c._book_id for c in view._cards] == [3, 2, 1]
    assert view._cards[0] is by_id[3]
    assert view._cards[1] is by_id[2]
    assert view._cards[2] is by_id[1]


def test_resort_does_not_rebuild_card_contents(view, monkeypatch):
    """Capa (e todo o conteúdo do card) NÃO é reconstruída no resort: o card do
    mesmo id curto-circuita em ``update_book`` ANTES de ``_build_contents`` — a
    carga/escala do QPixmap (parte mais cara do card) é evitada."""
    books = [_book(1), _book(2), _book(3)]
    view.load_books(books)

    calls = {"n": 0}
    original = BookCard._build_contents

    def counting(self):
        calls["n"] += 1
        return original(self)

    # Só conta reconstruções DEPOIS da carga inicial (o __init__ já construiu).
    monkeypatch.setattr(BookCard, "_build_contents", counting)

    view.load_books([dict(b) for b in reversed(books)])  # resort puro

    assert calls["n"] == 0, "resort não deve reconstruir o conteúdo dos cards"


def test_orphan_card_reused_for_new_book_preserving_matched(view):
    """Livro sem card correspondente pega um card ÓRFÃO (o do livro que saiu),
    enquanto os cards dos livros que permaneceram são preservados por id."""
    view.load_books([_book(1), _book(2), _book(3)])
    by_id = {c._book_id: c for c in view._cards}
    orphan = by_id[2]  # o livro 2 sai da lista; seu card fica órfão

    view.load_books([_book(1), _book(4), _book(3)])  # 4 é novo, no lugar de 2

    assert view._cards[0] is by_id[1]      # casado por id
    assert view._cards[2] is by_id[3]      # casado por id
    assert view._cards[1] is orphan        # órfão reaproveitado (não recriado)
    assert view._cards[1]._book_id == 4    # agora renderiza o livro novo
    assert len(view._cards) == 3


def test_resort_clears_selection_via_load_books(view):
    """``load_books`` limpa a seleção antes de reordenar (troca o conjunto do
    ponto de vista da view) — nenhum card fica selecionado após o resort."""
    books = [_book(1), _book(2), _book(3)]
    view.load_books(books)
    view._toggle_selection(2)
    assert not view._bulk_bar.isHidden()

    view.load_books([dict(b) for b in reversed(books)])

    assert view._selected_ids == set()
    assert all(not c.is_selected for c in view._cards)
    assert view._bulk_bar.isHidden()


def test_reflow_preserves_visual_selection_of_reused_card(view):
    """Reflow (resize) NÃO limpa ``_selected_ids``; o card do MESMO id continua
    legitimamente selecionado — o visual, zerado por ``update_book``, é
    re-sincronizado por ``_refresh_grid``."""
    view.load_books([_book(1), _book(2)])
    view._toggle_selection(1)
    assert view._card_by_id(1).is_selected

    # Simula o reflow do resizeEvent com mudança de colunas (força o re-grid),
    # sem limpar _selected_ids — mesmos livros, mesma ordem.
    view._grid_cols = 999
    view._refresh_grid([c.book_data for c in view._cards])

    assert view._selected_ids == {1}
    assert view._card_by_id(1).is_selected
    assert not view._card_by_id(2).is_selected
