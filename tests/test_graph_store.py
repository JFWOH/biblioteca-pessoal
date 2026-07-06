"""Testes do GraphStore (Fase 2 — grafo de conceitos)."""
import pytest

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def store(db):
    return GraphStore(db)


def _book(db, title="Livro", path="/tmp/x.pdf", pages=10) -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf", page_count=pages)


C = [("entropia", "Entropia", 0.9), ("termodinamica", "Termodinâmica", 0.7)]


def test_upsert_concept_idempotent(store):
    a = store.upsert_concept("entropia", "Entropia")
    b = store.upsert_concept("entropia", "Entropia (2)")
    assert a == b  # mesmo conceito; display_name original preservado


def test_add_mentions_and_idempotence(db, store):
    bid = _book(db)
    n1 = store.add_mentions(bid, "page:3", C, page=3, source="page")
    n2 = store.add_mentions(bid, "page:3", C, page=3, source="page")  # re-visita
    assert n1 == 2
    assert n2 == 0  # UNIQUE(concept_id, book_id, origin_ref) segura a duplicata
    total = db.conn.execute("SELECT COUNT(*) FROM concept_mentions").fetchone()[0]
    assert total == 2
    assert store.is_ingested(bid, "page:3")
    assert not store.is_ingested(bid, "page:4")


def test_mark_ingested_zero_mentions(db, store):
    """Página processada sem conceitos ≠ página não processada."""
    bid = _book(db)
    store.mark_ingested(bid, "page:7", mentions=0)
    assert store.is_ingested(bid, "page:7")


def test_ingested_refs_prefix(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", C[:1], page=1)
    store.add_mentions(bid, "annotation:5", C[1:], page=None, source="annotation")
    assert store.ingested_refs(bid, "page:") == {"page:1"}
    assert store.ingested_refs(bid) == {"page:1", "annotation:5"}


def test_coverage(db, store):
    bid = _book(db, pages=4)
    db.add_annotation(bid, 2, content="nota")
    store.mark_ingested(bid, "page:1")
    store.mark_ingested(bid, "page:2")
    cov = store.coverage(bid)
    assert cov["pages_done"] == 2 and cov["pages_total"] == 4
    assert cov["annotations_done"] == 0 and cov["annotations_total"] == 1
    assert cov["complete"] is False


def test_get_book_concepts_aggregates_weight(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", [("entropia", "Entropia", 0.5)], page=1)
    store.add_mentions(bid, "page:2", [("entropia", "Entropia", 0.8),
                                       ("calor", "Calor", 0.3)], page=2)
    top = store.get_book_concepts(bid)
    assert top[0]["name"] == "entropia"
    assert top[0]["mentions"] == 2
    assert abs(top[0]["weight"] - 1.3) < 1e-9


def test_get_concept_books_pages(db, store):
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    store.add_mentions(b1, "page:3", C[:1], page=3)
    store.add_mentions(b1, "page:9", C[:1], page=9)
    store.add_mentions(b2, "annotation:1", C[:1], page=None, source="annotation")
    books = store.get_concept_books("entropia")
    by_id = {b["book_id"]: b for b in books}
    assert by_id[b1]["pages"] == [3, 9]
    assert by_id[b2]["pages"] == []  # página NULL não vira número


def test_edges_and_related_books(db, store):
    b1 = _book(db, "Física A", "/tmp/a.pdf")
    b2 = _book(db, "Física B", "/tmp/b.pdf")
    shared = [("entropia", "Entropia", 0.9), ("calor", "Calor", 0.6)]
    store.add_mentions(b1, "page:1", shared + [("exclusivo-a", "Exclusivo A", 0.5)], page=1)
    store.add_mentions(b2, "page:1", shared + [("exclusivo-b", "Exclusivo B", 0.5)], page=1)
    written = store.recompute_book_edges(b1)
    assert written == 1
    rel = store.related_books(b1)
    assert len(rel) == 1
    assert rel[0]["book_id"] == b2 and rel[0]["title"] == "Física B"
    assert rel[0]["weight"] == 2.0
    assert set(rel[0]["shared"]) == {"Entropia", "Calor"}
    # Simetria: consulta do outro lado enxerga a mesma aresta
    rel_b = store.related_books(b2)
    assert rel_b and rel_b[0]["book_id"] == b1


def test_edges_min_shared(db, store):
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    store.add_mentions(b1, "page:1", [("um", "Um", 0.9)], page=1)
    store.add_mentions(b2, "page:1", [("um", "Um", 0.9)], page=1)
    assert store.recompute_book_edges(b1, min_shared=2) == 0
    assert store.related_books(b1) == []


def test_edges_df_cap_floor_small_library(db, store):
    """Com 2 livros, o teto de DF tem piso 2 — senão nunca haveria aresta."""
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    shared = [("x", "X", 1.0), ("y", "Y", 1.0)]
    store.add_mentions(b1, "page:1", shared, page=1)
    store.add_mentions(b2, "page:1", shared, page=1)
    assert store.recompute_book_edges(b1) == 1


def test_recompute_replaces_stale_edges(db, store):
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    shared = [("x", "X", 1.0), ("y", "Y", 1.0)]
    store.add_mentions(b1, "page:1", shared, page=1)
    store.add_mentions(b2, "page:1", shared, page=1)
    store.recompute_book_edges(b1)
    store.add_mentions(b1, "page:2", [("z", "Z", 1.0)], page=2)
    store.add_mentions(b2, "page:2", [("z", "Z", 1.0)], page=2)
    store.recompute_book_edges(b1)
    rel = store.related_books(b1)
    assert len(rel) == 1 and rel[0]["weight"] == 3.0


def test_delete_book_cleans_graph(db, store):
    b1 = _book(db, "A", "/tmp/a.pdf")
    b2 = _book(db, "B", "/tmp/b.pdf")
    shared = [("x", "X", 1.0), ("y", "Y", 1.0)]
    store.add_mentions(b1, "page:1", shared, page=1)
    store.add_mentions(b2, "page:1", shared, page=1)
    store.recompute_book_edges(b1)
    db.delete_book(b1)
    conn = db.conn
    assert conn.execute("SELECT COUNT(*) FROM concept_mentions WHERE book_id=?",
                        (b1,)).fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM book_edges").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM graph_ingest_log WHERE book_id=?",
                        (b1,)).fetchone()[0] == 0


def test_purge_book(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", C, page=1)
    store.purge_book(bid)
    assert store.stats()["mentions"] == 0
    assert store.ingested_refs(bid) == set()


def test_stats(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", C, page=1)
    s = store.stats()
    assert s["concepts"] == 2 and s["mentions"] == 2 and s["books_covered"] == 1
