"""Gerenciamento da biblioteca — importação, organização, manutenção."""

from pathlib import Path

from src.core.database import LibraryDB
from src.core.metadata import extract_metadata
from src.core.config import ConfigManager
from src.utils.file_utils import (
    get_file_extension, is_supported_format, calculate_file_hash,
    get_file_size, find_documents,
)
from src.utils.image_utils import save_cover_image, generate_placeholder_cover


class LibraryManager:
    """Gerencia a biblioteca de livros/documentos."""

    def __init__(self, db: LibraryDB, config: ConfigManager):
        self._db = db
        self._config = config

    @property
    def db(self) -> LibraryDB:
        return self._db

    def import_file(self, filepath: str | Path) -> tuple[dict | None, bool]:
        """Importa um único arquivo. Retorna (livro, eh_novo) ou (None, False)."""
        filepath = Path(filepath)
        if not filepath.exists() or not is_supported_format(filepath):
            return None, False

        # Verifica duplicata por caminho
        existing = self._db.get_book_by_path(str(filepath))
        if existing:
            return existing, False

        # Verifica duplicata por hash
        if self._config.get("import.detect_duplicates", True):
            file_hash = calculate_file_hash(filepath)
            dup = self._db.get_book_by_hash(file_hash)
            if dup:
                return dup, False  # Duplicata encontrada
        else:
            file_hash = ""

        # Extrai metadados
        meta = extract_metadata(filepath)

        # Salva no banco
        book_id = self._db.add_book(
            title=meta.title or filepath.stem,
            author=meta.author,
            isbn=meta.isbn,
            publisher=meta.publisher,
            year=meta.year,
            language=meta.language,
            description=meta.description,
            file_path=str(filepath),
            file_format=get_file_extension(filepath),
            file_size=get_file_size(filepath),
            file_hash=file_hash,
            page_count=meta.page_count,
        )

        # Salva capa
        cover_path = ""
        if meta.cover_data:
            try:
                cover_path = str(save_cover_image(meta.cover_data, book_id))
            except Exception:
                cover_path = str(generate_placeholder_cover(
                    meta.title, meta.author, book_id))
        else:
            cover_path = str(generate_placeholder_cover(
                meta.title, meta.author, book_id))

        self._db.update_book(book_id, cover_path=cover_path)

        return self._db.get_book(book_id), True

    def import_directory(self, directory: str | Path,
                         recursive: bool = True) -> list[dict]:
        """Importa todos os documentos de um diretório. Retorna lista apenas de *novos* importados."""
        documents = find_documents(directory, recursive)
        imported = []
        for doc_path in documents:
            book, is_new = self.import_file(doc_path)
            if book and is_new:
                imported.append(book)
        return imported

    def remove_book(self, book_id: int) -> bool:
        """Remove um livro da biblioteca (não apaga o arquivo)."""
        book = self._db.get_book(book_id)
        if not book:
            return False
        # Remove capa se existir
        cover = book.get("cover_path", "")
        if cover:
            p = Path(cover)
            if p.exists():
                p.unlink(missing_ok=True)
        self._db.delete_book(book_id)
        return True

    def toggle_favorite(self, book_id: int) -> bool:
        """Alterna o status de favorito. Retorna o novo estado."""
        book = self._db.get_book(book_id)
        if not book:
            return False
        new_state = 0 if book["is_favorite"] else 1
        self._db.update_book(book_id, is_favorite=new_state)
        return bool(new_state)

    def set_rating(self, book_id: int, rating: int) -> None:
        """Define a avaliação (0-5 estrelas)."""
        rating = max(0, min(5, rating))
        self._db.update_book(book_id, rating=rating)

    def get_library_stats(self) -> dict:
        """Retorna estatísticas da biblioteca."""
        return self._db.get_statistics()
