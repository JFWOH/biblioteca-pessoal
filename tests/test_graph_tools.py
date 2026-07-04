"""Testes das tools de grafo do agente RAG (Fase 3)."""
import json

import pytest

from src.core.database import LibraryDB
from src.core.graph.graph_store import GraphStore
from src.core.rag.agent_state import AgentState
from src.core.rag.orchestrator import Orchestrator
from src.core.rag.policy_engine import PolicyEngine
from src.core.rag.tools import graph_tools


class FakeEngine:
    """Só o que as tools de grafo usam do RAGEngine: o caminho do SQLite."""

    def __init__(self, db_path):
        self._db_path = db_path


class FakeTrace:
    def emit(self, *args, **kwargs):
        pass


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def orch(db):
    return Orchestrator(FakeEngine(db._db_path))


def _seed(db) -> tuple[int, int]:
    """Dois livros compartilhando conceitos, com menções paginadas."""
    store = GraphStore(db)
    b1 = db.add_book(title="Física do Caos", file_path="/tmp/a.pdf", file_format="pdf")
    b2 = db.add_book(title="Ordem e Desordem", file_path="/tmp/b.pdf", file_format="pdf")
    store.add_mentions(b1, "page:12", [("entropia", "Entropia", 0.9),
                                       ("caos", "Caos", 0.7)], page=12)
    store.add_mentions(b1, "page:30", [("entropia", "Entropia", 0.8)], page=30)
    store.add_mentions(b2, "page:87", [("entropia", "Entropia", 1.0),
                                       ("caos", "Caos", 0.5)], page=87)
    store.recompute_book_edges(b1)
    return b1, b2


# ── Funções puras (ToolOutput) ────────────────────────────────────────

def test_concept_lookup_returns_books_and_pages(db):
    b1, b2 = _seed(db)
    out = graph_tools.graph_concept_lookup(GraphStore(db), "Entropia")  # normaliza
    assert out["status"] == "success"
    by_id = {d["book_id"]: d for d in out["data"]}
    assert by_id[b1]["pages"] == [12, 30]
    assert by_id[b2]["title"] == "Ordem e Desordem" and by_id[b2]["pages"] == [87]
    assert out["confidence_score"] == 0.9


def test_concept_lookup_unknown_concept_low_confidence(db):
    _seed(db)
    out = graph_tools.graph_concept_lookup(GraphStore(db), "fotossíntese")
    assert out["status"] == "success" and out["data"] == []
    assert out["confidence_score"] == 0.2


def test_concept_lookup_empty_is_error(db):
    out = graph_tools.graph_concept_lookup(GraphStore(db), "  ")
    assert out["status"] == "error"


def test_related_books_shared_concepts(db):
    b1, b2 = _seed(db)
    out = graph_tools.graph_related_books(GraphStore(db), b1)
    assert out["status"] == "success"
    assert out["data"][0]["book_id"] == b2
    assert set(out["data"][0]["shared_concepts"]) == {"Entropia", "Caos"}


def test_book_concepts_ordered_by_weight(db):
    b1, _ = _seed(db)
    out = graph_tools.graph_book_concepts(GraphStore(db), b1)
    assert out["data"][0]["concept"] == "Entropia"  # 0.9+0.8 > 0.7
    assert out["data"][0]["mentions"] == 2


def test_missing_book_id_is_error(db):
    assert graph_tools.graph_related_books(GraphStore(db), 0)["status"] == "error"
    assert graph_tools.graph_book_concepts(GraphStore(db), None)["status"] == "error"


# ── Executores do Orchestrator + dispatch ─────────────────────────────

def test_executor_appends_called_tool(db, orch):
    _seed(db)
    state = AgentState("sess-1")
    out = orch.execute_graph_concept_lookup("entropia", state=state)
    assert out["status"] == "success"
    assert "graph_concept_lookup" in state.called_tools


def test_executor_error_is_graceful(db, orch):
    out = orch.execute_graph_related_books("x")  # book_id inválido → error
    assert out["status"] == "error"
    assert out["error_message"]


def test_dispatch_graph_concept_lookup(db, orch):
    b1, b2 = _seed(db)
    state = AgentState("sess-2")
    raw = orch._execute_tool_orchestrated(
        "graph_concept_lookup", {"concept": "entropia"}, state, FakeTrace())
    data = json.loads(raw)
    assert {d["book_id"] for d in data} == {b1, b2}


def test_dispatch_related_books_defaults_to_current_book(db, orch):
    b1, b2 = _seed(db)
    state = AgentState("sess-3")
    raw = orch._execute_tool_orchestrated(
        "graph_related_books", {}, state, FakeTrace(), book_id=b1)
    data = json.loads(raw)
    assert data and data[0]["book_id"] == b2


def test_dispatch_book_concepts_with_string_book_id(db, orch):
    b1, _ = _seed(db)
    state = AgentState("sess-4")
    raw = orch._execute_tool_orchestrated(
        "graph_book_concepts", {"book_id": str(b1)}, state, FakeTrace())
    data = json.loads(raw)
    assert data[0]["concept"] == "Entropia"


# ── PolicyEngine (ADR-003) ────────────────────────────────────────────

def test_policy_allows_graph_tools_any_provenance():
    for tool in ("graph_concept_lookup", "graph_related_books", "graph_book_concepts"):
        assert PolicyEngine.is_action_allowed(tool, "local", {}) is True
        assert PolicyEngine.is_action_allowed(tool, "web", {}) is True  # read-only


def test_tools_def_contains_graph_tools():
    from src.core.rag_engine import _TOOLS_DEF
    names = {t["function"]["name"] for t in _TOOLS_DEF}
    assert {"graph_concept_lookup", "graph_related_books",
            "graph_book_concepts"} <= names
