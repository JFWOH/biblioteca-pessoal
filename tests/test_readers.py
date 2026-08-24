"""Testes do módulo de leitores."""

import ast
from pathlib import Path

import pytest

from src.readers.base_reader import PageContent, TOCEntry
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


class TestFronteiraADR006:
    """ADR-006: ``src/readers/**`` devolve dados puros — Qt só na GUI.

    Até a Onda P (ago/2026), ``PDFReader.get_page`` importava PyQt6 no corpo do
    método para montar a página dupla com QImage/QPainter. A composição passou
    a ser feita em PyMuPDF e a conversão para ``QPixmap`` ficou onde já estava:
    em ``src/gui/reader_view.py``.
    """

    PROIBIDOS = ("PyQt6", "PySide2", "PySide6", "src.gui")

    @staticmethod
    def _imports(node):
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom):
            return [node.module or ""]
        return []

    def _checa(self, caminho: Path):
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for node in ast.walk(arvore):  # walk: pega import DENTRO de função também
            for mod in self._imports(node):
                for banido in self.PROIBIDOS:
                    assert not (mod == banido or mod.startswith(banido + ".")), (
                        f"{caminho.name}: import proibido pela ADR-006: {mod}")

    def test_pdf_reader_sem_pyqt6(self):
        self._checa(Path(__file__).resolve().parent.parent
                    / "src" / "readers" / "pdf_reader.py")

    def test_nenhum_leitor_importa_gui(self):
        readers_dir = Path(__file__).resolve().parent.parent / "src" / "readers"
        arquivos = list(readers_dir.rglob("*.py"))
        assert arquivos, "src/readers vazio?"
        for f in arquivos:
            self._checa(f)


class TestPaginaDuplaPDF:
    """A composição lado a lado (antes QImage/QPainter, agora PyMuPDF)."""

    @staticmethod
    def _pdf(tmp_path, paginas=2, largura=200, altura=300):
        fitz = pytest.importorskip("fitz")
        caminho = tmp_path / "duplo.pdf"
        doc = fitz.open()
        for _ in range(paginas):
            doc.new_page(width=largura, height=altura)
        doc.save(str(caminho))
        doc.close()
        return caminho

    def test_pagina_dupla_junta_as_duas_lado_a_lado(self, tmp_path):
        from src.readers.pdf_reader import PDFReader

        reader = PDFReader(self._pdf(tmp_path))
        reader.open()
        simples = reader.get_page(0)
        reader.set_double_page(True)
        dupla = reader.get_page(0)
        reader.close()

        assert dupla.content.startswith(b"\x89PNG")
        assert dupla.width == simples.width * 2
        assert dupla.height == simples.height

    def test_ultima_pagina_impar_cai_no_caminho_simples(self, tmp_path):
        from src.readers.pdf_reader import PDFReader

        reader = PDFReader(self._pdf(tmp_path, paginas=3))
        reader.open()
        reader.set_double_page(True)
        ultima = reader.get_page(2)  # não há página 3 para parear
        reader.close()

        assert ultima.content.startswith(b"\x89PNG")
