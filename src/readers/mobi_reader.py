"""Leitor de documentos MOBI/AZW (stub — conversão para EPUB internamente)."""

from pathlib import Path
from src.readers.base_reader import BaseReader, PageContent, TOCEntry


class MOBIReader(BaseReader):
    """Leitor MOBI — implementação futura via conversão para EPUB."""

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._content = ""

    def open(self) -> None:
        # Leitura básica como texto — extração completa requer KindleUnpack
        try:
            with open(self._filepath, "rb") as f:
                raw = f.read()
            # Tenta decodificar o que for possível
            self._content = raw.decode("utf-8", errors="replace")
        except Exception:
            self._content = "[Formato MOBI requer plugin adicional]"
        self._total_pages = 1
        self._is_open = True

    def close(self) -> None:
        self._content = ""
        self._is_open = False

    def get_page(self, page_number: int) -> PageContent:
        return PageContent(
            page_number=0, total_pages=1,
            content=f"<p>{self._content[:5000]}</p>",
            content_type="html",
        )

    def get_toc(self) -> list[TOCEntry]:
        return []

    def search_text(self, query: str) -> list[dict]:
        return []
