"""Leitor de documentos PDF usando PyMuPDF."""

from pathlib import Path
from src.readers.base_reader import BaseReader, PageContent, TOCEntry


class PDFReader(BaseReader):
    """Leitor de PDF com renderização de alta qualidade."""

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._doc = None
        self._zoom = 1.5  # Fator de zoom padrão

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, value: float):
        self._zoom = max(0.5, min(5.0, value))

    def open(self) -> None:
        import fitz
        self._doc = fitz.open(str(self._filepath))
        self._total_pages = self._doc.page_count
        self._is_open = True

    def close(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None
        self._is_open = False

    def get_page(self, page_number: int) -> PageContent:
        import fitz
        page = self._doc[page_number]
        mat = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return PageContent(
            page_number=page_number,
            total_pages=self._total_pages,
            content=pix.tobytes("png"),
            content_type="image",
            width=pix.width,
            height=pix.height,
        )

    def get_toc(self) -> list[TOCEntry]:
        if not self._doc:
            return []
        toc = self._doc.get_toc()
        return [
            TOCEntry(title=entry[1], page=entry[2] - 1, level=entry[0] - 1)
            for entry in toc
        ]

    def search_text(self, query: str) -> list[dict]:
        if not self._doc:
            return []
        results = []
        for page_num in range(self._total_pages):
            page = self._doc[page_num]
            instances = page.search_for(query)
            for rect in instances:
                results.append({
                    "page": page_num,
                    "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                    "text": query,
                })
        return results

    def get_page_text(self, page_number: int) -> str:
        """Retorna o texto puro de uma página."""
        if self._doc and 0 <= page_number < self._total_pages:
            return self._doc[page_number].get_text()
        return ""

    def get_page_links(self, page_number: int) -> list[dict]:
        """Retorna links encontrados na página."""
        if not self._doc or page_number >= self._total_pages:
            return []
        page = self._doc[page_number]
        links = []
        for link in page.get_links():
            links.append({
                "kind": link.get("kind"),
                "uri": link.get("uri", ""),
                "page": link.get("page", -1),
                "rect": [link["from"].x0, link["from"].y0,
                         link["from"].x1, link["from"].y1] if "from" in link else [],
            })
        return links
