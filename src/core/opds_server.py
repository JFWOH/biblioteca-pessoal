"""Servidor OPDS (Open Publication Distribution System) — catálogo compatível
com leitores de terceiros (ex.: KOReader, Moon+ Reader, Aldiko). Sem
autenticação: convenção OPDS, apps de terceiros não mandam bearer token.

Rodada M0 (backend API mobile): antes deste módulo criava um
``LibraryDB()`` global no import (item 4 da auditoria) — impedia apontar
para um DB isolado em teste/API. Agora as rotas viram um ``APIRouter`` e o
DB é resolvido por um provider substituível (``set_db_provider``): o
default é um singleton lazy (mantém o standalone/``OPDSWorker`` idêntico ao
comportamento anterior); ``src/api/main.py`` aponta o provider para o DB
configurado da API.
"""

import os
import urllib.parse
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response

from src.core.database import LibraryDB
from src.utils.constants import DB_PATH

OPDS_NAMESPACE = 'xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"'

router = APIRouter()

# Singleton lazy do provider default — só existe se ninguém chamar
# set_db_provider (uso standalone via OPDSWorker/execução direta do módulo).
_default_db: LibraryDB | None = None


def _default_db_provider() -> LibraryDB:
    global _default_db
    if _default_db is None:
        _default_db = LibraryDB(DB_PATH)
    return _default_db


_db_provider: Callable[[], LibraryDB] = _default_db_provider


def set_db_provider(provider: Callable[[], LibraryDB]) -> None:
    """Substitui a fonte do LibraryDB usada pelas rotas /opds.

    ``src/api/main.py`` aponta para o LibraryDB compartilhado da API;
    testes apontam para um DB isolado em tmp_path.
    """
    global _db_provider
    _db_provider = provider


def _db() -> LibraryDB:
    return _db_provider()


def _generate_entry(book: dict, base_url: str) -> str:
    """Gera um bloco <entry> XML para um livro no formato OPDS."""
    book_id = book["id"]
    title = book.get("title", "Sem título")
    author = book.get("author", "Autor Desconhecido")
    description = book.get("description", "")
    updated = book.get("added_date", "2023-01-01T00:00:00Z")

    # Determina o mimetype do arquivo para o OPDS
    file_path = book.get("file_path", "")
    ext = os.path.splitext(file_path)[1].lower()
    mimetype = "application/octet-stream"
    if ext == ".epub":
        mimetype = "application/epub+zip"
    elif ext == ".pdf":
        mimetype = "application/pdf"

    download_url = f"{base_url}/opds/download/{book_id}"

    return f"""
    <entry>
        <title>{title}</title>
        <author><name>{author}</name></author>
        <id>urn:uuid:book-{book_id}</id>
        <updated>{updated}</updated>
        <summary>{description}</summary>
        <link rel="http://opds-spec.org/acquisition" href="{download_url}" type="{mimetype}"/>
    </entry>
    """


@router.get("/opds")
async def get_opds_catalog(request: Request):
    """Endpoint raiz do catálogo OPDS."""
    base_url = str(request.base_url).rstrip("/")
    books = _db().get_all_books(sort_by="title", sort_order="ASC", limit=None)

    entries = "".join([_generate_entry(b, base_url) for b in books])

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed {OPDS_NAMESPACE}>
        <id>urn:uuid:biblioteca-pessoal-root</id>
        <title>Minha Biblioteca Pessoal</title>
        <updated>2023-01-01T00:00:00Z</updated>
        <link rel="self" href="{base_url}/opds" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
        <link rel="start" href="{base_url}/opds" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
        <link rel="search" href="{base_url}/opds/search?q={{searchTerms}}" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
        {entries}
    </feed>
    """
    return Response(content=xml, media_type="application/atom+xml")


@router.get("/opds/search")
async def search_opds(q: str, request: Request):
    """Pesquisa de livros OPDS (usa a função de busca do LibraryDB indiretamente, ou FTS)."""
    base_url = str(request.base_url).rstrip("/")
    # Busca rudimentar via list comprehension (poderíamos conectar diretamente no FTS)
    all_books = _db().get_all_books(sort_by="title", sort_order="ASC", limit=None)
    q_lower = q.lower()
    books = [b for b in all_books if q_lower in b.get("title", "").lower() or q_lower in b.get("author", "").lower()]

    entries = "".join([_generate_entry(b, base_url) for b in books])

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed {OPDS_NAMESPACE}>
        <id>urn:uuid:biblioteca-pessoal-search</id>
        <title>Resultados da Busca</title>
        <updated>2023-01-01T00:00:00Z</updated>
        <link rel="self" href="{base_url}/opds/search?q={urllib.parse.quote(q)}" type="application/atom+xml;profile=opds-catalog;kind=acquisition"/>
        {entries}
    </feed>
    """
    return Response(content=xml, media_type="application/atom+xml")


@router.get("/opds/download/{book_id}")
async def download_book(book_id: int):
    """Endpoint para baixar o arquivo do livro."""
    book = _db().get_book(book_id)
    if not book or not book.get("file_path"):
        raise HTTPException(status_code=404, detail="Livro não encontrado")

    file_path = book["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no disco")

    filename = os.path.basename(file_path)
    return FileResponse(file_path, filename=filename)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    yield
    # Fecha o LibraryDB default no shutdown (libera o arquivo no Windows) —
    # só existe se o app rodou standalone (ninguém chamou set_db_provider).
    global _default_db
    if _default_db is not None:
        _default_db.close()
        _default_db = None


# Mantido por retrocompat: OPDSWorker importa ``app`` diretamente
# (src/gui/workers/opds_worker.py) e sobe via uvicorn.Config/Server.
app = FastAPI(title="Biblioteca Pessoal - OPDS Server", lifespan=_lifespan)
app.include_router(router)
