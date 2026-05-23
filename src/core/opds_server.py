from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, FileResponse
from src.core.database import LibraryDB
import urllib.parse
import os

app = FastAPI(title="Biblioteca Pessoal - OPDS Server")
db = LibraryDB()

OPDS_NAMESPACE = 'xmlns="http://www.w3.org/2005/Atom" xmlns:opds="http://opds-spec.org/2010/catalog"'

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

@app.get("/opds")
async def get_opds_catalog(request: Request):
    """Endpoint raiz do catálogo OPDS."""
    base_url = str(request.base_url).rstrip("/")
    books = db.get_all_books(sort_by="title", sort_order="ASC", limit=None)
    
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

@app.get("/opds/search")
async def search_opds(q: str, request: Request):
    """Pesquisa de livros OPDS (usa a função de busca do LibraryDB indiretamente, ou FTS)."""
    base_url = str(request.base_url).rstrip("/")
    # Busca rudimentar via list comprehension (poderíamos conectar diretamente no FTS)
    all_books = db.get_all_books(sort_by="title", sort_order="ASC", limit=None)
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

@app.get("/opds/download/{book_id}")
async def download_book(book_id: int):
    """Endpoint para baixar o arquivo do livro."""
    book = db.get_book(book_id)
    if not book or not book.get("file_path"):
        raise HTTPException(status_code=404, detail="Livro não encontrado")
        
    file_path = book["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no disco")
        
    filename = os.path.basename(file_path)
    return FileResponse(file_path, filename=filename)
