"""Tarefa 2.1 — overlay de % de progresso nos cards.

Duas frentes:
1. ``LibraryDB.get_progress_map`` — consulta em lote (book_id -> percentage),
   a base para os cards evitarem N+1 (uma consulta por card seria inaceitável).
2. ``BookCard`` — a barra fina de progresso só aparece quando percentage > 0,
   e não interfere no badge de "quebrado" existente.
"""
import pytest

from src.core.database import LibraryDB
from src.gui.widgets.book_card import BookCard


# ── DB: get_progress_map ────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "lib.db")
    yield database
    database.close()


def _add_book(db, title):
    return db.add_book(title=title, file_path=f"/tmp/{title}.pdf", file_format="pdf")


def test_progress_map_empty_when_no_progress(db):
    _add_book(db, "Sem leitura")
    assert db.get_progress_map() == {}


def test_progress_map_returns_all_books_in_one_query(db):
    b1 = _add_book(db, "Um")
    b2 = _add_book(db, "Dois")
    db.update_reading_progress(b1, current_page=5, total_pages=10)
    db.update_reading_progress(b2, current_page=2, total_pages=8)

    progress_map = db.get_progress_map()
    assert progress_map[b1] == pytest.approx(50.0)
    assert progress_map[b2] == pytest.approx(25.0)


def test_progress_map_excludes_untouched_books(db):
    b1 = _add_book(db, "Com progresso")
    _add_book(db, "Sem progresso")
    db.update_reading_progress(b1, current_page=1, total_pages=4)

    progress_map = db.get_progress_map()
    assert set(progress_map.keys()) == {b1}


# ── Widget: BookCard ─────────────────────────────────────────────────────────

def test_card_hides_progress_bar_when_zero(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__, "percentage": 0}
    card = BookCard(data)
    qtbot.addWidget(card)
    assert card._progress_bar is None


def test_card_hides_progress_bar_when_absent(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__}
    card = BookCard(data)
    qtbot.addWidget(card)
    assert card._progress_bar is None


def test_card_shows_progress_bar_when_positive(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__, "percentage": 42.0}
    card = BookCard(data)
    qtbot.addWidget(card)
    assert card._progress_bar is not None
    assert card._progress_bar.value() == 42
    assert card._progress_bar.objectName() == "bookCardProgress"


def test_card_progress_bar_clamped_to_100(qtbot):
    data = {"id": 1, "title": "Livro", "file_path": __file__, "percentage": 133.7}
    card = BookCard(data)
    qtbot.addWidget(card)
    assert card._progress_bar.value() == 100


def test_card_progress_coexists_with_broken_badge(qtbot):
    """Livro quebrado E com progresso: os dois indicadores aparecem juntos,
    sem um sobrescrever o outro (barra sob a capa; badge na linha de
    indicadores abaixo do título)."""
    data = {
        "id": 1, "title": "Livro", "file_path": "/fake/nao/existe.pdf",
        "percentage": 30.0,
    }
    card = BookCard(data)
    qtbot.addWidget(card)
    assert card.is_broken is True
    assert card._progress_bar is not None
    assert card._progress_bar.value() == 30
