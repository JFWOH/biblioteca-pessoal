"""Classe abstrata base para todos os leitores de documentos."""

from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass


@dataclass
class PageContent:
    """Conteúdo de uma página renderizada."""
    page_number: int
    total_pages: int
    content: bytes | str  # bytes para imagem, str para HTML/texto
    content_type: str  # "image", "html", "text"
    width: int = 0
    height: int = 0


@dataclass
class TOCEntry:
    """Entrada do sumário (Table of Contents)."""
    title: str
    page: int
    level: int = 0  # Nível de indentação (0 = capítulo, 1 = seção, etc.)
    children: list = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


class BaseReader(ABC):
    """Classe abstrata base para leitores de documentos."""

    def __init__(self, filepath: str | Path):
        self._filepath = Path(filepath)
        self._current_page = 0
        self._total_pages = 0
        self._is_open = False

    @property
    def filepath(self) -> Path:
        return self._filepath

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    @property
    def is_open(self) -> bool:
        return self._is_open

    @abstractmethod
    def open(self) -> None:
        """Abre o documento para leitura."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Fecha o documento e libera recursos."""
        ...

    @abstractmethod
    def get_page(self, page_number: int) -> PageContent:
        """Retorna o conteúdo de uma página específica."""
        ...

    @abstractmethod
    def get_toc(self) -> list[TOCEntry]:
        """Retorna o sumário do documento."""
        ...

    def render_thumbnail(self, page: int, width: int = 110) -> bytes | None:
        """Miniatura PNG da página (para o painel de sumário).

        Opcional: leitores sem renderização visual (EPUB/TXT) devolvem None e
        o sumário exibe apenas texto.
        """
        return None

    @abstractmethod
    def search_text(self, query: str) -> list[dict]:
        """Busca texto dentro do documento. Retorna lista com página e trecho."""
        ...

    def go_to_page(self, page_number: int) -> PageContent | None:
        """Navega para uma página específica."""
        if 0 <= page_number < self._total_pages:
            self._current_page = page_number
            return self.get_page(page_number)
        return None

    def next_page(self) -> PageContent | None:
        """Avança para a próxima página."""
        if self._current_page < self._total_pages - 1:
            self._current_page += 1
            return self.get_page(self._current_page)
        return None

    def previous_page(self) -> PageContent | None:
        """Volta para a página anterior."""
        if self._current_page > 0:
            self._current_page -= 1
            return self.get_page(self._current_page)
        return None

    def get_progress(self) -> float:
        """Retorna o progresso de leitura (0.0 a 100.0)."""
        if self._total_pages == 0:
            return 0.0
        return (self._current_page + 1) / self._total_pages * 100

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()
