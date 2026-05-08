"""Extração de metadados de documentos."""

from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class BookMetadata:
    """Metadados extraídos de um documento."""
    title: str = ""
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    year: int | None = None
    language: str = ""
    description: str = ""
    page_count: int = 0
    cover_data: bytes | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("cover_data", None)
        return {k: v for k, v in d.items() if v is not None and v != ""}


def extract_pdf_metadata(filepath: str | Path) -> BookMetadata:
    """Extrai metadados de um PDF usando PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(str(filepath))
        meta = doc.metadata or {}
        title = meta.get("title", "") or Path(filepath).stem
        author = meta.get("author", "")
        page_count = doc.page_count

        # Tenta extrair capa
        cover_data = None
        if page_count > 0:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            cover_data = pix.tobytes("png")

        doc.close()
        return BookMetadata(
            title=title, author=author, page_count=page_count,
            publisher=meta.get("producer", ""),
            description=meta.get("subject", ""),
            cover_data=cover_data,
        )
    except Exception as e:
        return BookMetadata(title=Path(filepath).stem)


def extract_epub_metadata(filepath: str | Path) -> BookMetadata:
    """Extrai metadados de um EPUB."""
    try:
        import ebooklib
        from ebooklib import epub
        book = epub.read_epub(str(filepath))

        title = ""
        for t in book.get_metadata("DC", "title"):
            title = t[0]; break
        title = title or Path(filepath).stem

        author = ""
        for a in book.get_metadata("DC", "creator"):
            author = a[0]; break

        description = ""
        for d in book.get_metadata("DC", "description"):
            description = d[0]; break

        language = ""
        for l in book.get_metadata("DC", "language"):
            language = l[0]; break

        publisher = ""
        for p in book.get_metadata("DC", "publisher"):
            publisher = p[0]; break

        isbn = ""
        for ident in book.get_metadata("DC", "identifier"):
            val = ident[0]
            if val and ("isbn" in val.lower() or len(val.replace("-", "")) in (10, 13)):
                isbn = val; break

        # Extrai capa
        cover_data = None
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            if "cover" in item.get_name().lower():
                cover_data = item.get_content(); break
        if not cover_data:
            imgs = list(book.get_items_of_type(ebooklib.ITEM_IMAGE))
            if imgs:
                cover_data = imgs[0].get_content()

        return BookMetadata(
            title=title, author=author, isbn=isbn, publisher=publisher,
            language=language, description=description, cover_data=cover_data,
        )
    except Exception:
        return BookMetadata(title=Path(filepath).stem)


def extract_docx_metadata(filepath: str | Path) -> BookMetadata:
    """Extrai metadados de um DOCX."""
    try:
        from docx import Document
        doc = Document(str(filepath))
        props = doc.core_properties
        return BookMetadata(
            title=props.title or Path(filepath).stem,
            author=props.author or "",
            description=props.comments or props.subject or "",
            language=props.language or "",
        )
    except Exception:
        return BookMetadata(title=Path(filepath).stem)


def extract_metadata(filepath: str | Path) -> BookMetadata:
    """Extrai metadados baseado no formato do arquivo."""
    ext = Path(filepath).suffix.lstrip(".").lower()
    extractors = {
        "pdf": extract_pdf_metadata,
        "epub": extract_epub_metadata,
        "docx": extract_docx_metadata,
    }
    extractor = extractors.get(ext)
    if extractor:
        return extractor(filepath)
    # Para formatos sem extrator, usa o nome do arquivo
    return BookMetadata(title=Path(filepath).stem)
