"""Testes do dossiê do livro (Fase 4 — core puro)."""
import pytest

from src.core.book_dossier import (
    build_dossier_data,
    build_dossier_synthesis_prompt,
    coverage_percent,
    format_coverage_label,
)
from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def store(db):
    return GraphStore(db)


def _book(db, title="Livro", path="/tmp/x.pdf", pages=10) -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf",
                       page_count=pages)


C = [("entropia", "Entropia", 0.9), ("termodinamica", "Termodinâmica", 0.7)]


def _seed_full(db, store):
    """Dois livros conectados por 2 conceitos + anotação + progresso."""
    bid = _book(db, title="Calor e Caos", path="/tmp/a.pdf", pages=4)
    other = _book(db, title="Física do Tempo", path="/tmp/b.pdf", pages=6)
    store.add_mentions(bid, "page:1", C, page=1)
    store.add_mentions(other, "page:2", C, page=2)
    store.recompute_book_edges(bid)
    db.add_annotation(bid, 2, content="A entropia sempre cresce.")
    db.update_reading_progress(bid, current_page=2, total_pages=4)
    return bid, other


# ── build_dossier_data ─────────────────────────────────────────────────

def test_dossier_data_complete(db, store):
    bid, other = _seed_full(db, store)
    data = build_dossier_data(db, store, bid)
    assert data["book"]["title"] == "Calor e Caos"
    assert data["progress"]["current_page"] == 2
    assert [c["name"] for c in data["concepts"]] == ["entropia", "termodinamica"]
    assert data["related"][0]["book_id"] == other
    assert data["coverage"]["pages_done"] == 1
    assert data["annotations_total"] == 1
    assert data["annotations_recent"][0]["content"].startswith("A entropia")


def test_dossier_data_missing_book(db, store):
    assert build_dossier_data(db, store, 999) is None


def test_dossier_data_empty_graph(db, store):
    bid = _book(db)
    data = build_dossier_data(db, store, bid)
    assert data["concepts"] == [] and data["related"] == []
    assert data["progress"] is None
    assert data["annotations_total"] == 0 and data["annotations_recent"] == []


def test_dossier_data_annotations_by_type(db, store):
    bid = _book(db)
    db.add_annotation(bid, 1, content="a", annotation_type="highlight")
    db.add_annotation(bid, 2, content="b", annotation_type="highlight")
    db.add_annotation(bid, 3, content="c", annotation_type="note")
    data = build_dossier_data(db, store, bid)
    assert data["annotations_by_type"] == {"highlight": 2, "note": 1}


def test_dossier_data_annotations_by_type_empty(db, store):
    bid = _book(db)
    data = build_dossier_data(db, store, bid)
    assert data["annotations_by_type"] == {}


def test_dossier_recent_annotations_capped_and_truncated(db, store):
    bid = _book(db)
    for i in range(5):
        db.add_annotation(bid, i + 1, content=f"nota {i} " + "x" * 300)
    data = build_dossier_data(db, store, bid)
    assert data["annotations_total"] == 5
    assert len(data["annotations_recent"]) == 3
    # Mais recente (maior id) primeiro; trecho truncado.
    assert data["annotations_recent"][0]["content"].startswith("nota 4")
    assert len(data["annotations_recent"][0]["content"]) <= 160


# ── cobertura ──────────────────────────────────────────────────────────

def test_coverage_label_unknown_total():
    assert format_coverage_label({"pages_done": 0, "pages_total": 0}) == \
        "cobertura desconhecida"
    assert format_coverage_label(None) == "cobertura desconhecida"
    assert coverage_percent(None) is None


def test_coverage_label_not_processed():
    label = format_coverage_label({"pages_done": 0, "pages_total": 10})
    assert label == "livro ainda não processado pelo grafo"


def test_coverage_label_percent():
    label = format_coverage_label({"pages_done": 3, "pages_total": 5})
    assert "60%" in label and "(3 de 5)" in label
    assert coverage_percent({"pages_done": 3, "pages_total": 5}) == 60


# ── prompt da síntese ──────────────────────────────────────────────────

def test_synthesis_prompt_none_without_concepts(db, store):
    bid = _book(db)
    data = build_dossier_data(db, store, bid)
    assert build_dossier_synthesis_prompt(data) is None
    assert build_dossier_synthesis_prompt(None) is None


def test_synthesis_prompt_contains_facts(db, store):
    bid, _other = _seed_full(db, store)
    prompt = build_dossier_synthesis_prompt(build_dossier_data(db, store, bid))
    assert "Calor e Caos" in prompt
    assert "Entropia" in prompt
    assert "Física do Tempo" in prompt
    assert "25%" in prompt  # 1 de 4 páginas
    # Cobertura < 50% → instrução de visão parcial.
    assert "parcial" in prompt


def test_synthesis_prompt_no_partial_with_high_coverage(db, store):
    bid = _book(db, pages=2)
    store.add_mentions(bid, "page:1", C, page=1)
    store.add_mentions(bid, "page:2", C[:1], page=2)
    prompt = build_dossier_synthesis_prompt(build_dossier_data(db, store, bid))
    assert "parcial" not in prompt


# ── perfil do leitor (tarefa 3.9) ────────────────────────────────────────

def test_synthesis_prompt_includes_reader_profile(db, store):
    bid, _other = _seed_full(db, store)
    prompt = build_dossier_synthesis_prompt(build_dossier_data(db, store, bid))
    assert "Perfil do leitor" in prompt
    assert "50%" in prompt        # current_page=2, total_pages=4
    assert "highlight" in prompt  # anotação padrão de _seed_full


def test_synthesis_prompt_reader_profile_degrades_without_progress(db, store):
    bid = _book(db)
    store.add_mentions(bid, "page:1", C, page=1)
    prompt = build_dossier_synthesis_prompt(build_dossier_data(db, store, bid))
    assert "Perfil do leitor" in prompt
    assert "leitura ainda não iniciada" in prompt
    assert "nenhuma anotação registrada" in prompt
