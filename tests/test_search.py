"""Testes do módulo de busca."""

import pytest

from src.core.database import LibraryDB
from src.core.search import SearchEngine


@pytest.fixture
def search_engine(tmp_path):
    db = LibraryDB(tmp_path / "test.db")
    # Popula com dados de teste
    db.add_book(title="Dom Casmurro", author="Machado de Assis",
                file_path="/dom.pdf", file_format="pdf", description="Romance brasileiro")
    db.add_book(title="Memórias Póstumas", author="Machado de Assis",
                file_path="/mem.epub", file_format="epub", description="Clássico da literatura")
    db.add_book(title="1984", author="George Orwell",
                file_path="/1984.pdf", file_format="pdf", description="Distopia")
    db.add_book(title="Python Fluente", author="Luciano Ramalho",
                file_path="/python.pdf", file_format="pdf", rating=5)
    engine = SearchEngine(db)
    yield engine
    db.close()


class TestSearchEngine:
    """Testes para o motor de busca."""

    def test_search_by_title(self, search_engine):
        results = search_engine.search("Casmurro")
        assert len(results) == 1
        assert results[0]["title"] == "Dom Casmurro"

    def test_search_by_author(self, search_engine):
        results = search_engine.search("Machado")
        assert len(results) == 2

    def test_search_empty_query(self, search_engine):
        results = search_engine.search("")
        assert len(results) == 4  # Todos

    def test_search_with_format_filter(self, search_engine):
        results = search_engine.search("", {"format": "epub"})
        assert len(results) == 1
        assert results[0]["file_format"] == "epub"

    def test_search_no_results(self, search_engine):
        results = search_engine.search("XYZNONEXISTENT")
        assert len(results) == 0

    def test_suggestions(self, search_engine):
        suggestions = search_engine.get_suggestions("Dom")
        assert len(suggestions) >= 1
        assert any("Dom" in s for s in suggestions)

    def test_suggestions_includes_authors(self, search_engine):
        suggestions = search_engine.get_suggestions("Machado")
        assert any("Machado" in s for s in suggestions)

    def test_suggestions_short_query(self, search_engine):
        suggestions = search_engine.get_suggestions("D")
        assert len(suggestions) == 0  # Muito curto
