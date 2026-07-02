"""Testes do pipeline puro de ingestão do grafo (Fase 2)."""
import pytest

from src.core.database import LibraryDB
from src.core.graph.concept_extractor import ConceptExtractor
from src.core.graph.graph_store import GraphStore
from src.core.graph import ingest


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def store(db):
    return GraphStore(db)


@pytest.fixture
def ex():
    return ConceptExtractor()


class FakeCollection:
    """Imita chromadb Collection.get(where=..., include=...) para os testes."""

    def __init__(self):
        self._docs: list[tuple[str, dict]] = []

    def add_page_chunks(self, book_id: int, page0: int, texts: list[str],
                        chunk_type: str = "content"):
        for idx, text in enumerate(texts):
            self._docs.append((text, {
                "book_id": book_id, "page_number": page0,
                "chunk_index": len(self._docs), "chunk_type": chunk_type,
            }))

    def get(self, where=None, include=None):
        book_id = (where or {}).get("book_id")
        hits = [(d, m) for d, m in self._docs
                if book_id is None or m["book_id"] == book_id]
        return {"documents": [d for d, _ in hits],
                "metadatas": [m for _, m in hits]}


PAGE = ("A entropia domina a termodinâmica. A entropia cresce; a "
        "termodinâmica descreve o calor e a entropia dos sistemas.")


def _book(db, title="Livro", path="/tmp/x.pdf", pages=3, indexed=True) -> int:
    bid = db.add_book(title=title, file_path=path, file_format="pdf", page_count=pages)
    if indexed:
        db.set_indexing_status(bid, "indexed_ok")
    return bid


def test_ingest_page_and_idempotence(db, store, ex):
    bid = _book(db)
    n1 = ingest.ingest_page(store, ex, bid, 2, PAGE)
    n2 = ingest.ingest_page(store, ex, bid, 2, PAGE)  # re-visita da página
    assert n1 > 0 and n2 == 0
    assert store.is_ingested(bid, "page:2")
    top = store.get_book_concepts(bid)
    assert "entropia" in [c["name"] for c in top]


def test_ingest_empty_page_marks_done(db, store, ex):
    bid = _book(db)
    assert ingest.ingest_page(store, ex, bid, 1, "   ") == 0
    assert store.is_ingested(bid, "page:1")  # não fica pendente para sempre


def test_ingest_annotation_source(db, store, ex):
    bid = _book(db)
    ann_id = db.add_annotation(bid, 4, content="Conceito chave: homeostase.")
    ingest.ingest_annotation(store, ex, bid, ann_id,
                             "Conceito chave: homeostase.", page=4, use_llm=False)
    row = db.conn.execute(
        "SELECT source, page FROM concept_mentions WHERE origin_ref = ?",
        (f"annotation:{ann_id}",)).fetchone()
    assert row["source"] == "annotation" and row["page"] == 4


def test_sweep_annotations_skips_done(db, store, ex):
    bid = _book(db)
    a1 = db.add_annotation(bid, 1, content="Nota sobre entropia e desordem.")
    db.add_annotation(bid, 2, content="Nota sobre homeostase celular.")
    ingest.ingest_annotation(store, ex, bid, a1,
                             "Nota sobre entropia e desordem.", page=1, use_llm=False)
    processed = ingest.sweep_annotations(db, store, ex, bid, use_llm=False)
    assert processed == 1  # só a segunda; a primeira já estava ingerida


def test_get_book_pages_from_chroma_normalizes_1based(db, store, ex):
    col = FakeCollection()
    col.add_page_chunks(7, page0=0, texts=["primeira parte", "segunda parte"])
    col.add_page_chunks(7, page0=3, texts=["página quatro"])
    col.add_page_chunks(7, page0=1, texts=["nota do usuário"], chunk_type="note")
    pages = ingest.get_book_pages_from_chroma(col, 7)
    assert set(pages) == {1, 4}  # 0-based do chunk → 1-based; 'note' fica fora
    assert pages[1] == "primeira parte\nsegunda parte"


def test_pick_next_untreated_prioritizes_active(db, store, ex):
    b1 = _book(db, "A", "/tmp/a.pdf", pages=1)
    b2 = _book(db, "B", "/tmp/b.pdf", pages=1)
    col = FakeCollection()
    col.add_page_chunks(b1, 0, [PAGE])
    col.add_page_chunks(b2, 0, [PAGE])
    assert ingest.pick_next_untreated_book(db, store, col, active_book_id=b2) == b2
    # Livro sem indexação concluída não é candidato
    b3 = _book(db, "C", "/tmp/c.pdf", pages=1, indexed=False)
    assert ingest.pick_next_untreated_book(db, store, col, active_book_id=b3) != b3


def test_pick_next_skips_complete_books(db, store, ex):
    b1 = _book(db, "A", "/tmp/a.pdf", pages=1)
    col = FakeCollection()
    col.add_page_chunks(b1, 0, [PAGE])
    ingest.ingest_page(store, ex, b1, 1, PAGE)  # cobre a única página
    assert ingest.pick_next_untreated_book(db, store, col) is None


def test_process_idle_batch(db, store, ex):
    bid = _book(db, pages=3)
    col = FakeCollection()
    for p in range(3):
        col.add_page_chunks(bid, p, [PAGE])
    db.add_annotation(bid, 1, content="Nota sobre entropia.")

    report = ingest.process_idle_batch(db, store, ex, col, batch_pages=2)
    assert report["book_id"] == bid
    assert report["pages"] == 2 and report["annotations"] == 1
    assert report["exhausted"] is False

    report2 = ingest.process_idle_batch(db, store, ex, col, batch_pages=25)
    assert report2["pages"] == 1
    assert report2["exhausted"] is True

    report3 = ingest.process_idle_batch(db, store, ex, col, batch_pages=25)
    assert report3["book_id"] is None and report3["exhausted"] is True


def test_process_idle_batch_cancel(db, store, ex):
    bid = _book(db, pages=3)
    col = FakeCollection()
    for p in range(3):
        col.add_page_chunks(bid, p, [PAGE])
    report = ingest.process_idle_batch(db, store, ex, col, batch_pages=25,
                                       should_cancel=lambda: True)
    assert report["pages"] == 0  # cancelamento cooperativo antes da 1ª página
