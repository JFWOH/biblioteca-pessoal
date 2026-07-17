"""Tarefa 2.2 — prateleira "Continuar lendo".

Duas frentes:
1. Consulta pura de DB ``LibraryDB.get_in_progress_books`` (tmp_path), cobrindo
   sem-progresso, progresso ordenado por ``last_read`` e exclusão de terminados.
2. Widget ``LibraryView.load_continue_reading`` / ``_ContinueReadingCard``:
   mostra/esconde a faixa e reencaminha os sinais de clique/duplo-clique.
"""
import pytest

from src.core.database import LibraryDB
from src.gui.library_view import LibraryView, _ContinueReadingCard


# ── DB: get_in_progress_books ──────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "lib.db")
    yield database
    database.close()


def _add_book(db, title):
    return db.add_book(
        title=title, file_path=f"/tmp/{title}.pdf", file_format="pdf")


def _set_progress(db, book_id, percentage, current_page, total_pages, last_read):
    """Insere/atualiza reading_progress com valores explícitos (inclui last_read)."""
    with db._write_lock:
        db.conn.execute(
            """INSERT INTO reading_progress
                   (book_id, current_page, total_pages, percentage, last_read)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(book_id) DO UPDATE SET
                   current_page=excluded.current_page,
                   total_pages=excluded.total_pages,
                   percentage=excluded.percentage,
                   last_read=excluded.last_read""",
            (book_id, current_page, total_pages, percentage, last_read))
        db.conn.commit()


def test_no_progress_returns_empty(db):
    _add_book(db, "Sem leitura")
    assert db.get_in_progress_books() == []


def test_in_progress_ordered_by_last_read_desc(db):
    b1 = _add_book(db, "Antigo")
    b2 = _add_book(db, "Meio")
    b3 = _add_book(db, "Recente")
    _set_progress(db, b1, 10.0, 1, 10, "2026-07-16 08:00:00")
    _set_progress(db, b2, 50.0, 5, 10, "2026-07-16 09:00:00")
    _set_progress(db, b3, 80.0, 8, 10, "2026-07-16 10:00:00")

    result = db.get_in_progress_books()
    assert [r["id"] for r in result] == [b3, b2, b1]


def test_finished_and_unstarted_excluded(db):
    started = _add_book(db, "Iniciado")
    finished_exact = _add_book(db, "Terminado 99.5")
    finished_over = _add_book(db, "Terminado 100")
    unstarted = _add_book(db, "Zero")

    _set_progress(db, started, 50.0, 5, 10, "2026-07-16 09:00:00")
    _set_progress(db, finished_exact, 99.5, 199, 200, "2026-07-16 09:10:00")
    _set_progress(db, finished_over, 100.0, 200, 200, "2026-07-16 09:20:00")
    _set_progress(db, unstarted, 0.0, 0, 300, "2026-07-16 09:30:00")

    ids = {r["id"] for r in db.get_in_progress_books()}
    assert ids == {started}


def test_dict_carries_progress_and_book_fields(db):
    bid = _add_book(db, "Com dados")
    _set_progress(db, bid, 42.0, 42, 100, "2026-07-16 11:00:00")

    row = db.get_in_progress_books()[0]
    # Campos do livro
    assert row["id"] == bid
    assert row["title"] == "Com dados"
    # Campos do progresso necessários ao card compacto
    assert row["percentage"] == 42.0
    assert row["current_page"] == 42
    assert row["total_pages"] == 100
    assert row["last_read"] == "2026-07-16 11:00:00"


def test_limit_is_respected(db):
    for i in range(5):
        bid = _add_book(db, f"Livro {i}")
        _set_progress(db, bid, 20.0, 2, 10, f"2026-07-16 10:0{i}:00")
    assert len(db.get_in_progress_books(limit=3)) == 3


# ── Widget: prateleira em LibraryView ──────────────────────────────────────

@pytest.fixture
def view(qtbot):
    v = LibraryView()
    qtbot.addWidget(v)
    return v


def _sample_books():
    return [
        {"id": 1, "title": "Alfa", "percentage": 30.0,
         "current_page": 3, "total_pages": 10},
        {"id": 2, "title": "Beta", "percentage": 60.0,
         "current_page": 6, "total_pages": 10},
    ]


def test_shelf_shows_cards_when_populated(view):
    assert view._continue_widget.isHidden()  # começa escondida

    view.load_continue_reading(_sample_books())
    assert len(view._continue_cards) == 2
    assert not view._continue_widget.isHidden()


def test_shelf_hides_and_clears_when_empty(view):
    view.load_continue_reading(_sample_books())
    view.load_continue_reading([])
    assert view._continue_cards == []
    assert view._continue_widget.isHidden()


def test_shelf_reloads_replace_previous_cards(view):
    view.load_continue_reading(_sample_books())
    view.load_continue_reading([_sample_books()[0]])
    assert len(view._continue_cards) == 1


def test_card_click_signals_route_to_view(view):
    view.load_continue_reading([_sample_books()[1]])  # id=2
    card = view._continue_cards[0]

    selected, opened = [], []
    view.book_selected.connect(selected.append)
    view.book_open.connect(opened.append)

    card.clicked.emit(2)
    card.double_clicked.emit(2)

    assert selected == [2]
    assert opened == [2]


def test_card_meta_text_shows_percentage_and_pages(qtbot):
    card = _ContinueReadingCard(
        {"id": 9, "title": "T", "percentage": 33.7,
         "current_page": 5, "total_pages": 15})
    qtbot.addWidget(card)
    assert card._book_id == 9
    assert _ContinueReadingCard._meta_text(
        {"current_page": 5, "total_pages": 15}, 34) == "34% · pág. 5/15"
    assert _ContinueReadingCard._meta_text({}, 34) == "34%"
