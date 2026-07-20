"""Servidor MCP local (stdio) da Biblioteca Pessoal — rodada M1 (somente leitura).

Expõe a biblioteca a um host MCP (Claude Desktop/Code ou outro):

    claude mcp add biblioteca -- <venv>\\Scripts\\python.exe -m src.mcp.server

Invariantes de segurança do plano jul/2026-D:
- transporte stdio apenas (sem rede);
- a rodada M1 é 100% somente-leitura (nenhuma ferramenta grava no banco);
- teto de ``PAGE_CAP`` páginas por chamada em ``get_page_text``;
- fronteira ADR-006: importa apenas ``src/core``, ``src/readers`` e
  ``src/utils`` — zero Qt;
- startup leve: chromadb/readers só são importados dentro das ferramentas que
  os usam (lição B0 — lazy import); torch/kokoro não entram nesta rodada.

Convenção da fronteira MCP: TODOS os números de página em parâmetros e
retornos são 1-based (o armazenamento interno do app é 0-based). Toda
ferramenta devolve o envelope uniforme ``{"status": "success", "data": ...}``
ou ``{"status": "error", "error": ...}`` — erros esperados viram dado, nunca
exceção (ADR-005: degradação graciosa).
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.core.database import LibraryDB
from src.utils.constants import DATA_DIR, DB_PATH

# Teto de páginas por chamada de get_page_text (invariante do plano M1).
PAGE_CAP = 10

# Caminhos ativos — redirecionáveis via configure() (testes usam tmp_path).
_db_path: Path = DB_PATH
_chroma_path: Path = DATA_DIR / "chroma_db"

# Singletons preguiçosos, criados na 1ª ferramenta que os usa.
_state: dict[str, Any] = {"db": None, "rag": None}

mcp = FastMCP(
    "biblioteca-pessoal",
    instructions=(
        "Biblioteca pessoal local do usuário: livros, anotações, progresso de "
        "leitura e buscas (metadados, full-text e semântica). Todas as "
        "ferramentas são somente-leitura; números de página são 1-based."
    ),
)


def configure(db_path: str | Path | None = None,
              chroma_path: str | Path | None = None) -> None:
    """Redireciona os caminhos de dados (testes) e descarta os singletons."""
    global _db_path, _chroma_path
    if db_path is not None:
        _db_path = Path(db_path)
    if chroma_path is not None:
        _chroma_path = Path(chroma_path)
    close()


def close() -> None:
    """Fecha o LibraryDB e zera os singletons (libera o arquivo no Windows)."""
    db = _state.get("db")
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    _state["db"] = None
    _state["rag"] = None


def _db() -> LibraryDB:
    if _state["db"] is None:
        _state["db"] = LibraryDB(_db_path)
    return _state["db"]


def _rag():
    if _state["rag"] is None:
        from src.core.rag_engine import RAGEngine
        _state["rag"] = RAGEngine(db_path=str(_db_path), chroma_path=str(_chroma_path))
    return _state["rag"]


def _ok(data: Any) -> dict:
    return {"status": "success", "data": data}


def _err(message: str) -> dict:
    return {"status": "error", "error": message}


# Campos expostos nas listagens — o registro completo (com file_path etc.)
# sai apenas em get_book, para manter as listas enxutas.
_SUMMARY_KEYS = ("id", "title", "author", "file_format", "read_status",
                 "rating", "is_favorite", "date_added", "date_modified")


def _summary(book: dict) -> dict:
    return {k: book.get(k) for k in _SUMMARY_KEYS}


# ── Ferramentas: biblioteca ──────────────────────────────────────────────


@mcp.tool()
def list_books(status: str | None = None, file_format: str | None = None,
               author: str | None = None, min_rating: int | None = None,
               favorites_only: bool = False,
               sort_by: str = "date_added", sort_order: str = "desc",
               limit: int = 50, offset: int = 0) -> dict:
    """Lista livros da biblioteca, com filtros e ordenação.

    Args:
        status: estado de leitura ('unread', 'reading' ou 'read').
        file_format: formato do arquivo ('pdf', 'epub', ...).
        author: filtro por autor (busca parcial, sem diferenciar maiúsculas).
        min_rating: avaliação mínima (0-5 estrelas).
        favorites_only: apenas favoritos.
        sort_by: 'date_added', 'date_modified', 'title', 'author' ou 'rating'
            (valor fora da whitelist cai no padrão 'date_added').
        sort_order: 'asc' ou 'desc'.
        limit: máximo de livros retornados (<=0 = sem limite).
        offset: deslocamento de paginação sobre o resultado filtrado.
    """
    books = _db().get_all_books(sort_by=sort_by, sort_order=sort_order)
    if status:
        books = [b for b in books if b.get("read_status") == status]
    if file_format:
        fmt = file_format.lstrip(".").lower()
        books = [b for b in books if (b.get("file_format") or "").lower() == fmt]
    if author:
        needle = author.lower()
        books = [b for b in books if needle in (b.get("author") or "").lower()]
    if min_rating is not None:
        books = [b for b in books if (b.get("rating") or 0) >= min_rating]
    if favorites_only:
        books = [b for b in books if b.get("is_favorite")]
    total = len(books)
    offset = max(0, offset)
    window = books[offset:offset + limit] if limit > 0 else books[offset:]
    return _ok({"total": total, "returned": len(window),
                "books": [_summary(b) for b in window]})


@mcp.tool()
def get_book(book_id: int) -> dict:
    """Detalhes completos de um livro: registro, tags, coleções, progresso de
    leitura, estado de indexação (RAG e FTS) e contagem de anotações."""
    db = _db()
    book = db.get_book(book_id)
    if book is None:
        return _err(f"Livro {book_id} não encontrado.")
    return _ok({
        "book": book,
        "tags": db.get_book_tags(book_id),
        "collections": db.get_book_collections(book_id),
        "reading_progress": db.get_reading_progress(book_id),
        "indexing_status": db.get_indexing_status(book_id),
        "fts_indexed": db.fts_is_indexed(book_id),
        "annotations_count": len(db.get_annotations(book_id)),
    })


@mcp.tool()
def search_books(query: str) -> dict:
    """Busca livros por METADADOS (título/autor/descrição, FTS5).

    Para buscar dentro do conteúdo das páginas, use search_content."""
    try:
        rows = _db().search_books(query)
    except sqlite3.OperationalError:
        # O MATCH recebe a query crua — sintaxe FTS inválida vira erro
        # amigável em vez de exceção (ADR-005).
        return _err("Consulta inválida para busca por metadados — "
                    "tente termos simples, sem operadores especiais.")
    return _ok({"total": len(rows), "books": [_summary(b) for b in rows]})


# ── Ferramentas: busca em conteúdo ───────────────────────────────────────


@mcp.tool()
def search_content(query: str, limit: int = 20) -> dict:
    """Busca full-text (FTS5) no CONTEÚDO indexado dos livros.

    Suporta prefixo (ex.: 'filos' encontra 'filosofia'). Retorna trechos
    (snippets) com os termos entre marcadores de destaque, ordenados por
    relevância (bm25). Páginas 1-based."""
    db = _db()
    rows = db.fts_search(query, limit=limit)
    titles: dict[int, str] = {}
    results = []
    for r in rows:
        bid = r["book_id"]
        if bid not in titles:
            book = db.get_book(bid)
            titles[bid] = (book or {}).get("title") or f"Livro {bid}"
        results.append({
            "book_id": bid,
            "book_title": titles[bid],
            "page": r["page_number"] + 1,
            "snippet": r["snippet"],
            "rank": r["rank"],
        })
    data: dict[str, Any] = {"total": len(results), "results": results}
    pending = db.fts_pending_count()
    if pending:
        data["note"] = (f"{pending} livro(s) ainda sem conteúdo indexado no "
                        "FTS — resultados podem estar incompletos.")
    return _ok(data)


@mcp.tool()
def semantic_search(query: str, n_results: int = 5,
                    book_id: int | None = None) -> dict:
    """Busca SEMÂNTICA (embeddings bge-m3 via Ollama + ChromaDB) nos livros
    indexados. Requer o Ollama local em execução; book_id restringe a um
    livro. Páginas 1-based."""
    try:
        rows = _rag().search_similar(query, n_results=n_results, book_id=book_id)
    except RuntimeError as exc:
        # Ollama indisponível ou índice construído com outro modelo de
        # embeddings (needs_reindex) — mensagens já são amigáveis.
        return _err(str(exc))
    except Exception as exc:
        return _err(f"Falha na busca semântica: {exc}")
    results = []
    for r in rows:
        meta = dict(r.get("metadata") or {})
        page0 = meta.get("page_number")
        results.append({
            "text": r.get("document"),
            "distance": r.get("distance"),
            "book_id": meta.get("book_id"),
            "page": (page0 + 1) if isinstance(page0, int) else None,
            "chunk_type": meta.get("chunk_type"),
        })
    return _ok({"total": len(results), "results": results})


# ── Ferramentas: conteúdo literal ────────────────────────────────────────


def _page_text(reader, db: LibraryDB, book_id: int, page0: int) -> str:
    """Texto de uma página (0-based), na mesma cascata do DocumentIndexerService:
    ``get_page_text`` (PDF) → ``get_chapter_text`` (EPUB) → ``get_page()``
    texto/HTML. Se vazio, cai no cache de OCR persistido pelo app — o servidor
    NÃO roda OCR (M1 é somente-leitura e não grava cache)."""
    text = ""
    if hasattr(reader, "get_page_text"):
        text = reader.get_page_text(page0) or ""
    elif hasattr(reader, "get_chapter_text"):
        text = reader.get_chapter_text(page0) or ""
    else:
        page = reader.get_page(page0)
        content = getattr(page, "content", "") if page else ""
        if isinstance(content, str) and content:
            if getattr(page, "content_type", "text") == "html":
                from bs4 import BeautifulSoup
                text = BeautifulSoup(content, "html.parser").get_text(" ", strip=True)
            else:
                text = content
    if not text.strip():
        row = db.get_ocr_page(book_id, page0)
        if row and (row.get("content") or "").strip():
            text = row["content"]
    return text


@mcp.tool()
def get_page_text(book_id: int, first_page: int,
                  last_page: int | None = None) -> dict:
    """Texto literal de um intervalo de páginas de um livro.

    Páginas 1-based; last_page omitido = apenas first_page; máximo de
    10 páginas por chamada. PDFs escaneados dependem do cache de OCR já
    gerado pelo app (o servidor não executa OCR)."""
    if last_page is None:
        last_page = first_page
    if first_page < 1 or last_page < first_page:
        return _err("Intervalo inválido: exige-se 1 <= first_page <= last_page.")
    if last_page - first_page + 1 > PAGE_CAP:
        return _err(f"Máximo de {PAGE_CAP} páginas por chamada — "
                    "peça um intervalo menor.")
    db = _db()
    book = db.get_book(book_id)
    if book is None:
        return _err(f"Livro {book_id} não encontrado.")
    path = Path(book.get("file_path") or "")
    if not path.exists():
        return _err(f"Arquivo do livro não encontrado no disco: {path}")
    from src.readers.reader_factory import create_reader  # pesado — lazy
    try:
        reader = create_reader(path)
        reader.open()
    except Exception as exc:
        return _err(f"Falha ao abrir o livro: {exc}")
    try:
        total = reader.total_pages or 0
        if total and first_page > total:
            return _err(f"first_page ({first_page}) está além do total de "
                        f"páginas ({total}).")
        end = min(last_page, total) if total else last_page
        pages = [{"page": p, "text": _page_text(reader, db, book_id, p - 1)}
                 for p in range(first_page, end + 1)]
        return _ok({"book_id": book_id, "title": book.get("title"),
                    "total_pages": total, "pages": pages})
    except Exception as exc:
        return _err(f"Falha ao extrair texto: {exc}")
    finally:
        try:
            reader.close()
        except Exception:
            pass


# ── Ferramentas: anotações e estatísticas ────────────────────────────────


@mcp.tool()
def list_annotations(book_id: int, annotation_type: str | None = None) -> dict:
    """Anotações de um livro em ordem de página (1-based).

    annotation_type opcional: 'note', 'highlight', 'bookmark', 'ai_note' ou
    'ai_bookmark'."""
    db = _db()
    if db.get_book(book_id) is None:
        return _err(f"Livro {book_id} não encontrado.")
    rows = db.get_annotations(book_id, annotation_type)
    annotations = [{
        "id": a.get("id"),
        "page": (a.get("page_number") or 0) + 1,
        "type": a.get("annotation_type"),
        "title": a.get("title") or "",
        "content": a.get("content") or "",
        "highlight_color": a.get("highlight_color"),
        "created_at": a.get("created_at"),
    } for a in rows]
    return _ok({"total": len(annotations), "annotations": annotations})


def _annotations_markdown(db: LibraryDB, book_id: int) -> str:
    """Markdown das anotações via o exportador do app (que escreve em arquivo)."""
    from src.utils.export import export_annotations_markdown as export_md
    with tempfile.TemporaryDirectory() as tmp:
        out = export_md(db, book_id, Path(tmp) / "annotations.md")
        return out.read_text(encoding="utf-8")


@mcp.tool()
def export_annotations_markdown(book_id: int) -> dict:
    """Todas as anotações de um livro consolidadas em um único documento
    Markdown (mesmo formato do exportador do app)."""
    db = _db()
    if db.get_book(book_id) is None:
        return _err(f"Livro {book_id} não encontrado.")
    return _ok({"markdown": _annotations_markdown(db, book_id)})


@mcp.tool()
def library_stats() -> dict:
    """Estatísticas da biblioteca: contagens por estado de leitura, formatos,
    favoritos, tempo total de leitura, sequência de dias (streak), minutos por
    semana, livros concluídos no ano e cobertura do índice de conteúdo (FTS)."""
    db = _db()
    stats = db.get_statistics()
    stats["streak_days"] = db.get_reading_streak()
    stats["weekly_minutes"] = db.get_weekly_reading_minutes()
    stats["books_read_this_year"] = db.get_books_read_in_year()
    stats["fts"] = db.fts_stats()
    stats["fts_pending_books"] = db.fts_pending_count()
    return _ok(stats)


# ── Resources ────────────────────────────────────────────────────────────


@mcp.resource("biblioteca://stats")
def stats_resource() -> str:
    """Estatísticas da biblioteca (JSON)."""
    return json.dumps(library_stats()["data"], ensure_ascii=False, indent=2)


@mcp.resource("biblioteca://book/{book_id}/annotations")
def book_annotations_resource(book_id: int) -> str:
    """Anotações de um livro (Markdown)."""
    db = _db()
    if db.get_book(book_id) is None:
        return f"Livro {book_id} não encontrado."
    return _annotations_markdown(db, book_id)


def main() -> None:
    """Ponto de entrada: ``python -m src.mcp.server`` (transporte stdio)."""
    mcp.run()


if __name__ == "__main__":
    main()
