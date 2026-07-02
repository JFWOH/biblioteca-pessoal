"""Testes de dedup de anotações + rename + purga do grafo ao deletar."""
import pytest

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


def _book(db) -> int:
    return db.add_book(title="Livro", file_path="/tmp/x.pdf", file_format="pdf")


def test_add_annotation_dedup_exact_duplicate(db):
    """Cliques repetidos em 'Destacar' não podem duplicar a anotação."""
    bid = _book(db)
    a1 = db.add_annotation(bid, 33, content="Quarta Revolução Industrial",
                           position_data='{"coords": [1, 2, 3, 4]}')
    a2 = db.add_annotation(bid, 33, content="Quarta Revolução Industrial",
                           position_data='{"coords": [1, 2, 3, 4]}')
    assert a1 == a2
    assert len(db.get_annotations(bid)) == 1


def test_add_annotation_different_color_is_new_row(db):
    """Só duplicata EXATA é bloqueada — outra cor é uma anotação nova."""
    bid = _book(db)
    a1 = db.add_annotation(bid, 1, content="trecho", highlight_color="#fbbf24")
    a2 = db.add_annotation(bid, 1, content="trecho", highlight_color="#f87171")
    assert a1 != a2
    assert len(db.get_annotations(bid)) == 2


def test_add_annotation_different_page_is_new_row(db):
    bid = _book(db)
    a1 = db.add_annotation(bid, 1, content="trecho")
    a2 = db.add_annotation(bid, 2, content="trecho")
    assert a1 != a2


def test_dedupe_annotations_cleans_legacy_duplicates(db):
    """Duplicatas históricas (pré-guarda) são removidas mantendo a mais antiga."""
    bid = _book(db)
    # Insere duplicatas direto no SQL (simula o estado antigo do banco)
    for _ in range(4):
        with db._write_lock:
            db.conn.execute(
                """INSERT INTO annotations (book_id, page_number, content,
                   annotation_type, position_data, title)
                   VALUES (?, 33, 'Quarta Revolução Industrial', 'highlight', '{}', '')""",
                (bid,))
            db.conn.commit()
    removed = db.dedupe_annotations()
    assert removed == 3
    remaining = db.get_annotations(bid)
    assert len(remaining) == 1


def test_dedupe_purges_graph_of_removed_annotations(db):
    bid = _book(db)
    ids = []
    for _ in range(2):
        with db._write_lock:
            cur = db.conn.execute(
                """INSERT INTO annotations (book_id, page_number, content,
                   annotation_type, position_data, title)
                   VALUES (?, 1, 'nota', 'note', '{}', '')""", (bid,))
            db.conn.commit()
            ids.append(cur.lastrowid)
    store = GraphStore(db)
    for ann_id in ids:
        store.add_mentions(bid, f"annotation:{ann_id}",
                           [("entropia", "Entropia", 1.0)], page=1, source="annotation")
    db.dedupe_annotations()
    refs = store.ingested_refs(bid, "annotation:")
    assert refs == {f"annotation:{ids[0]}"}  # só a mantida


def test_delete_annotation_purges_graph(db):
    bid = _book(db)
    ann_id = db.add_annotation(bid, 5, content="nota", annotation_type="note")
    store = GraphStore(db)
    store.add_mentions(bid, f"annotation:{ann_id}",
                       [("calor", "Calor", 1.0)], page=5, source="annotation")
    db.delete_annotation(ann_id)
    assert store.ingested_refs(bid) == set()
    assert db.conn.execute(
        "SELECT COUNT(*) FROM concept_mentions WHERE book_id=?", (bid,)
    ).fetchone()[0] == 0


def test_update_annotation_title(db):
    bid = _book(db)
    ann_id = db.add_annotation(bid, 1, content="corpo", annotation_type="ai_note",
                               title="[⚙ highlight_book_text(...)...]")
    db.update_annotation_title(ann_id, "Contexto da inovação")
    ann = db.get_annotations(bid)[0]
    assert ann["title"] == "Contexto da inovação"
