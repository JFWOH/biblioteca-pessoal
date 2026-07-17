"""Testes da busca full-text no CONTEÚDO dos livros (Tarefa 5.1).

Cobre a lógica pura de sanitização (``src/core/fts_search.py``) e o acesso ao
FTS5 em ``LibraryDB`` (index/replace/delete/search/snippet/backfill/stats), além
da robustez a queries malformadas (ADR-005: nunca estourar erro de sintaxe).
"""

import sqlite3

import pytest

from src.core.database import LibraryDB
from src.core.fts_search import (
    SNIPPET_CLOSE,
    SNIPPET_OPEN,
    sanitize_fts_query,
)


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db, title="Livro", path="/tmp/x.pdf") -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf")


# ── Sanitização (pura) ─────────────────────────────────────────────────

@pytest.mark.parametrize("raw", ["", "   ", "\t\n", None])
def test_sanitize_empty_returns_empty(raw):
    assert sanitize_fts_query(raw) == ""


def test_sanitize_wraps_each_word_in_quotes():
    assert sanitize_fts_query("gato preto") == '"gato" "preto"'


def test_sanitize_only_punctuation_returns_empty():
    assert sanitize_fts_query("()* : ^ -") == ""


def test_sanitize_neutralizes_operators():
    # Operadores do FTS5 viram texto literal (entre aspas) — não quebram.
    out = sanitize_fts_query("gato AND OR NOT")
    assert out == '"gato" "AND" "OR" "NOT"'


def test_sanitize_handles_embedded_quotes():
    out = sanitize_fts_query('di"sse')
    # aspas embutidas viram espaço → frase de duas palavras, sem sintaxe inválida
    assert out == '"di sse"'


# ── Index / search / snippet ───────────────────────────────────────────

def test_index_and_search_finds_page(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "O gato preto subiu no telhado"),
                            (1, "Nada aqui sobre felinos")])
    res = db.fts_search("gato")
    assert len(res) == 1
    assert res[0]["book_id"] == bid
    assert res[0]["page_number"] == 0
    assert "rank" in res[0]


def test_snippet_has_highlight_markers(db):
    bid = _book(db)
    db.fts_index_book(bid, [(3, "uma frase longa com a palavra alvo bem no meio dela")])
    res = db.fts_search("alvo")
    assert res and SNIPPET_OPEN in res[0]["snippet"] and SNIPPET_CLOSE in res[0]["snippet"]
    assert "alvo" in res[0]["snippet"]


def test_search_is_accent_insensitive(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "tomei um cafe forte")])
    assert db.fts_search("café")  # com acento casa 'cafe' (remove_diacritics 2)
    assert db.fts_search("cafe")


def test_search_multiword_is_and(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "gato preto"), (1, "gato branco")])
    res = db.fts_search("gato preto")
    assert len(res) == 1 and res[0]["page_number"] == 0


def test_empty_pages_are_skipped(db):
    bid = _book(db)
    n = db.fts_index_book(bid, [(0, "   "), (1, ""), (2, "conteúdo real")])
    assert n == 1
    assert db.fts_stats()["pages"] == 1


# ── Replace / delete / backfill state ──────────────────────────────────

def test_reindex_replaces_previous_content(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "conteúdo antigo obsoleto")])
    db.fts_index_book(bid, [(0, "conteúdo novo atualizado")])
    assert not db.fts_search("obsoleto")
    assert db.fts_search("atualizado")
    assert db.fts_stats()["pages"] == 1  # não acumulou


def test_fts_remove_book(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "algo indexado")])
    assert db.fts_is_indexed(bid)
    db.fts_remove_book(bid)
    assert not db.fts_is_indexed(bid)
    assert db.fts_search("indexado") == []


def test_delete_book_removes_fts(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "vai sumir junto com o livro")])
    db.delete_book(bid)
    assert db.fts_search("sumir") == []
    assert not db.fts_is_indexed(bid)


def test_is_indexed_and_pending_count(db):
    b1 = _book(db, "Com FTS", "/tmp/a.pdf")
    _book(db, "Sem FTS", "/tmp/b.pdf")
    db.fts_index_book(b1, [(0, "texto")])
    assert db.fts_is_indexed(b1)
    assert db.fts_pending_count() == 1  # só o segundo livro está pendente


def test_stats_counts_books_and_pages(db):
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    db.fts_index_book(b1, [(0, "um"), (1, "dois")])
    db.fts_index_book(b2, [(0, "tres")])
    stats = db.fts_stats()
    assert stats["books"] == 2 and stats["pages"] == 3


# ── Lotes (batching > 200 páginas) ─────────────────────────────────────

def test_batched_indexing_large_book(db):
    bid = _book(db)
    pages = [(i, f"pagina numero {i} com termo comum") for i in range(250)]
    n = db.fts_index_book(bid, pages)
    assert n == 250
    assert db.fts_stats()["pages"] == 250
    # termo único numa página específica é recuperável
    db.fts_index_book(bid, pages[:200] + [(200, "sentinela unica xyzzy")] + pages[201:])
    res = db.fts_search("xyzzy")
    assert len(res) == 1 and res[0]["page_number"] == 200


# ── Robustez a queries malformadas (ADR-005) ───────────────────────────

@pytest.mark.parametrize("evil", [
    'foo"', '"', ')(', 'a AND', 'NEAR(', '* * *', 'col:val', '-', '^^',
    'a OR OR b', '""""',
])
def test_malformed_queries_never_raise(db, evil):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "algum conteúdo qualquer")])
    # Não deve levantar sqlite3.OperationalError — no pior caso, lista vazia.
    try:
        res = db.fts_search(evil)
    except sqlite3.OperationalError:
        pytest.fail(f"query malformada estourou sintaxe FTS5: {evil!r}")
    assert isinstance(res, list)


def test_search_empty_query_returns_empty(db):
    bid = _book(db)
    db.fts_index_book(bid, [(0, "conteúdo")])
    assert db.fts_search("") == []
    assert db.fts_search("   ") == []
