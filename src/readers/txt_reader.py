"""Leitor de documentos TXT e Markdown."""

from pathlib import Path
from src.readers.base_reader import BaseReader, PageContent, TOCEntry


class TXTReader(BaseReader):
    """Leitor de texto simples e Markdown com paginação."""

    CHARS_PER_PAGE = 3000  # Caracteres por página virtual

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._text = ""
        self._pages: list[str] = []
        self._is_markdown = False

    def open(self) -> None:
        self._is_markdown = self._filepath.suffix.lower() in (".md", ".markdown")

        # Tenta detectar encoding
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                self._text = self._filepath.read_text(encoding=enc)
                break
            except (UnicodeDecodeError, OSError):
                continue

        # Pagina o texto
        self._pages = []
        for i in range(0, len(self._text), self.CHARS_PER_PAGE):
            self._pages.append(self._text[i:i + self.CHARS_PER_PAGE])

        if not self._pages:
            self._pages = [""]

        self._total_pages = len(self._pages)
        self._is_open = True

    def close(self) -> None:
        self._text = ""
        self._pages = []
        self._is_open = False

    def get_page(self, page_number: int) -> PageContent:
        if 0 <= page_number < len(self._pages):
            text = self._pages[page_number]
            if self._is_markdown:
                try:
                    import markdown
                    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
                except ImportError:
                    html = f"<pre>{text}</pre>"
                return PageContent(
                    page_number=page_number, total_pages=self._total_pages,
                    content=html, content_type="html",
                )
            else:
                # Texto simples com tipografia agradável
                escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html = f'<div style="white-space: pre-wrap; font-family: Georgia, serif; '\
                       f'line-height: 1.8; font-size: 16px;">{escaped}</div>'
                return PageContent(
                    page_number=page_number, total_pages=self._total_pages,
                    content=html, content_type="html",
                )
        return PageContent(page_number=page_number, total_pages=self._total_pages,
                           content="", content_type="html")

    def get_toc(self) -> list[TOCEntry]:
        if not self._is_markdown:
            return []
        entries = []
        for i, line in enumerate(self._text.split("\n")):
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                # Calcula a página onde esse heading está
                char_pos = self._text.index(line)
                page = char_pos // self.CHARS_PER_PAGE
                entries.append(TOCEntry(title=title, page=page, level=level - 1))
        return entries

    def search_text(self, query: str) -> list[dict]:
        results = []
        query_lower = query.lower()
        for i, page_text in enumerate(self._pages):
            if query_lower in page_text.lower():
                idx = page_text.lower().index(query_lower)
                start = max(0, idx - 50)
                end = min(len(page_text), idx + len(query) + 50)
                results.append({
                    "page": i,
                    "snippet": f"...{page_text[start:end].strip()}...",
                })
        return results
