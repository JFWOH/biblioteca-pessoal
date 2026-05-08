"""Leitor de quadrinhos CBZ/CBR (Comic Book Archive)."""

import zipfile
import base64
from pathlib import Path

from src.readers.base_reader import BaseReader, PageContent, TOCEntry

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


class CBZReader(BaseReader):
    """Leitor de arquivos CBZ (ZIP) e CBR (RAR) de quadrinhos."""

    def __init__(self, filepath: str | Path):
        super().__init__(filepath)
        self._images: list[str] = []  # nomes dos arquivos de imagem ordenados
        self._archive = None

    def open(self) -> bool:
        """Abre o arquivo CBZ (ZIP)."""
        try:
            self._archive = zipfile.ZipFile(str(self._filepath), "r")
            # Filtra apenas imagens e ordena por nome
            self._images = sorted(
                name for name in self._archive.namelist()
                if Path(name).suffix.lower() in IMAGE_EXTENSIONS
                and not name.startswith("__MACOSX")
            )
            self._current_page = 0
            self._total_pages = len(self._images)
            self._is_open = self._total_pages > 0
            return self._is_open
        except (zipfile.BadZipFile, FileNotFoundError, PermissionError):
            self._is_open = False
            return False

    def close(self) -> None:
        if self._archive:
            self._archive.close()
            self._archive = None
        self._images = []
        self._current_page = 0
        self._total_pages = 0
        self._is_open = False

    def get_page(self, page_number: int) -> PageContent:
        """Retorna o conteúdo de uma página (imagem do quadrinho)."""
        if not self._archive or page_number < 0 or page_number >= self._total_pages:
            return PageContent(
                page_number=page_number,
                total_pages=self._total_pages,
                content="",
                content_type="html",
            )

        self._current_page = page_number
        img_name = self._images[page_number]

        try:
            image_data = self._archive.read(img_name)
            ext = Path(img_name).suffix.lstrip(".").lower()
            mime = f"image/{'jpeg' if ext in ('jpg', 'jpeg') else ext}"
            b64 = base64.b64encode(image_data).decode("ascii")

            html = f"""
            <div style="display:flex; justify-content:center; align-items:center;
                        min-height:100vh; background:#0f0f17; padding:0; margin:0;">
                <img src="data:{mime};base64,{b64}"
                     style="max-width:100%; max-height:100vh; object-fit:contain;"
                     alt="Página {page_number + 1} — {Path(img_name).name}"/>
            </div>
            """
            return PageContent(
                page_number=page_number,
                total_pages=self._total_pages,
                content=html,
                content_type="html",
            )
        except Exception:
            return PageContent(
                page_number=page_number,
                total_pages=self._total_pages,
                content=f"<p>Erro ao ler: {Path(img_name).name}</p>",
                content_type="html",
            )

    def get_toc(self) -> list[TOCEntry]:
        """Quadrinhos não possuem TOC — retorna lista de páginas agrupadas."""
        entries = []
        # Agrupa por diretório (volume/capítulo)
        dirs_seen = set()
        for i, name in enumerate(self._images):
            parent = str(Path(name).parent)
            if parent not in dirs_seen and parent != ".":
                dirs_seen.add(parent)
                label = Path(parent).name or f"Capítulo {len(dirs_seen)}"
                entries.append(TOCEntry(title=label, page=i, level=0))
        if not entries:
            # Sem diretórios — marca cada 10 páginas
            for i in range(0, len(self._images), 10):
                entries.append(TOCEntry(
                    title=f"Páginas {i+1}–{min(i+10, len(self._images))}",
                    page=i, level=0
                ))
        return entries

    def search_text(self, query: str) -> list[int]:
        """Quadrinhos não suportam busca textual."""
        return []

    def get_image_data(self, page_number: int) -> bytes | None:
        """Retorna os dados brutos da imagem de uma página."""
        if not self._archive or page_number < 0 or page_number >= self._total_pages:
            return None
        try:
            return self._archive.read(self._images[page_number])
        except Exception:
            return None

    def get_image_name(self, page_number: int) -> str:
        """Retorna o nome do arquivo de imagem de uma página."""
        if page_number < 0 or page_number >= len(self._images):
            return ""
        return self._images[page_number]
