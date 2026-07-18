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


class TestExportTiposDaIAETiposDesconhecidos:
    """Regressão do relato real (2026-07-18): livro só com anotações da IA
    exportava o cabeçalho ("Total: 2 anotações") e corpo VAZIO — os tipos
    ai_note/ai_bookmark não estavam no dicionário de seções."""

    @pytest.fixture
    def db_ai(self, tmp_path):
        db = LibraryDB(tmp_path / "ai.db")
        book_id = db.add_book(
            title="Livro IA", author="A", file_path=str(tmp_path / "a.pdf"),
            file_format="pdf",
        )
        db.add_annotation(
            book_id=book_id, page_number=10,
            content="Explicação gerada pela IA\ncom segunda linha",
            highlight_color="", annotation_type="ai_note",
        )
        db.add_annotation(
            book_id=book_id, page_number=20, content="Ponto marcado pela IA",
            highlight_color="", annotation_type="ai_bookmark",
        )
        return db, book_id

    def test_conteudo_de_ai_note_e_ai_bookmark_aparece_no_corpo(self, db_ai, tmp_path):
        db, book_id = db_ai
        out = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = out.read_text(encoding="utf-8")
        assert "Explicação gerada pela IA" in content
        assert "Ponto marcado pela IA" in content
        assert "Notas da IA" in content
        assert "Marcadores da IA" in content

    def test_total_do_cabecalho_bate_com_o_corpo(self, db_ai, tmp_path):
        db, book_id = db_ai
        out = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = out.read_text(encoding="utf-8")
        assert "**Total:** 2 anotações" in content
        assert content.count("### Página") == 2

    def test_conteudo_multilinha_vira_blockquote_completo(self, db_ai, tmp_path):
        db, book_id = db_ai
        out = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = out.read_text(encoding="utf-8")
        assert "> com segunda linha" in content

    def test_tipo_desconhecido_futuro_nao_e_descartado(self, tmp_path):
        db = LibraryDB(tmp_path / "x.db")
        book_id = db.add_book(
            title="Livro X", author="A", file_path=str(tmp_path / "x.pdf"),
            file_format="pdf",
        )
        db.add_annotation(
            book_id=book_id, page_number=1, content="Conteúdo tipo novo",
            highlight_color="", annotation_type="tipo_futuro",
        )
        out = export_annotations_markdown(db, book_id, tmp_path / "out.md")
        content = out.read_text(encoding="utf-8")
        assert "Conteúdo tipo novo" in content
        assert "Outras" in content
