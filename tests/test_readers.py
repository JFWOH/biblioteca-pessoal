"""Testes do módulo de leitores."""

import tempfile
from pathlib import Path

import pytest

from src.readers.base_reader import BaseReader, PageContent, TOCEntry
from src.readers.txt_reader import TXTReader
from src.readers.reader_factory import create_reader, get_supported_reader_formats


class TestTXTReader:
    """Testes para o leitor de texto."""

    def test_open_text_file(self, tmp_path):
        """Testa abertura de arquivo de texto."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello World\n" * 100, encoding="utf-8")

        reader = TXTReader(txt_file)
        reader.open()

        assert reader.is_open
        assert reader.total_pages >= 1

        page = reader.get_page(0)
        assert page is not None
        assert "Hello World" in page.content
        assert page.content_type == "html"

        reader.close()
        assert not reader.is_open

    def test_navigation(self, tmp_path):
        """Testa navegação entre páginas."""
        txt_file = tmp_path / "nav.txt"
        # Cria texto grande para ter múltiplas páginas
        txt_file.write_text("X" * 10000, encoding="utf-8")

        with TXTReader(txt_file) as reader:
            assert reader.current_page == 0

            next_page = reader.next_page()
            if reader.total_pages > 1:
                assert next_page is not None
                assert reader.current_page == 1

                reader.previous_page()
                assert reader.current_page == 0

    def test_search_text(self, tmp_path):
        """Testa busca dentro do texto."""
        txt_file = tmp_path / "search.txt"
        txt_file.write_text("Lorem ipsum dolor sit amet", encoding="utf-8")

        with TXTReader(txt_file) as reader:
            results = reader.search_text("ipsum")
            assert len(results) > 0
            assert results[0]["page"] == 0

    def test_markdown_toc(self, tmp_path):
        """Testa extração de TOC de markdown."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Chapter 1\nContent\n## Section 1.1\nMore", encoding="utf-8")

        with TXTReader(md_file) as reader:
            toc = reader.get_toc()
            assert len(toc) >= 1
            assert toc[0].title == "Chapter 1"

    def test_progress(self, tmp_path):
        """Testa cálculo de progresso."""
        txt_file = tmp_path / "progress.txt"
        txt_file.write_text("Test content", encoding="utf-8")

        with TXTReader(txt_file) as reader:
            progress = reader.get_progress()
            assert 0 <= progress <= 100


class TestReaderFactory:
    """Testes para a factory de leitores."""

    def test_create_txt_reader(self, tmp_path):
        """Testa criação de leitor TXT."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("content")
        reader = create_reader(txt_file)
        assert isinstance(reader, TXTReader)

    def test_supported_formats(self):
        """Testa lista de formatos suportados."""
        formats = get_supported_reader_formats()
        assert "pdf" in formats
        assert "epub" in formats
        assert "txt" in formats

    def test_fallback_reader(self, tmp_path):
        """Testa fallback para formato desconhecido."""
        file = tmp_path / "test.xyz"
        file.write_text("content")
        reader = create_reader(file)
        assert isinstance(reader, TXTReader)  # Fallback para texto


class TestPageContent:
    """Testes para o dataclass PageContent."""

    def test_page_content(self):
        page = PageContent(
            page_number=5, total_pages=100,
            content="<p>Test</p>", content_type="html",
        )
        assert page.page_number == 5
        assert page.total_pages == 100
        assert page.content_type == "html"

    def test_toc_entry(self):
        entry = TOCEntry(title="Chapter 1", page=0, level=0)
        assert entry.title == "Chapter 1"
        assert entry.children == []
