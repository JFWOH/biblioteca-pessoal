"""Tarefa 2.5 — menu de contexto (botão direito) nos cards.

``BookCard._build_context_menu``/``_handle_context_action`` são separados de
``contextMenuEvent`` justamente para serem testáveis sem chamar ``QMenu.exec()``
(que bloqueia esperando interação do usuário). Cobre:
1. Os 5 itens do menu (Abrir/Favoritar-Desfavoritar/Coleção/Metadados/Remover).
2. O rótulo de favoritar alterna conforme ``is_favorite``.
3. Cada ação emite ``context_action(book_id, "<ação>")``.
4. ``LibraryView`` repassa cada ação ao sinal correspondente (reaproveitando
   os MESMOS handlers que o MainWindow já conecta ao BookDetails).
"""
import pytest

from src.gui.widgets.book_card import BookCard
from src.gui.library_view import LibraryView


# ── BookCard: construção e roteamento do menu ───────────────────────────────

def test_menu_has_five_actions_not_favorited(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__, "is_favorite": 0}
    card = BookCard(data)
    qtbot.addWidget(card)

    menu = card._build_context_menu()
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert labels == [
        "📂 Abrir", "⭐ Favoritar", "📁 Adicionar à coleção…",
        "🌐 Buscar metadados", "🗑️ Remover",
    ]


def test_menu_shows_unfavorite_when_already_favorite(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__, "is_favorite": 1}
    card = BookCard(data)
    qtbot.addWidget(card)

    menu = card._build_context_menu()
    labels = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert "☆ Desfavoritar" in labels
    assert "⭐ Favoritar" not in labels


@pytest.mark.parametrize("action_attr,expected", [
    ("_ctx_open", "open"),
    ("_ctx_favorite", "favorite"),
    ("_ctx_collection", "collection"),
    ("_ctx_metadata", "fetch_metadata"),
    ("_ctx_delete", "delete"),
])
def test_each_menu_item_emits_expected_action(qtbot, action_attr, expected):
    data = {"id": 7, "title": "Livro", "file_path": __file__}
    card = BookCard(data)
    qtbot.addWidget(card)
    card._build_context_menu()

    with qtbot.waitSignal(card.context_action, timeout=1000) as blocker:
        card._handle_context_action(getattr(card, action_attr))
    assert blocker.args == [7, expected]


def test_no_action_chosen_emits_nothing(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__}
    card = BookCard(data)
    qtbot.addWidget(card)
    card._build_context_menu()

    received = []
    card.context_action.connect(lambda bid, action: received.append((bid, action)))
    card._handle_context_action(None)
    assert received == []


# ── LibraryView: roteamento das ações para os sinais públicos ──────────────

@pytest.fixture
def view(qtbot):
    v = LibraryView()
    qtbot.addWidget(v)
    return v


def test_open_action_routes_to_book_open(view, qtbot):
    with qtbot.waitSignal(view.book_open, timeout=1000) as blocker:
        view._on_card_context_action(5, "open")
    assert blocker.args == [5]


def test_favorite_action_routes_to_favorite_signal(view, qtbot):
    with qtbot.waitSignal(view.favorite_toggle_requested, timeout=1000) as blocker:
        view._on_card_context_action(5, "favorite")
    assert blocker.args == [5]


def test_collection_action_routes_to_collection_signal(view, qtbot):
    with qtbot.waitSignal(view.add_to_collection_requested, timeout=1000) as blocker:
        view._on_card_context_action(5, "collection")
    assert blocker.args == [5]


def test_metadata_action_routes_to_metadata_signal(view, qtbot):
    with qtbot.waitSignal(view.fetch_metadata_requested, timeout=1000) as blocker:
        view._on_card_context_action(5, "fetch_metadata")
    assert blocker.args == [5]


def test_delete_action_routes_to_delete_signal(view, qtbot):
    with qtbot.waitSignal(view.delete_requested, timeout=1000) as blocker:
        view._on_card_context_action(5, "delete")
    assert blocker.args == [5]


def test_card_context_action_wired_when_loaded_via_grid(view, qtbot):
    """Card criado por load_books já vem com context_action conectado —
    dispará-lo deve chegar até o sinal público da LibraryView."""
    view.load_books([{"id": 3, "title": "Livro", "file_path": __file__}])
    card = view._cards[0]

    with qtbot.waitSignal(view.delete_requested, timeout=1000) as blocker:
        card.context_action.emit(3, "delete")
    assert blocker.args == [3]
