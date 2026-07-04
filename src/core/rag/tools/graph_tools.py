"""Tools de grafo de conceitos para o agente RAG (Fase 3).

Wrappers read-only sobre o GraphStore (Fase 2) no contrato ToolOutput
(ADR-001). Dão ao agente memória simbólica da biblioteca:
- onde um conceito aparece (livros + páginas → citação [Título, p. X]);
- que livros se conectam a um livro (conceitos compartilhados);
- o mapa conceitual de um livro.

Proveniência sempre "local" (grafo interno) — a PolicyEngine (ADR-003) as
trata como leitura, sem restrição.
"""

from src.core.graph.concept_extractor import ConceptExtractor
from src.core.graph.graph_store import GraphStore
from src.core.rag.tools.base import ToolOutput, create_tool_output


def graph_concept_lookup(store: GraphStore, concept: str, limit: int = 10) -> ToolOutput:
    """Em quais livros/páginas o conceito aparece ("onde mais aparece?")."""
    name = ConceptExtractor.normalize(concept or "")
    if not name:
        return create_tool_output(
            status="error", data=[], error_message="Conceito vazio.",
            confidence=0.0, metadata={"tool_name": "graph_concept_lookup"})
    books = store.get_concept_books(name, limit=limit)
    data = [
        {
            "title": b["title"],
            "book_id": b["book_id"],
            "mentions": b["mentions"],
            "pages": (b.get("pages") or [])[:10],
        }
        for b in books
    ]
    return create_tool_output(
        status="success", data=data, provenance="local",
        confidence=0.9 if data else 0.2,
        metadata={"tool_name": "graph_concept_lookup",
                  "concept": name, "result_count": len(data)})


def graph_related_books(store: GraphStore, book_id: int, limit: int = 5) -> ToolOutput:
    """Livros conectados a um livro por conceitos compartilhados."""
    if not book_id:
        return create_tool_output(
            status="error", data=[], error_message="book_id ausente.",
            confidence=0.0, metadata={"tool_name": "graph_related_books"})
    related = store.related_books(int(book_id), limit=limit)
    data = [
        {
            "title": r["title"],
            "book_id": r["book_id"],
            "shared_concepts": r.get("shared") or [],
            "strength": r.get("weight", 0),
        }
        for r in related
    ]
    return create_tool_output(
        status="success", data=data, provenance="local",
        confidence=0.9 if data else 0.2,
        metadata={"tool_name": "graph_related_books",
                  "book_id": int(book_id), "result_count": len(data)})


def graph_book_concepts(store: GraphStore, book_id: int, limit: int = 10) -> ToolOutput:
    """Principais conceitos de um livro segundo o grafo."""
    if not book_id:
        return create_tool_output(
            status="error", data=[], error_message="book_id ausente.",
            confidence=0.0, metadata={"tool_name": "graph_book_concepts"})
    concepts = store.get_book_concepts(int(book_id), limit=limit)
    data = [
        {
            "concept": c["display_name"],
            "weight": round(float(c.get("weight") or 0), 3),
            "mentions": c.get("mentions", 0),
        }
        for c in concepts
    ]
    return create_tool_output(
        status="success", data=data, provenance="local",
        confidence=0.9 if data else 0.2,
        metadata={"tool_name": "graph_book_concepts",
                  "book_id": int(book_id), "result_count": len(data)})
