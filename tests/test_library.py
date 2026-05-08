"""Testes do módulo library (gerenciamento)."""

from pathlib import Path

import pytest

from src.core.database import LibraryDB
from src.core.config import ConfigManager
from src.core.library import LibraryManager


@pytest.fixture
def library(tmp_path):
    db = LibraryDB(tmp_path / "test.db")
    config = ConfigManager(tmp_path / "config.json")
    lib = LibraryManager(db, config)
    return lib, db, tmp_path


class TestLibraryManager:
    def test_import_txt_file(self, library):
        lib, db, tmp_path = library
        txt = tmp_path / "book.txt"
        txt.write_text("Este é o conteúdo do livro.", encoding="utf-8")
        result = lib.import_file(str(txt))
        assert result is not None
        assert db.count_books() == 1

    def test_import_duplicate_path_returns_existing(self, library):
        lib, db, tmp_path = library
        txt = tmp_path / "dup.txt"
        txt.write_text("Conteúdo.", encoding="utf-8")
        first = lib.import_file(str(txt))
        second = lib.import_file(str(txt))
        assert second is not None  # retorna o livro existente
        assert first["id"] == second["id"]
        assert db.count_books() == 1

    def test_import_nonexistent(self, library):
        lib, db, tmp_path = library
        result = lib.import_file(str(tmp_path / "nope.pdf"))
        assert result is None
        assert db.count_books() == 0

    def test_import_unsupported_format(self, library):
        lib, db, tmp_path = library
        f = tmp_path / "data.xyz"
        f.write_bytes(b"not supported")
        result = lib.import_file(str(f))
        assert result is None  # formato não suportado
        assert db.count_books() == 0

    def test_import_directory(self, library):
        lib, db, tmp_path = library
        (tmp_path / "books").mkdir()
        for i in range(3):
            (tmp_path / "books" / f"book_{i}.txt").write_text(f"Livro {i}", encoding="utf-8")
        imported = lib.import_directory(str(tmp_path / "books"))
        assert len(imported) == 3
        assert db.count_books() == 3

    def test_remove_book(self, library):
        lib, db, tmp_path = library
        txt = tmp_path / "remove.txt"
        txt.write_text("Para remover", encoding="utf-8")
        lib.import_file(str(txt))
        assert db.count_books() == 1
        books = db.get_all_books()
        lib.remove_book(books[0]["id"])
        assert db.count_books() == 0

    def test_toggle_favorite(self, library):
        lib, db, tmp_path = library
        txt = tmp_path / "fav.txt"
        txt.write_text("Favorito", encoding="utf-8")
        lib.import_file(str(txt))
        book = db.get_all_books()[0]
        assert book["is_favorite"] == 0
        lib.toggle_favorite(book["id"])
        book = db.get_book(book["id"])
        assert book["is_favorite"] == 1
        lib.toggle_favorite(book["id"])
        book = db.get_book(book["id"])
        assert book["is_favorite"] == 0
