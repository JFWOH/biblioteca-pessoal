"""Testes do módulo CBZ Reader."""

import zipfile
from pathlib import Path

import pytest

from src.readers.cbz_reader import CBZReader
from src.readers.reader_factory import create_reader


def _create_cbz(path: Path, images: dict[str, bytes]) -> Path:
    """Helper: cria um arquivo CBZ com imagens fake."""
    cbz_path = path / "test.cbz"
    with zipfile.ZipFile(str(cbz_path), "w") as zf:
        for name, data in images.items():
            zf.writestr(name, data)
    return cbz_path


# PNG mínimo válido (1x1 pixel, transparente)
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class TestCBZReader:
    def test_open_valid(self, tmp_path):
        cbz = _create_cbz(tmp_path, {
            "page_01.png": MINIMAL_PNG,
            "page_02.png": MINIMAL_PNG,
            "page_03.jpg": b"\xff\xd8\xff\xe0",
        })
        reader = CBZReader(cbz)
        assert reader.open() is True
        assert reader.total_pages == 3
        reader.close()

    def test_open_empty(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"readme.txt": b"not an image"})
        reader = CBZReader(cbz)
        assert reader.open() is False
        reader.close()

    def test_open_nonexistent(self, tmp_path):
        reader = CBZReader(tmp_path / "nope.cbz")
        assert reader.open() is False

    def test_page_navigation(self, tmp_path):
        cbz = _create_cbz(tmp_path, {
            "01.png": MINIMAL_PNG,
            "02.png": MINIMAL_PNG,
            "03.png": MINIMAL_PNG,
        })
        reader = CBZReader(cbz)
        reader.open()
        assert reader.current_page == 0

        page = reader.get_page(1)
        assert reader.current_page == 1
        assert page.content_type == "html"
        assert page.page_number == 1

        page = reader.get_page(2)
        assert reader.current_page == 2
        reader.close()

    def test_get_page_html(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"cover.png": MINIMAL_PNG})
        reader = CBZReader(cbz)
        reader.open()
        page = reader.get_page(0)
        assert "base64" in page.content
        assert "image/png" in page.content
        assert page.content_type == "html"
        reader.close()

    def test_get_page_out_of_range(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"p1.png": MINIMAL_PNG})
        reader = CBZReader(cbz)
        reader.open()
        page = reader.get_page(99)
        assert page.content == ""  # empty for out of range
        reader.close()

    def test_toc_with_directories(self, tmp_path):
        cbz = _create_cbz(tmp_path, {
            "Cap01/001.png": MINIMAL_PNG,
            "Cap01/002.png": MINIMAL_PNG,
            "Cap02/001.png": MINIMAL_PNG,
        })
        reader = CBZReader(cbz)
        reader.open()
        toc = reader.get_toc()
        assert len(toc) == 2
        assert toc[0].title == "Cap01"
        assert toc[1].title == "Cap02"
        reader.close()

    def test_toc_without_directories(self, tmp_path):
        cbz = _create_cbz(tmp_path, {
            f"page_{i:02d}.png": MINIMAL_PNG for i in range(25)
        })
        reader = CBZReader(cbz)
        reader.open()
        toc = reader.get_toc()
        # Sem diretórios, agrupa em blocos de 10
        assert len(toc) == 3  # 1-10, 11-20, 21-25
        reader.close()

    def test_search_returns_empty(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"p1.png": MINIMAL_PNG})
        reader = CBZReader(cbz)
        reader.open()
        assert reader.search_text("anything") == []
        reader.close()

    def test_get_image_data(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"img.png": MINIMAL_PNG})
        reader = CBZReader(cbz)
        reader.open()
        data = reader.get_image_data(0)
        assert data == MINIMAL_PNG
        assert reader.get_image_data(99) is None
        reader.close()

    def test_ignores_macosx(self, tmp_path):
        cbz = _create_cbz(tmp_path, {
            "__MACOSX/thumb.png": MINIMAL_PNG,
            "page.png": MINIMAL_PNG,
        })
        reader = CBZReader(cbz)
        reader.open()
        assert reader.total_pages == 1
        reader.close()

    def test_close_resets_state(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"p1.png": MINIMAL_PNG})
        reader = CBZReader(cbz)
        reader.open()
        assert reader.total_pages == 1
        reader.close()
        assert reader.total_pages == 0
        assert reader.current_page == 0


class TestReaderFactoryWithCBZ:
    def test_cbz_creates_cbz_reader(self, tmp_path):
        cbz = _create_cbz(tmp_path, {"p.png": MINIMAL_PNG})
        reader = create_reader(cbz)
        assert isinstance(reader, CBZReader)

    def test_cbr_creates_cbz_reader(self):
        # CBR criado via factory retorna CBZReader (que tenta abrir como ZIP)
        reader = create_reader("test.cbr")
        assert isinstance(reader, CBZReader)
