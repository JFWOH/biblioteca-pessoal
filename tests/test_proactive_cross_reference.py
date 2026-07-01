"""Testes de format_cross_reference (conexão proativa com outros livros)."""
from src.core.proactive_cross_reference import format_cross_reference


def _hit(book_id, title, page0, dist):
    return {"metadata": {"book_id": book_id, "title": title, "page_number": page0}, "distance": dist}


def test_excludes_current_book():
    assert format_cross_reference([_hit(1, "Atual", 0, 0.1)], current_book_id=1) is None


def test_picks_best_other_book_and_formats():
    hits = [_hit(1, "Atual", 0, 0.05), _hit(2, "Outro", 4, 0.2), _hit(3, "Terceiro", 9, 0.7)]
    note = format_cross_reference(hits, current_book_id=1, min_similarity=0.5)
    assert note is not None
    assert "Outro" in note   # sim 0.8 é o melhor entre os outros livros
    assert "p. 5" in note    # page_number 4 + 1


def test_respects_min_similarity():
    assert format_cross_reference([_hit(2, "Fraco", 0, 0.9)], 1, min_similarity=0.5) is None


def test_none_when_empty_or_none():
    assert format_cross_reference([], 1) is None
    assert format_cross_reference(None, 1) is None


def test_ignores_missing_or_bool_distance():
    assert format_cross_reference([{"metadata": {"book_id": 2, "title": "X", "page_number": 0}}], 1) is None
    assert format_cross_reference([{"metadata": {"book_id": 2}, "distance": True}], 1) is None
