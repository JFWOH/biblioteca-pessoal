"""Leitor de documentos EPUB."""

from pathlib import Path
from src.readers.base_reader import BaseReader, PageContent, TOCEntry


class EPUBReader(BaseReader):
    """Leitor EPUB com refluxo de texto e renderização HTML."""

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._book = None
        self._chapters: list[dict] = []  # {title, content_html}
        self.is_double_page = False

    def set_double_page(self, active: bool) -> None:
        """Ativa/Desativa o modo de leitura em página dupla."""
        self.is_double_page = active

    def open(self) -> None:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        self._book = epub.read_epub(str(self._filepath))
        self._chapters = []

        # Extrai capítulos na ordem da spine
        for item in self._book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            content = item.get_content().decode("utf-8", errors="replace")
            soup = BeautifulSoup(content, "html.parser")
            title = ""
            h_tag = soup.find(["h1", "h2", "h3"])
            if h_tag:
                title = h_tag.get_text(strip=True)
            if not title:
                title = item.get_name().split("/")[-1].replace(".xhtml", "").replace(".html", "")
            body = soup.find("body")
            html_content = str(body) if body else content
            if html_content.strip():
                self._chapters.append({"title": title, "content": html_content})

        self._total_pages = len(self._chapters)
        self._is_open = True

    def close(self) -> None:
        self._book = None
        self._chapters = []
        self._is_open = False

    def get_page(self, page_number: int) -> PageContent:
        if 0 <= page_number < len(self._chapters):
            chapter = self._chapters[page_number]
            content = chapter["content"]
            
            if self.is_double_page:
                script = "<script>document.head.insertAdjacentHTML('beforeend', '<style>body { column-count: 2; column-gap: 20px; height: 100vh; overflow-y: hidden; overflow-x: auto; }</style>');</script>"
                content += script
                
            return PageContent(
                page_number=page_number,
                total_pages=self._total_pages,
                content=content,
                content_type="html",
            )
        return PageContent(page_number=page_number, total_pages=self._total_pages,
                           content="", content_type="html")

    def get_toc(self) -> list[TOCEntry]:
        return [
            TOCEntry(title=ch["title"], page=i, level=0)
            for i, ch in enumerate(self._chapters)
        ]

    def search_text(self, query: str) -> list[dict]:
        from bs4 import BeautifulSoup
        results = []
        query_lower = query.lower()
        for i, chapter in enumerate(self._chapters):
            soup = BeautifulSoup(chapter["content"], "html.parser")
            text = soup.get_text()
            if query_lower in text.lower():
                # Encontra contexto
                idx = text.lower().index(query_lower)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(query) + 50)
                snippet = text[start:end].strip()
                results.append({
                    "page": i,
                    "chapter": chapter["title"],
                    "snippet": f"...{snippet}...",
                })
        return results

    def get_chapter_text(self, chapter_index: int) -> str:
        """Retorna texto puro de um capítulo."""
        if 0 <= chapter_index < len(self._chapters):
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self._chapters[chapter_index]["content"], "html.parser")
            return soup.get_text()
        return ""
