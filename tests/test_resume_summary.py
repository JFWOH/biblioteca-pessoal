"""Testes do mini-resumo de retomada de leitura (tarefa 3.7).

Lógica pura (sem GUI): usa um DB falso — não precisa de sqlite nem PyQt6.
"""
from src.core.resume_summary import (
    build_resume_info,
    format_resume_summary_line,
    format_resume_banner_text,
)


class _FakeDB:
    def __init__(self, progress=None, annotations=None):
        self._progress = progress
        self._annotations = annotations or []

    def get_reading_progress(self, book_id):
        return self._progress

    def get_annotations(self, book_id, annotation_type=None):
        if annotation_type:
            return [a for a in self._annotations
                    if a.get("annotation_type") == annotation_type]
        return list(self._annotations)


def test_no_progress_returns_none():
    assert build_resume_info(_FakeDB(progress=None), 1) is None


def test_zero_percent_returns_none():
    db = _FakeDB(progress={"current_page": 0, "total_pages": 100, "percentage": 0})
    assert build_resume_info(db, 1) is None


def test_missing_book_id_returns_none():
    db = _FakeDB(progress={"percentage": 50})
    assert build_resume_info(db, 0) is None


def test_basic_info_from_progress():
    db = _FakeDB(progress={
        "current_page": 41, "total_pages": 200,
        "percentage": 20.5, "time_spent_seconds": 3600, "last_read": "2026-07-16",
    })
    info = build_resume_info(db, 7)
    assert info is not None
    assert info["current_page"] == 41
    assert info["total_pages"] == 200
    assert info["percentage"] == 20.5
    assert info["summary_line"] == "Você parou na p. 42 (20% lido)"


def test_recent_notes_extracted_and_bookmarks_ignored():
    db = _FakeDB(
        progress={"current_page": 10, "total_pages": 100, "percentage": 10},
        annotations=[
            {"annotation_type": "highlight", "page_number": 2, "content": "destaque A"},
            {"annotation_type": "bookmark", "page_number": 3, "content": ""},
            {"annotation_type": "note", "page_number": 5, "content": "nota B"},
        ],
    )
    info = build_resume_info(db, 1)
    notes = info["recent_notes"]
    assert all(n["type"] != "bookmark" for n in notes)
    assert {n["snippet"] for n in notes} == {"destaque A", "nota B"}


def test_summary_line_is_one_based_and_rounded():
    assert format_resume_summary_line(
        {"current_page": 0, "percentage": 0.4}) == "Você parou na p. 1 (0% lido)"
    assert format_resume_summary_line(
        {"current_page": 99, "percentage": 99.6}) == "Você parou na p. 100 (100% lido)"


def test_banner_text_prefers_synthesis_then_note_then_concepts():
    base = {"current_page": 4, "percentage": 30}

    with_syn = dict(base, synthesis="Uma síntese\nsegunda linha", recent_notes=[], concepts=[])
    txt = format_resume_banner_text(with_syn)
    assert "Uma síntese" in txt and "segunda linha" not in txt  # só a 1ª linha

    with_note = dict(base, synthesis=None,
                     recent_notes=[{"page": 3, "snippet": "meu destaque"}], concepts=["x"])
    txt = format_resume_banner_text(with_note)
    assert "meu destaque" in txt and "p. 4" in txt  # página 1-based

    with_concepts = dict(base, synthesis=None, recent_notes=[], concepts=["a", "b"])
    txt = format_resume_banner_text(with_concepts)
    assert "Conceitos:" in txt and "a, b" in txt


def test_graph_errors_degrade_gracefully():
    # graph_store que estoura não deve derrubar build_resume_info (ADR-005).
    class _BoomGraph:
        def get_book_concepts(self, *a, **k):
            raise RuntimeError("grafo indisponível")

        def ingest_fingerprint(self, *a, **k):
            raise RuntimeError("grafo indisponível")

    db = _FakeDB(progress={"current_page": 1, "total_pages": 10, "percentage": 12})
    info = build_resume_info(db, 1, graph_store=_BoomGraph())
    assert info is not None
    assert info["concepts"] == []
    assert info["synthesis"] is None
