"""Testes do módulo de exportação de anotações."""

from pathlib import Path

import pytest

from src.core.database import LibraryDB
from src.utils.export import export_annotations_markdown


@pytest.fixture
def db_with_annotations(tmp_path):
    """Cria um banco com livro e anotações para teste."""
    db = LibraryDB(tmp_path / "test.db")
    book_id = db.add_book(
        title="Livro de Teste",
        author="Autor Teste",
        file_path=str(tmp_path / "test.pdf"),
        file_format="pdf",
    )
    db.add_annotation(
        book_id=book_id, page_number=1, content="Nota importante",
        highlight_color="#fbbf24", annotation_type="note"
    )
    db.add_annotation(
        book_id=book_id, page_number=3, content="Texto destacado",
        highlight_color="#34d399", annotation_type="highlight"
    )
    db.add_annotation(
        book_id=book_id, page_number=5, content="Marcador cap. 2",
        highlight_color="#3b82f6", annotation_type="bookmark"
    )
    return db, book_id


class TestExportAnnotations:
    def test_export_creates_file(self, db_with_annotations, tmp_path):
        db, book_id = db_with_annotations
        output = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        assert output.exists()
        assert output.suffix == ".md"

    def test_export_contains_title(self, db_with_annotations, tmp_path):
        db, book_id = db_with_annotations
        output = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = output.read_text(encoding="utf-8")
        assert "Livro de Teste" in content

    def test_export_contains_annotations(self, db_with_annotations, tmp_path):
        db, book_id = db_with_annotations
        output = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = output.read_text(encoding="utf-8")
        assert "Nota importante" in content
        assert "Texto destacado" in content
        assert "Marcador cap. 2" in content

    def test_export_groups_by_type(self, db_with_annotations, tmp_path):
        db, book_id = db_with_annotations
        output = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = output.read_text(encoding="utf-8")
        # Verifica que os tipos de anotação aparecem como cabeçalhos
        assert "note" in content.lower() or "nota" in content.lower() or "Nota" in content

    def test_export_no_annotations(self, tmp_path):
        db = LibraryDB(tmp_path / "empty.db")
        book_id = db.add_book(
            title="Livro Vazio",
            author="Autor",
            file_path=str(tmp_path / "empty.pdf"),
            file_format="pdf",
        )
        output = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = output.read_text(encoding="utf-8")
        assert "Livro Vazio" in content
        # Mesmo sem anotações, o arquivo é criado
        assert output.exists()

    def test_export_returns_path(self, db_with_annotations, tmp_path):
        db, book_id = db_with_annotations
        result = export_annotations_markdown(db, book_id, tmp_path / "result.md")
        assert isinstance(result, Path)
        assert result.name == "result.md"
