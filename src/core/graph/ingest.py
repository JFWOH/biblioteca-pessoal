"""Pipeline puro de ingestão do grafo de conceitos (Fase 2).

Funções sem estado e sem Qt (ADR-006), chamadas pelo worker da GUI:
- página do livro ativo durante a leitura (gatilho: virada de página);
- anotações (nova ao criar + varredura das existentes do livro);
- lote ocioso de um livro ainda não tratado (conteúdo já indexado no Chroma).

Idempotência garantida por ``graph_ingest_log`` + UNIQUE das menções:
reprocessar qualquer origem é inócuo.
"""

import logging

from src.core.graph.concept_extractor import ConceptExtractor
from src.core.graph.graph_store import GraphStore

logger = logging.getLogger(__name__)


def ingest_text(store: GraphStore, extractor: ConceptExtractor, book_id: int,
                origin_ref: str, text: str, source: str, page: int | None,
                use_llm: bool, max_concepts: int) -> int:
    """Ingere uma origem qualquer. Devolve o nº de menções novas."""
    if store.is_ingested(book_id, origin_ref):
        return 0
    if not text or not text.strip():
        # Origem processada sem conceitos ≠ origem pendente.
        store.mark_ingested(book_id, origin_ref, 0)
        return 0
    concepts, method = extractor.extract(text, max_concepts=max_concepts, use_llm=use_llm)
    if not concepts:
        store.mark_ingested(book_id, origin_ref, 0)
        return 0
    return store.add_mentions(book_id, origin_ref, concepts, page=page,
                              source=source, extracted_by=method)


def ingest_page(store: GraphStore, extractor: ConceptExtractor, book_id: int,
                page: int, text: str, use_llm: bool = False,
                max_concepts: int = 8) -> int:
    """Ingere uma página (1-based) do livro."""
    return ingest_text(store, extractor, book_id, f"page:{page}", text,
                       source="page", page=page, use_llm=use_llm,
                       max_concepts=max_concepts)


def ingest_annotation(store: GraphStore, extractor: ConceptExtractor, book_id: int,
                      annotation_id: int, text: str, page: int | None = None,
                      use_llm: bool = True, max_concepts: int = 5) -> int:
    """Ingere uma anotação do usuário (texto curado → LLM por padrão)."""
    return ingest_text(store, extractor, book_id, f"annotation:{annotation_id}",
                       text, source="annotation", page=page, use_llm=use_llm,
                       max_concepts=max_concepts)


def sweep_annotations(db, store: GraphStore, extractor: ConceptExtractor,
                      book_id: int, use_llm: bool = True,
                      max_concepts: int = 5) -> int:
    """Varre as anotações do livro ainda não ingeridas.

    Devolve o nº de anotações processadas nesta chamada.
    """
    done = store.ingested_refs(book_id, "annotation:")
    processed = 0
    for ann in db.get_annotations(book_id):
        ref = f"annotation:{ann['id']}"
        if ref in done:
            continue
        text = f"{ann.get('title', '')} {ann.get('content', '')}".strip()
        ingest_annotation(store, extractor, book_id, ann["id"], text,
                          page=ann.get("page_number"), use_llm=use_llm,
                          max_concepts=max_concepts)
        processed += 1
    return processed


def get_book_pages_from_chroma(collection, book_id: int) -> dict[int, str]:
    """Texto integral por página (1-based) a partir dos chunks do Chroma.

    ÚNICO ponto de alinhamento de numeração: os chunks guardam ``page_number``
    0-based (indexer usa o índice do loop de páginas); o reader e todo o grafo
    trabalham 1-based — daí o ``+ 1``.
    Só chunks ``chunk_type='content'`` viram página (metadata/note ficam fora).
    """
    result = collection.get(where={"book_id": book_id},
                            include=["documents", "metadatas"])
    per_page: dict[int, list[tuple[int, str]]] = {}
    for doc, meta in zip(result.get("documents") or [], result.get("metadatas") or []):
        meta = meta or {}
        if not doc or meta.get("chunk_type", "content") != "content":
            continue
        page_number = meta.get("page_number")
        if page_number is None:
            continue
        page = int(page_number) + 1  # 0-based (chunk) → 1-based (grafo/reader)
        per_page.setdefault(page, []).append((int(meta.get("chunk_index", 0)), doc))
    return {
        page: "\n".join(doc for _, doc in sorted(chunks))
        for page, chunks in per_page.items()
    }


def pick_next_untreated_book(db, store: GraphStore, collection,
                             active_book_id: int | None = None) -> int | None:
    """Escolhe o próximo livro indexado com cobertura incompleta.

    Prioriza o livro ativo, depois os de modificação mais recente.
    """
    candidates = db.get_books_by_indexing_status("indexed_ok")
    active = [b for b in candidates if b.get("id") == active_book_id]
    others = sorted((b for b in candidates if b.get("id") != active_book_id),
                    key=lambda b: str(b.get("date_modified") or ""), reverse=True)
    for book in active + others:
        book_id = book["id"]
        pages = get_book_pages_from_chroma(collection, book_id)
        cov = store.coverage(book_id, pages_total=len(pages))
        if not cov["complete"]:
            return book_id
    return None


def process_idle_batch(db, store: GraphStore, extractor: ConceptExtractor,
                       collection, batch_pages: int = 25, use_llm: bool = False,
                       active_book_id: int | None = None, max_concepts: int = 8,
                       should_cancel=None) -> dict:
    """Processa um lote conservador de um livro não tratado (modo ocioso).

    ``should_cancel`` (callable → bool) permite cancelamento cooperativo entre
    páginas (padrão do ProactiveWorker).
    """
    book_id = pick_next_untreated_book(db, store, collection, active_book_id)
    if book_id is None:
        return {"book_id": None, "pages": 0, "annotations": 0, "exhausted": True}

    pages = get_book_pages_from_chroma(collection, book_id)
    done = store.ingested_refs(book_id, "page:")
    processed = 0
    for page in sorted(pages):
        if should_cancel is not None and should_cancel():
            break
        if f"page:{page}" in done:
            continue
        if processed >= batch_pages:
            break
        ingest_page(store, extractor, book_id, page, pages[page],
                    use_llm=use_llm, max_concepts=max_concepts)
        processed += 1

    annotations = sweep_annotations(db, store, extractor, book_id, use_llm=use_llm)
    cov = store.coverage(book_id, pages_total=len(pages))
    return {"book_id": book_id, "pages": processed, "annotations": annotations,
            "exhausted": cov["complete"]}
