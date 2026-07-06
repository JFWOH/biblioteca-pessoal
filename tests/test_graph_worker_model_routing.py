"""Roteamento de modelo por tarefa no GraphWorker (Sprint A3, revisão de
engenharia 2026-07-05 §1.3): refino de conceitos do grafo é tarefa
rápida/estruturada e usa o modelo "fast" do tier (gemma4:e4b, com thinking
desligado no ConceptExtractor) quando não há override explícito em config
(``graph.llm_model``).
"""
from unittest.mock import patch

from src.core.database import LibraryDB
from src.gui.workers.graph_worker import GraphWorker


def _book(db, title="Livro", path="/tmp/x.pdf") -> int:
    return db.add_book(title=title, file_path=path, file_format="pdf", page_count=4)


def _fake_resolve_capturing(captured: dict):
    def fake(url, preferred=None, timeout=3):
        captured["preferred"] = preferred
        return preferred or "gemma4:e4b"
    return fake


def test_annotation_task_prefers_fast_model_without_config_override(tmp_path):
    db = LibraryDB(tmp_path / "lib.db")
    bid = _book(db)
    task = {"kind": "annotation", "book_id": bid, "annotation_id": 1,
           "page": 1, "text": "A entropia mede a desordem do sistema."}
    cfg = {"use_llm_annotations": True, "llm_model": None,
          "ollama_url": "http://localhost:11434"}
    captured: dict = {}

    with patch("src.core.graph.concept_extractor.resolve_llm_model",
              side_effect=_fake_resolve_capturing(captured)), \
         patch("urllib.request.urlopen", side_effect=OSError("sem rede no teste")):
        GraphWorker(task, db, rag_engine=None, cfg=cfg)._execute()

    assert captured["preferred"] == "gemma4:e4b"


def test_annotation_task_respects_explicit_config_override(tmp_path):
    db = LibraryDB(tmp_path / "lib.db")
    bid = _book(db)
    task = {"kind": "annotation", "book_id": bid, "annotation_id": 1,
           "page": 1, "text": "texto qualquer"}
    cfg = {"use_llm_annotations": True, "llm_model": "gemma2:2b",
          "ollama_url": "http://localhost:11434"}
    captured: dict = {}

    with patch("src.core.graph.concept_extractor.resolve_llm_model",
              side_effect=_fake_resolve_capturing(captured)), \
         patch("urllib.request.urlopen", side_effect=OSError("sem rede no teste")):
        GraphWorker(task, db, rag_engine=None, cfg=cfg)._execute()

    assert captured["preferred"] == "gemma2:2b"
