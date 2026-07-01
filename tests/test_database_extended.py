"""Testes do módulo database — cobertura ampliada para coleções e tags."""

import pytest

from src.core.database import LibraryDB


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "test.db")


@pytest.fixture
def db_with_book(db):
    book_id = db.add_book(
        title="Livro Teste",
        author="Autor",
        file_path="/tmp/test.pdf",
        file_format="pdf",
    )
    return db, book_id


class TestCollections:
    def test_create_collection(self, db):
        cid = db.create_collection("Ficção Científica")
        assert cid > 0

    def test_get_all_collections(self, db):
        db.create_collection("Col A")
        db.create_collection("Col B")
        cols = db.get_all_collections()
        assert len(cols) == 2
        names = {c["name"] for c in cols}
        assert "Col A" in names
        assert "Col B" in names

    def test_rename_collection(self, db):
        cid = db.create_collection("Antigo")
        db.rename_collection(cid, "Novo Nome")
        cols = db.get_all_collections()
        assert cols[0]["name"] == "Novo Nome"

    def test_delete_collection(self, db):
        cid = db.create_collection("Para Deletar")
        db.delete_collection(cid)
        assert len(db.get_all_collections()) == 0

    def test_add_book_to_collection(self, db_with_book):
        db, book_id = db_with_book
        cid = db.create_collection("Favoritos")
        db.add_book_to_collection(book_id, cid)
        books = db.get_books_in_collection(cid)
        assert len(books) == 1
        assert books[0]["id"] == book_id

    def test_get_book_collections(self, db_with_book):
        db, book_id = db_with_book
        c1 = db.create_collection("Col A")
        c2 = db.create_collection("Col B")
        db.add_book_to_collection(book_id, c1)
        db.add_book_to_collection(book_id, c2)
        cols = db.get_book_collections(book_id)
        assert len(cols) == 2

    def test_remove_book_from_collection(self, db_with_book):
        db, book_id = db_with_book
        cid = db.create_collection("Temp")
        db.add_book_to_collection(book_id, cid)
        db.remove_book_from_collection(book_id, cid)
        assert len(db.get_books_in_collection(cid)) == 0

    def test_duplicate_add_ignored(self, db_with_book):
        db, book_id = db_with_book
        cid = db.create_collection("Uniq")
        db.add_book_to_collection(book_id, cid)
        db.add_book_to_collection(book_id, cid)  # duplicata — ignorada
        assert len(db.get_books_in_collection(cid)) == 1


class TestTags:
    def test_create_tag(self, db):
        tid = db.create_tag("Fantasia", "#ef4444")
        assert tid > 0

    def test_get_all_tags(self, db):
        db.create_tag("Tag A")
        db.create_tag("Tag B")
        tags = db.get_all_tags()
        assert len(tags) == 2

    def test_add_tag_to_book(self, db_with_book):
        db, book_id = db_with_book
        tid = db.create_tag("Sci-Fi")
        db.add_tag_to_book(book_id, tid)
        tags = db.get_book_tags(book_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "Sci-Fi"

    def test_remove_tag_from_book(self, db_with_book):
        db, book_id = db_with_book
        tid = db.create_tag("Temp")
        db.add_tag_to_book(book_id, tid)
        db.remove_tag_from_book(book_id, tid)
        assert len(db.get_book_tags(book_id)) == 0

    def test_duplicate_tag_ignored(self, db_with_book):
        db, book_id = db_with_book
        tid = db.create_tag("Uniq")
        db.add_tag_to_book(book_id, tid)
        db.add_tag_to_book(book_id, tid)
        assert len(db.get_book_tags(book_id)) == 1

    def test_tag_colors(self, db):
        tid = db.create_tag("Vermelho", "#ff0000")
        tags = db.get_all_tags()
        assert tags[0]["color"] == "#ff0000"


class TestDatabaseEdgeCases:
    def test_filter_by_rating(self, db):
        db.add_book(title="3 Stars", author="A", file_path="/a.pdf",
                    file_format="pdf", rating=3)
        db.add_book(title="5 Stars", author="B", file_path="/b.pdf",
                    file_format="pdf", rating=5)
        db.add_book(title="1 Star", author="C", file_path="/c.pdf",
                    file_format="pdf", rating=1)
        results = db.filter_books(min_rating=3)
        assert len(results) == 2
        titles = {r["title"] for r in results}
        assert "1 Star" not in titles

    def test_filter_by_author(self, db):
        db.add_book(title="Book A", author="George Orwell", file_path="/d.pdf",
                    file_format="pdf")
        db.add_book(title="Book B", author="Isaac Asimov", file_path="/e.pdf",
                    file_format="pdf")
        results = db.filter_books(author="Orwell")
        assert len(results) == 1
        assert results[0]["author"] == "George Orwell"

    def test_unique_authors(self, db):
        db.add_book(title="B1", author="Autor X", file_path="/f.pdf", file_format="pdf")
        db.add_book(title="B2", author="Autor X", file_path="/g.pdf", file_format="pdf")
        db.add_book(title="B3", author="Autor Y", file_path="/h.pdf", file_format="pdf")
        authors = db.get_unique_authors()
        assert len(authors) == 2
        assert "Autor X" in authors
        assert "Autor Y" in authors

    def test_context_manager(self, tmp_path):
        with LibraryDB(tmp_path / "ctx.db") as db:
            db.add_book(title="Ctx", author="A", file_path="/ctx.pdf", file_format="pdf")
            assert db.count_books() == 1
        # After exit, connection is closed
        assert getattr(db._local, "conn", None) is None
