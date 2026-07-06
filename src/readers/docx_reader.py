"""Leitor de documentos DOCX."""

from pathlib import Path
from src.readers.base_reader import BaseReader, PageContent, TOCEntry


class DOCXReader(BaseReader):
    """Leitor de documentos Word (.docx)."""

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._paragraphs: list[str] = []
        self._pages: list[str] = []

    def open(self) -> None:
        from docx import Document
        doc = Document(str(self._filepath))

        # Extrai parágrafos com formatação básica em HTML
        self._paragraphs = []
        for para in doc.paragraphs:
            style = para.style.name if para.style else ""
            text = para.text
            if not text.strip():
                self._paragraphs.append("<br>")
                continue

            if "Heading 1" in style:
                self._paragraphs.append(f"<h1>{text}</h1>")
            elif "Heading 2" in style:
                self._paragraphs.append(f"<h2>{text}</h2>")
            elif "Heading 3" in style:
                self._paragraphs.append(f"<h3>{text}</h3>")
            else:
                # Processa runs para bold/italic
                html_parts = []
                for run in para.runs:
                    t = run.text.replace("&", "&amp;").replace("<", "&lt;")
                    if run.bold and run.italic:
                        t = f"<b><i>{t}</i></b>"
                    elif run.bold:
                        t = f"<b>{t}</b>"
                    elif run.italic:
                        t = f"<i>{t}</i>"
                    html_parts.append(t)
                self._paragraphs.append(f"<p>{''.join(html_parts)}</p>")

        # Pagina (agrupando parágrafos)
        self._pages = []
        paras_per_page = 30
        for i in range(0, len(self._paragraphs), paras_per_page):
            page_html = "\n".join(self._paragraphs[i:i + paras_per_page])
            self._pages.append(page_html)

        if not self._pages:
            self._pages = ["<p>Documento vazio</p>"]

        self._total_pages = len(self._pages)
        self._is_open = True

    def close(self) -> None:
        self._paragraphs = []
        self._pages = []
        self._is_open = False

    def get_page(self, page_number: int) -> PageContent:
        if 0 <= page_number < len(self._pages):
            return PageContent(
                page_number=page_number, total_pages=self._total_pages,
                content=self._pages[page_number], content_type="html",
            )
        return PageContent(page_number=page_number, total_pages=self._total_pages,
                           content="", content_type="html")

    def get_toc(self) -> list[TOCEntry]:
        entries = []
        for i, p in enumerate(self._paragraphs):
            for level, tag in enumerate(["<h1>", "<h2>", "<h3>"]):
                if p.startswith(tag):
                    title = p.replace(tag, "").replace(tag.replace("<", "</"), "")
                    page = i // 30
                    entries.append(TOCEntry(title=title, page=page, level=level))
        return entries

    def search_text(self, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        results = []
        query_lower = query.lower()
        for i, page_html in enumerate(self._pages):
            soup = BeautifulSoup(page_html, "html.parser")
            text = soup.get_text()
            if query_lower in text.lower():
                idx = text.lower().index(query_lower)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(query) + 50)
                results.append({"page": i, "snippet": f"...{text[start:end].strip()}..."})
        return results
