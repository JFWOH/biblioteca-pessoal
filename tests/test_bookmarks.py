"""Testes da tabela e métodos de marcadores de página (bookmarks).

Testes puros de banco (sem Qt): a persistência dos marcadores vive no
``LibraryDB`` (core puro, ADR-006). Tabela própria com UNIQUE(book_id,
page_number) → múltiplos marcadores por livro, um por página.
"""
import pytest

from src.core.database import LibraryDB


@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "test_library.db")
    yield database
    database.close()


@pytest.fixture
def book_id(db):
    return db.add_book(title="Livro", file_path="/livro.pdf", file_format="pdf")


def test_bookmarks_table_exists(db):
    tables = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert "bookmarks" in {r["name"] for r in tables}


def test_add_and_get_bookmark(db, book_id):
    bid = db.add_bookmark(book_id, 3, label="Capítulo 2")
    assert bid > 0
    marks = db.get_bookmarks(book_id)
    assert len(marks) == 1
    assert marks[0]["page_number"] == 3
    assert marks[0]["label"] == "Capítulo 2"


def test_add_bookmark_is_idempotent(db, book_id):
    """UNIQUE(book_id, page_number): re-adicionar a mesma página é no-op."""
    first = db.add_bookmark(book_id, 5)
    second = db.add_bookmark(book_id, 5, label="ignorado")
    assert first == second
    assert len(db.get_bookmarks(book_id)) == 1


def test_is_bookmarked(db, book_id):
    assert db.is_bookmarked(book_id, 7) is False
    db.add_bookmark(book_id, 7)
    assert db.is_bookmarked(book_id, 7) is True


def test_remove_bookmark(db, book_id):
    db.add_bookmark(book_id, 2)
    db.remove_bookmark(book_id, 2)
    assert db.is_bookmarked(book_id, 2) is False
    assert db.get_bookmarks(book_id) == []


def test_toggle_bookmark_returns_final_state(db, book_id):
    assert db.toggle_bookmark(book_id, 4) is True   # criou
    assert db.is_bookmarked(book_id, 4) is True
    assert db.toggle_bookmark(book_id, 4) is False  # removeu
    assert db.is_bookmarked(book_id, 4) is False


def test_get_bookmarks_ordered_by_page(db, book_id):
    for p in (9, 1, 5):
        db.add_bookmark(book_id, p)
    pages = [m["page_number"] for m in db.get_bookmarks(book_id)]
    assert pages == [1, 5, 9]


def test_bookmarks_scoped_by_book(db):
    b1 = db.add_book(title="A", file_path="/a.pdf", file_format="pdf")
    b2 = db.add_book(title="B", file_path="/b.pdf", file_format="pdf")
    db.add_bookmark(b1, 1)
    db.add_bookmark(b2, 2)
    assert [m["page_number"] for m in db.get_bookmarks(b1)] == [1]
    assert [m["page_number"] for m in db.get_bookmarks(b2)] == [2]


def test_delete_book_removes_bookmarks(db, book_id):
    db.add_bookmark(book_id, 1)
    db.add_bookmark(book_id, 2)
    db.delete_book(book_id)
    assert db.get_bookmarks(book_id) == []
