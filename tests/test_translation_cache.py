"""Testes do cache de tradução por página (tarefa 3.5).

Mesmo padrão do cache de síntese do dossiê (dossier_synthesis_cache):
fingerprint (sha256 do texto normalizado) valida o cache — se o texto da
página mudou, a tradução salva é tratada como ausente.
"""
from pathlib import Path

import pytest

from src.core.database import LibraryDB, page_translation_fingerprint

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(tmp_path):
    database = LibraryDB(tmp_path / "lib.db")
    yield database
    database.close()


def _book(db, title="Livro", path="/tmp/x.pdf") -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf")


# ── page_translation_fingerprint (pura) ──────────────────────────────────

def test_fingerprint_stable_for_same_text():
    assert page_translation_fingerprint("Hello world") == page_translation_fingerprint("Hello world")


def test_fingerprint_differs_for_different_text():
    assert page_translation_fingerprint("Hello world") != page_translation_fingerprint("Goodbye world")


def test_fingerprint_normalizes_whitespace():
    # Espaços/quebras de linha extras não devem contar como texto diferente.
    assert page_translation_fingerprint("Hello   world\n\n") == page_translation_fingerprint("Hello world")


def test_fingerprint_empty_text_is_stable():
    assert page_translation_fingerprint("") == page_translation_fingerprint("   ")


# ── LibraryDB: get/set_page_translation_cache ────────────────────────────

def test_no_cache_returns_none(db):
    bid = _book(db)
    fp = page_translation_fingerprint("texto da página")
    assert db.get_cached_page_translation(bid, 0, "en", "pt", fp) is None


def test_save_then_get_returns_cached_translation(db):
    bid = _book(db)
    text = "This is page one."
    fp = page_translation_fingerprint(text)
    db.set_page_translation_cache(bid, 0, "en", "pt", fp, "Esta é a página um.")
    assert db.get_cached_page_translation(bid, 0, "en", "pt", fp) == "Esta é a página um."


def test_cache_invalidated_when_text_changes(db):
    bid = _book(db)
    old_text = "This is page one."
    new_text = "This is page one, revised."
    old_fp = page_translation_fingerprint(old_text)
    db.set_page_translation_cache(bid, 0, "en", "pt", old_fp, "Tradução antiga.")

    # Texto da página mudou (ex.: OCR reprocessado) → fingerprint nova não bate.
    new_fp = page_translation_fingerprint(new_text)
    assert db.get_cached_page_translation(bid, 0, "en", "pt", new_fp) is None
    # A entrada antiga continua consultável com a fingerprint antiga.
    assert db.get_cached_page_translation(bid, 0, "en", "pt", old_fp) == "Tradução antiga."


def test_cache_isolated_by_page_number(db):
    bid = _book(db)
    fp = page_translation_fingerprint("mesmo texto")
    db.set_page_translation_cache(bid, 0, "en", "pt", fp, "tradução da página 0")
    assert db.get_cached_page_translation(bid, 1, "en", "pt", fp) is None


def test_cache_isolated_by_language_pair(db):
    bid = _book(db)
    fp = page_translation_fingerprint("same text")
    db.set_page_translation_cache(bid, 0, "en", "pt", fp, "tradução pt")
    assert db.get_cached_page_translation(bid, 0, "en", "es", fp) is None


def test_cache_isolated_by_book(db):
    bid_a = _book(db, title="A", path="/tmp/a.pdf")
    bid_b = _book(db, title="B", path="/tmp/b.pdf")
    fp = page_translation_fingerprint("mesmo texto em dois livros")
    db.set_page_translation_cache(bid_a, 0, "en", "pt", fp, "tradução do livro A")
    assert db.get_cached_page_translation(bid_b, 0, "en", "pt", fp) is None


def test_set_page_translation_cache_upserts(db):
    bid = _book(db)
    text = "Page text."
    fp = page_translation_fingerprint(text)
    db.set_page_translation_cache(bid, 0, "en", "pt", fp, "primeira tradução")
    db.set_page_translation_cache(bid, 0, "en", "pt", fp, "tradução corrigida")
    assert db.get_cached_page_translation(bid, 0, "en", "pt", fp) == "tradução corrigida"


def test_delete_book_clears_translation_cache(db):
    bid = _book(db)
    fp = page_translation_fingerprint("texto")
    db.set_page_translation_cache(bid, 0, "en", "pt", fp, "tradução")
    db.delete_book(bid)
    rows = db.conn.execute(
        "SELECT COUNT(*) FROM page_translation_cache WHERE book_id=?", (bid,)).fetchone()
    assert rows[0] == 0


# ── Fiação estática no MainWindow (3.5) ──────────────────────────────────

def test_main_window_checks_cache_before_translating():
    src = (_ROOT / "src" / "gui" / "main_window.py").read_text(encoding="utf-8")
    assert "get_cached_page_translation" in src
    assert "set_page_translation_cache" in src
    assert "page_translation_fingerprint" in src
