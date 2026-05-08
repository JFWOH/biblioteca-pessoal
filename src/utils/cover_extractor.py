"""Utilitários para extração de capas de documentos."""

from pathlib import Path
from io import BytesIO

from PIL import Image


def extract_cover_from_pdf(filepath: str | Path) -> bytes | None:
    """Extrai a capa (primeira página) de um arquivo PDF."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(filepath))
        if doc.page_count == 0:
            doc.close()
            return None

        page = doc[0]
        # Renderiza em resolução mais alta para qualidade
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        doc.close()
        return img_data
    except Exception:
        return None


def extract_cover_from_epub(filepath: str | Path) -> bytes | None:
    """Extrai a imagem de capa de um arquivo EPUB."""
    try:
        import ebooklib
        from ebooklib import epub

        book = epub.read_epub(str(filepath))

        # Tenta encontrar a capa nos metadados
        cover_id = None
        for meta in book.get_metadata("OPF", "cover"):
            if meta[1] and "content" in meta[1]:
                cover_id = meta[1]["content"]
                break

        # Busca pelo item de capa
        if cover_id:
            for item in book.get_items():
                if item.get_id() == cover_id:
                    return item.get_content()

        # Fallback: busca por nome de arquivo contendo "cover"
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            name = item.get_name().lower()
            if "cover" in name:
                return item.get_content()

        # Fallback: primeira imagem
        images = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
        if images:
            return images[0].get_content()

        return None
    except Exception:
        return None


def extract_cover(filepath: str | Path) -> bytes | None:
    """Extrai a capa de um documento baseado no formato."""
    ext = Path(filepath).suffix.lstrip(".").lower()

    if ext == "pdf":
        return extract_cover_from_pdf(filepath)
    elif ext == "epub":
        return extract_cover_from_epub(filepath)
    # MOBI, DOCX etc. — placeholder por enquanto
    return None
