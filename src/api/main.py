"""Backend HTTP fino da Biblioteca Pessoal — rodada M0 (API mobile).

Expõe o core existente (LibraryDB, RAGEngine, config) por HTTP para o futuro
cliente Flutter, no mesmo espírito do servidor MCP (``src/mcp/server.py``):
envelope uniforme ``{"status": "success", "data": ...}`` /
``{"status": "error", "error": ...}``, singletons preguiçosos redirecionáveis
por ``configure()``/``close()`` (testes) e lazy import de módulos pesados
(RAGEngine só entra dentro do endpoint de busca semântica — lição B0).

Convenções:
- Números de página são 1-based na fronteira HTTP (armazenamento interno
  0-based) — mesma convenção do MCP.
- Auth por bearer token estático em TODAS as rotas, exceto ``/health`` e
  ``/opds/*`` (apps OPDS de terceiros não mandam ``Authorization``).
- DB COMPARTILHADO (não recriado por request): ``LibraryDB.conn`` usa
  ``threading.local()`` internamente (ver ``src/core/database.py``), então
  cada thread do threadpool do FastAPI abre sua PRÓPRIA conexão sqlite na
  primeira vez que toca o LibraryDB — ``check_same_thread=True`` (default do
  sqlite3, que o LibraryDB não sobrescreve) nunca é violado porque nenhuma
  conexão cruza threads. Um singleton compartilhado evita reabrir o arquivo
  e re-rodar ``CREATE TABLE IF NOT EXISTS`` a cada requisição — decisão
  tomada lendo o código real de ``LibraryDB.__init__``/``conn``.
- Busca semântica é serializada com ``threading.Lock()`` — o RAGEngine
  compartilha estado de cancelamento entre chamadas (mesmo gotcha do MCP).
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import uvicorn
from fastapi import Depends, FastAPI, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.core.database import LibraryDB
from src.core.opds_server import router as opds_router
from src.core.opds_server import set_db_provider as _set_opds_db_provider
from src.core.reading_stats import clamp_session_seconds
from src.utils.constants import APP_VERSION, DATA_DIR, DB_PATH

# Caminhos ativos — redirecionáveis via configure() (testes usam tmp_path).
_db_path: Path = DB_PATH
_chroma_path: Path = DATA_DIR / "chroma_db"
_config_path: Path | None = None

# Singletons preguiçosos, criados na 1ª rota que os usa.
_state: dict[str, Any] = {"db": None, "rag": None, "config": None}

# Override de token só para testes. None = configure() nunca tocou o token
# (resolução cai para env/config normalmente — ver _resolve_token). Qualquer
# string (incluindo "") = valor FIXO com precedência máxima: "" significa
# "configurado como ausente" (força 503, nunca cai para env/config); uma
# string não-vazia é o token efetivo, ignorando env/config.
_token_override: str | None = None

# Busca semântica é serializada (mesmo gotcha do RAGEngine no MCP: o
# cancelamento é estado global compartilhado entre chamadas).
_rag_lock = threading.Lock()


def configure(db_path: str | Path | None = None,
              chroma_path: str | Path | None = None,
              config_path: str | Path | None = None,
              token: str | None = None) -> None:
    """Redireciona os caminhos de dados e o token (testes) e descarta os singletons.

    IMPORTANTE sobre ``token``: o default ``None`` significa "não mexer" —
    chamar ``configure()`` sem token (ou explicitamente com ``token=None``)
    PRESERVA o override atual e nunca força reler do ambiente. Para testar o
    caminho "token não configurado" (503), passe ``token=""`` explicitamente
    — isso limpa qualquer valor fixo anterior e bloqueia o fallback para
    ``BIBLIOTECA_API_TOKEN``/``api.token`` nesta sessão de testes.
    """
    global _db_path, _chroma_path, _config_path, _token_override
    if db_path is not None:
        _db_path = Path(db_path)
    if chroma_path is not None:
        _chroma_path = Path(chroma_path)
    if config_path is not None:
        _config_path = Path(config_path)
    if token is not None:
        _token_override = token
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
    _state["config"] = None


def _db() -> LibraryDB:
    if _state["db"] is None:
        _state["db"] = LibraryDB(_db_path)
    return _state["db"]


def _rag():
    if _state["rag"] is None:
        from src.core.rag_engine import RAGEngine
        _state["rag"] = RAGEngine(db_path=str(_db_path), chroma_path=str(_chroma_path))
    return _state["rag"]


def _config():
    if _state["config"] is None:
        from src.core.config import ConfigManager
        _state["config"] = ConfigManager(_config_path)
    return _state["config"]


def _resolve_token() -> str | None:
    """Token efetivo: ``configure(token=...)`` > env ``BIBLIOTECA_API_TOKEN``
    > config ``api.token``. Override "" (configurado como ausente) nunca cai
    para env/config — resolve direto para ``None`` (não configurado)."""
    if _token_override is not None:
        return _token_override or None
    env_token = os.environ.get("BIBLIOTECA_API_TOKEN")
    if env_token:
        return env_token
    cfg_token = _config().get("api.token", "")
    return cfg_token or None


def _ok(data: Any) -> dict:
    return {"status": "success", "data": data}


def _err(message: str) -> dict:
    return {"status": "error", "error": message}


class APIError(Exception):
    """Erro esperado com status HTTP definido — vira envelope pelo handler
    único abaixo (ADR-005: degradação graciosa, sem try/except repetido em
    cada rota)."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Dependency de auth: bearer token estático em todas as rotas exceto
    /health e /opds/*."""
    token = _resolve_token()
    if token is None:
        raise APIError(503, "Token da API não configurado (defina "
                        "BIBLIOTECA_API_TOKEN ou api.token no config).")
    if authorization != f"Bearer {token}":
        raise APIError(401, "Token inválido ou ausente.")


class ProgressUpdate(BaseModel):
    page: int = Field(..., ge=1)
    total_pages: int = Field(..., gt=0)
    seconds: int = 0


class AnnotationCreate(BaseModel):
    page: int = Field(..., ge=1)
    content: str = ""
    annotation_type: Literal["note", "highlight"] = "note"
    title: str | None = None
    highlight_color: str | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # O provider do OPDS aponta para o MESMO LibraryDB da API (singleton
    # lazy _db) — um só arquivo sqlite, uma só fonte de verdade.
    _set_opds_db_provider(_db)
    yield
    close()


app = FastAPI(title="Biblioteca Pessoal API", lifespan=_lifespan)
app.include_router(opds_router)


@app.exception_handler(APIError)
async def _handle_api_error(request, exc: APIError):
    return JSONResponse(status_code=exc.status_code, content=_err(exc.message))


@app.exception_handler(sqlite3.OperationalError)
async def _handle_db_locked(request, exc: sqlite3.OperationalError):
    # WAL com 1 escritor (precedente: "database is locked" no
    # append_chat_turn do desktop) — o cliente mobile faz retry suave em 503.
    if "locked" in str(exc).lower():
        return JSONResponse(status_code=503, content=_err(
            "Banco de dados temporariamente bloqueado (escrita concorrente) "
            "— tente novamente em instantes."))
    return JSONResponse(status_code=500, content=_err(f"Erro interno: {exc}"))


# Campos expostos nas listagens — mesma whitelist do MCP (_SUMMARY_KEYS),
# acrescida de percentage/has_cover (interesse específico do mobile).
_SUMMARY_KEYS = ("id", "title", "author", "file_format", "read_status",
                 "rating", "is_favorite", "date_added", "date_modified")


def _summary(book: dict, progress_map: dict[int, float]) -> dict:
    out = {k: book.get(k) for k in _SUMMARY_KEYS}
    out["percentage"] = progress_map.get(book["id"], 0.0)
    out["has_cover"] = bool(book.get("cover_path"))
    return out


def _progress_payload(row: dict | None) -> dict:
    if row is None:
        return {"page": None, "percentage": 0.0}
    return {
        "page": (row.get("current_page") or 0) + 1,
        "total_pages": row.get("total_pages"),
        "percentage": row.get("percentage"),
        "last_read": row.get("last_read"),
        "time_spent_seconds": row.get("time_spent_seconds"),
    }


# ── Rotas: saúde (sem auth) ──────────────────────────────────────────────


@app.get("/health")
def health():
    return _ok({"app": "biblioteca-api", "version": APP_VERSION})


# ── Rotas: biblioteca ─────────────────────────────────────────────────────


@app.get("/library")
def get_library(status: str | None = None, file_format: str | None = None,
                author: str | None = None, min_rating: int | None = None,
                favorites_only: bool = False, sort_by: str = "date_added",
                sort_order: str = "desc", limit: int = 50, offset: int = 0,
                _auth: None = Depends(require_auth)):
    """Lista livros com filtros/ordenação — lógica adaptada de
    ``src/mcp/server.py:list_books`` (copiada, não importada — módulos
    distintos, sem acoplamento MCP<->API)."""
    db = _db()
    books = db.get_all_books(sort_by=sort_by, sort_order=sort_order)
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
    progress_map = db.get_progress_map()
    return _ok({"total": total, "returned": len(window),
                "books": [_summary(b, progress_map) for b in window]})


@app.get("/library/{book_id}")
def get_library_book(book_id: int, _auth: None = Depends(require_auth)):
    db = _db()
    book = db.get_book(book_id)
    if book is None:
        raise APIError(404, f"Livro {book_id} não encontrado.")
    detail = {k: v for k, v in book.items() if k not in ("file_path", "cover_path")}
    detail["progress"] = _progress_payload(db.get_reading_progress(book_id))
    detail["annotations_count"] = len(db.get_annotations(book_id))
    detail["tags"] = db.get_book_tags(book_id)
    detail["collections"] = db.get_book_collections(book_id)
    return _ok(detail)


@app.get("/library/{book_id}/cover")
def get_library_cover(book_id: int, _auth: None = Depends(require_auth)):
    db = _db()
    book = db.get_book(book_id)
    cover_path = (book or {}).get("cover_path") or ""
    if not book or not cover_path or not Path(cover_path).exists():
        raise APIError(404, "Capa não encontrada.")
    return FileResponse(cover_path)


@app.get("/read/{book_id}")
def read_book(book_id: int, _auth: None = Depends(require_auth)):
    db = _db()
    book = db.get_book(book_id)
    if book is None:
        raise APIError(404, f"Livro {book_id} não encontrado.")
    file_path = book.get("file_path") or ""
    if not file_path or not Path(file_path).exists():
        raise APIError(404, "Arquivo do livro não encontrado no disco.")
    # FileResponse (Starlette) suporta Range nativamente — download
    # progressivo/streaming para o leitor mobile sem esforço extra aqui.
    return FileResponse(file_path, filename=Path(file_path).name)


# ── Rotas: progresso de leitura ────────────────────────────────────────────


@app.get("/progress/{book_id}")
def get_progress(book_id: int, _auth: None = Depends(require_auth)):
    db = _db()
    if db.get_book(book_id) is None:
        raise APIError(404, f"Livro {book_id} não encontrado.")
    return _ok(_progress_payload(db.get_reading_progress(book_id)))


@app.post("/progress/{book_id}")
def post_progress(book_id: int, body: ProgressUpdate,
                  _auth: None = Depends(require_auth)):
    db = _db()
    if db.get_book(book_id) is None:
        raise APIError(404, f"Livro {book_id} não encontrado.")
    # Teto anti-idle de 300s/página (paridade com o desktop — mesmo cap
    # usado pelo cronômetro de leitura da GUI).
    clamped = clamp_session_seconds(body.seconds)
    db.update_reading_progress(book_id, body.page - 1, body.total_pages,
                               time_spent=clamped)
    return _ok(_progress_payload(db.get_reading_progress(book_id)))


# ── Rotas: anotações e marcadores ──────────────────────────────────────────


@app.get("/annotations/{book_id}")
def get_annotations(book_id: int, annotation_type: str | None = None,
                    _auth: None = Depends(require_auth)):
    db = _db()
    if db.get_book(book_id) is None:
        raise APIError(404, f"Livro {book_id} não encontrado.")
    annotations = [{
        "id": a.get("id"),
        "page": (a.get("page_number") or 0) + 1,
        "content": a.get("content") or "",
        "title": a.get("title") or "",
        "highlight_color": a.get("highlight_color"),
        "annotation_type": a.get("annotation_type"),
        "created_at": a.get("created_at"),
    } for a in db.get_annotations(book_id, annotation_type)]
    bookmarks = [{
        "id": b.get("id"),
        "page": (b.get("page_number") or 0) + 1,
        "label": b.get("label") or "",
        "created_at": b.get("created_at"),
    } for b in db.get_bookmarks(book_id)]
    return _ok({"annotations": annotations, "bookmarks": bookmarks})


@app.post("/annotations/{book_id}")
def post_annotation(book_id: int, body: AnnotationCreate,
                    _auth: None = Depends(require_auth)):
    db = _db()
    if db.get_book(book_id) is None:
        raise APIError(404, f"Livro {book_id} não encontrado.")
    content = (body.content or "").strip()
    if not content:
        raise APIError(400, "Conteúdo vazio — nada para anotar.")
    ann_id = db.add_annotation(
        book_id, body.page - 1, content=content,
        annotation_type=body.annotation_type,
        highlight_color=body.highlight_color or "#fbbf24",
        # Origem aditiva — espelha {"source": "mcp"} do servidor MCP, mas
        # marcando a anotação como criada pelo cliente mobile.
        position_data=json.dumps({"source": "mobile"}),
        title=(body.title or "").strip(),
    )
    return _ok({"annotation_id": ann_id, "book_id": book_id, "page": body.page,
                "annotation_type": body.annotation_type,
                "title": (body.title or "").strip()})


# ── Rotas: busca ────────────────────────────────────────────────────────────


@app.get("/search")
def search(q: str = "", mode: str = "fts", limit: int = 20,
          book_id: int | None = None, _auth: None = Depends(require_auth)):
    db = _db()
    if mode == "semantic":
        with _rag_lock:
            try:
                rows = _rag().search_similar(q, n_results=limit, book_id=book_id)
            except RuntimeError as exc:
                # Ollama indisponível ou índice desatualizado (needs_reindex)
                # — mensagens já são amigáveis no core.
                raise APIError(503, str(exc)) from exc
            except Exception as exc:
                raise APIError(503, f"Falha na busca semântica: {exc}") from exc
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

    rows = db.fts_search(q, limit=limit)
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
    return _ok({"total": len(results), "results": results})


# ── Rotas: estatísticas ──────────────────────────────────────────────────


@app.get("/stats")
def get_stats(_auth: None = Depends(require_auth)):
    db = _db()
    stats = db.get_statistics()
    stats["streak"] = db.get_reading_streak()
    stats["weekly_minutes"] = db.get_weekly_reading_minutes()
    return _ok(stats)


def main() -> None:
    """Ponto de entrada: ``python -m src.api.main``."""
    cfg = _config()
    host = cfg.get("api.host", "0.0.0.0")
    port = cfg.get("api.port", 8765)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
