"""Testes dos utilitários de arquivo."""

from pathlib import Path

from src.utils.file_utils import (
    get_file_extension, is_supported_format, format_file_size,
    find_documents, calculate_file_hash,
)


class TestFileUtils:
    """Testes para utilitários de arquivo."""

    def test_get_extension(self):
        assert get_file_extension("book.pdf") == "pdf"
        assert get_file_extension("book.EPUB") == "epub"
        assert get_file_extension(Path("/path/to/doc.docx")) == "docx"

    def test_is_supported(self):
        assert is_supported_format("book.pdf")
        assert is_supported_format("book.epub")
        assert is_supported_format("book.txt")
        assert not is_supported_format("book.exe")
        assert not is_supported_format("book.jpg")

    def test_format_size(self):
        assert format_file_size(500) == "500 B"
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1048576) == "1.0 MB"
        assert format_file_size(1073741824) == "1.0 GB"

    def test_find_documents(self, tmp_path):
        (tmp_path / "book.pdf").write_text("pdf")
        (tmp_path / "note.txt").write_text("txt")
        (tmp_path / "image.jpg").write_text("img")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "deep.epub").write_text("epub")

        docs = find_documents(tmp_path, recursive=True)
        exts = {d.suffix for d in docs}
        assert ".pdf" in exts
        assert ".txt" in exts
        assert ".epub" in exts
        assert ".jpg" not in exts

    def test_find_documents_non_recursive(self, tmp_path):
        (tmp_path / "book.pdf").write_text("pdf")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "deep.epub").write_text("epub")

        docs = find_documents(tmp_path, recursive=False)
        assert len(docs) == 1  # Apenas o pdf na raiz

    def test_file_hash(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h1 = calculate_file_hash(f)
        assert len(h1) == 64  # SHA-256 hex

        f2 = tmp_path / "test2.txt"
        f2.write_text("hello world")
        h2 = calculate_file_hash(f2)
        assert h1 == h2  # Mesmo conteúdo = mesmo hash

    def test_find_empty_dir(self, tmp_path):
        docs = find_documents(tmp_path)
        assert len(docs) == 0

    def test_find_nonexistent_dir(self):
        docs = find_documents("/nonexistent/path")
        assert len(docs) == 0
