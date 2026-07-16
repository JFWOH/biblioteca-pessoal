"""Testes do módulo database."""


import pytest

from src.core.database import LibraryDB


@pytest.fixture
def db(tmp_path):
    """Cria um banco de dados temporário para testes."""
    db_path = tmp_path / "test_library.db"
    database = LibraryDB(db_path)
    yield database
    database.close()


class TestLibraryDB:
    """Testes para o banco de dados da biblioteca."""

    def test_create_tables(self, db):
        """Verifica se as tabelas são criadas corretamente."""
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "books" in table_names
        assert "reading_progress" in table_names
        assert "collections" in table_names
        assert "tags" in table_names
        assert "annotations" in table_names

    def test_add_book(self, db):
        """Testa adição de livro."""
        book_id = db.add_book(
            title="Test Book",
            author="Test Author",
            file_path="/test/book.pdf",
            file_format="pdf",
        )
        assert book_id > 0
        book = db.get_book(book_id)
        assert book is not None
        assert book["title"] == "Test Book"
        assert book["author"] == "Test Author"
        assert book["read_status"] == "unread"

    def test_get_book_by_path(self, db):
        """Testa busca por caminho."""
        db.add_book(title="Book", file_path="/path/to/book.pdf", file_format="pdf")
        book = db.get_book_by_path("/path/to/book.pdf")
        assert book is not None
        assert book["title"] == "Book"

    def test_update_book(self, db):
        """Testa atualização de livro."""
        book_id = db.add_book(title="Old Title", file_path="/test.pdf", file_format="pdf")
        db.update_book(book_id, title="New Title", rating=5)
        book = db.get_book(book_id)
        assert book["title"] == "New Title"
        assert book["rating"] == 5

    def test_delete_book(self, db):
        """Testa remoção de livro."""
        book_id = db.add_book(title="To Delete", file_path="/del.pdf", file_format="pdf")
        db.delete_book(book_id)
        assert db.get_book(book_id) is None

    def test_count_books(self, db):
        """Testa contagem de livros."""
        assert db.count_books() == 0
        db.add_book(title="Book 1", file_path="/b1.pdf", file_format="pdf")
        db.add_book(title="Book 2", file_path="/b2.epub", file_format="epub")
        assert db.count_books() == 2

    def test_reading_progress(self, db):
        """Testa progresso de leitura."""
        book_id = db.add_book(title="Book", file_path="/b.pdf", file_format="pdf")
        db.update_reading_progress(book_id, current_page=50, total_pages=200)
        progress = db.get_reading_progress(book_id)
        assert progress is not None
        assert progress["current_page"] == 50
        assert progress["percentage"] == 25.0
        # Status deve mudar para "reading"
        book = db.get_book(book_id)
        assert book["read_status"] == "reading"

    def test_collections(self, db):
        """Testa criação e associação de coleções."""
        col_id = db.create_collection("Ficção Científica")
        book_id = db.add_book(title="Dune", file_path="/dune.epub", file_format="epub")
        db.add_book_to_collection(book_id, col_id)
        books = db.get_books_in_collection(col_id)
        assert len(books) == 1
        assert books[0]["title"] == "Dune"

    def test_tags(self, db):
        """Testa criação e associação de tags."""
        tag_id = db.create_tag("sci-fi", color="#3b82f6")
        book_id = db.add_book(title="Book", file_path="/b.pdf", file_format="pdf")
        db.add_tag_to_book(book_id, tag_id)
        tags = db.get_book_tags(book_id)
        assert len(tags) == 1
        assert tags[0]["name"] == "sci-fi"

    def test_annotations(self, db):
        """Testa anotações."""
        book_id = db.add_book(title="Book", file_path="/b.pdf", file_format="pdf")
        ann_id = db.add_annotation(book_id, page_number=10, content="Nota importante")
        annotations = db.get_annotations(book_id)
        assert len(annotations) == 1
        assert annotations[0]["content"] == "Nota importante"
        db.delete_annotation(ann_id)
        assert len(db.get_annotations(book_id)) == 0

    def test_search_fts(self, db):
        """Testa busca full-text."""
        db.add_book(title="Python Programming", author="Guido",
                     file_path="/python.pdf", file_format="pdf")
        db.add_book(title="Java Basics", author="James",
                     file_path="/java.pdf", file_format="pdf")
        results = db.search_books("Python")
        assert len(results) == 1
        assert results[0]["title"] == "Python Programming"

    def test_statistics(self, db):
        """Testa estatísticas."""
        db.add_book(title="B1", file_path="/1.pdf", file_format="pdf")
        db.add_book(title="B2", file_path="/2.epub", file_format="epub")
        stats = db.get_statistics()
        assert stats["total"] == 2
        assert stats["unread"] == 2
        assert "pdf" in stats["formats"]

    def test_filter_books(self, db):
        """Testa filtros."""
        db.add_book(title="PDF Book", file_path="/a.pdf", file_format="pdf", rating=5)
        db.add_book(title="EPUB Book", file_path="/b.epub", file_format="epub", rating=3)
        pdf_books = db.filter_books(format="pdf")
        assert len(pdf_books) == 1
        high_rated = db.filter_books(min_rating=4)
        assert len(high_rated) == 1


class TestAgentFeedback:
    """Feedback do agente: retorno de id, atualização de motivo e leitura recente."""

    def test_add_feedback_returns_increasing_ids(self, db):
        id1 = db.add_feedback(rating=-1, kind="answer", query="q1")
        id2 = db.add_feedback(rating=1, kind="answer", query="q2")
        assert isinstance(id1, int) and isinstance(id2, int)
        assert id2 > id1

    def test_set_reason_updates_existing_row(self, db):
        fid = db.add_feedback(rating=-1, kind="answer", query="q")
        db.set_agent_feedback_reason(fid, "resposta_errada")
        rows = db.get_recent_agent_feedback()
        match = [r for r in rows if r["id"] == fid]
        assert match and match[0]["reason"] == "resposta_errada"

    def test_set_reason_noop_on_missing_id(self, db):
        db.add_feedback(rating=-1, kind="answer", query="q")
        # id inexistente: no-op silencioso, sem exceção (ADR-005).
        db.set_agent_feedback_reason(999999, "resposta_errada")
        rows = db.get_recent_agent_feedback()
        assert all(r["reason"] != "resposta_errada" for r in rows)

    def test_get_recent_orders_desc_and_respects_limit(self, db):
        ids = [db.add_feedback(rating=-1, query=f"q{i}") for i in range(5)]
        rows = db.get_recent_agent_feedback(limit=3)
        assert len(rows) == 3
        # Mais recentes primeiro: ids em ordem decrescente.
        returned = [r["id"] for r in rows]
        assert returned == sorted(returned, reverse=True)
        assert returned[0] == ids[-1]

    def test_get_recent_exposes_expected_fields(self, db):
        db.add_feedback(rating=-1, kind="answer", query="pergunta",
                        book_id=None, page=7, reason="incompleta")
        row = db.get_recent_agent_feedback()[0]
        for field in ("id", "rating", "reason", "kind", "query",
                      "book_id", "page", "created_at"):
            assert field in row
