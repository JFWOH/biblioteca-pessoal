import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from src.core import opds_server
from src.core.database import LibraryDB
from src.core.opds_server import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Redireciona o DB do router OPDS para um LibraryDB isolado em tmp_path.

    Rodada M0 (API mobile): opds_server não tem mais ``db`` global (item 4 da
    auditoria) — a fonte agora é substituível via ``set_db_provider``.
    """
    temp_db_path = tmp_path / "test_opds.db"
    db = LibraryDB(temp_db_path)
    opds_server.set_db_provider(lambda: db)

    db.add_book(
        title="Livro de Teste OPDS",
        author="Autor OPDS",
        description="Um livro para testar o OPDS",
        file_path="/tmp/fake.epub",
        file_format="epub",
        file_size=1024,
        date_added="2026-05-18T00:00:00",
    )

    yield db

    db.close()
    opds_server._db_provider = opds_server._default_db_provider


def test_get_opds_catalog():
    response = client.get("/opds")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/atom+xml"

    xml = response.text
    assert "Livro de Teste OPDS" in xml
    assert "Autor OPDS" in xml
    assert "application/epub+zip" in xml


def test_search_opds():
    response = client.get("/opds/search?q=Teste")
    assert response.status_code == 200
    assert "Livro de Teste OPDS" in response.text

    response_empty = client.get("/opds/search?q=Inexistente")
    assert response_empty.status_code == 200
    assert "Livro de Teste OPDS" not in response_empty.text


def test_download_book_not_found():
    response = client.get("/opds/download/9999")
    assert response.status_code == 404


def test_download_book_file_not_found(setup_db):
    books = setup_db.get_all_books()
    book_id = books[0]["id"]
    response = client.get(f"/opds/download/{book_id}")
    assert response.status_code == 404


def test_download_book_success(setup_db):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp.write(b"fake_epub_content")
        tmp_path = tmp.name

    book_id = setup_db.add_book(
        title="Livro Real OPDS",
        file_path=tmp_path,
        file_format="epub",
        file_size=1024,
        date_added="2026-05-18T00:00:00",
    )

    response = client.get(f"/opds/download/{book_id}")
    assert response.status_code == 200
    assert response.content == b"fake_epub_content"

    os.remove(tmp_path)
