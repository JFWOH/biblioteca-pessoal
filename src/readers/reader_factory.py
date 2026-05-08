"""Factory para criação de leitores baseado no formato do arquivo."""

from pathlib import Path
from src.readers.base_reader import BaseReader
from src.readers.pdf_reader import PDFReader
from src.readers.epub_reader import EPUBReader
from src.readers.mobi_reader import MOBIReader
from src.readers.txt_reader import TXTReader
from src.readers.docx_reader import DOCXReader
from src.readers.cbz_reader import CBZReader
from src.utils.constants import (
    PDF_FORMATS, EPUB_FORMATS, MOBI_FORMATS, TEXT_FORMATS, DOCX_FORMATS,
    COMIC_FORMATS,
)


def create_reader(filepath: str | Path) -> BaseReader:
    """Cria o leitor apropriado baseado na extensão do arquivo."""
    ext = Path(filepath).suffix.lstrip(".").lower()

    if ext in PDF_FORMATS:
        return PDFReader(filepath)
    elif ext in EPUB_FORMATS:
        return EPUBReader(filepath)
    elif ext in MOBI_FORMATS:
        return MOBIReader(filepath)
    elif ext in TEXT_FORMATS:
        return TXTReader(filepath)
    elif ext in DOCX_FORMATS:
        return DOCXReader(filepath)
    elif ext in COMIC_FORMATS:
        return CBZReader(filepath)
    else:
        # Fallback para texto simples
        return TXTReader(filepath)


def get_supported_reader_formats() -> list[str]:
    """Retorna lista de formatos com leitor disponível."""
    return sorted(
        PDF_FORMATS | EPUB_FORMATS | MOBI_FORMATS | TEXT_FORMATS
        | DOCX_FORMATS | COMIC_FORMATS
    )
