import pytest
from fastapi.testclient import TestClient
from src.core.opds_server import app, db
import os
import tempfile

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    books = db.get_all_books()
    for b in books:
        db.delete_book(b["id"])

    db.add_book(
        title="Livro de Teste OPDS",
        author="Autor OPDS",
        description="Um livro para testar o OPDS",
        file_path="/tmp/fake.epub",
        file_format="epub",
        file_size=1024,
        date_added="2026-05-18T00:00:00",
    )

    yield

    books = db.get_all_books()
    for b in books:
        db.delete_book(b["id"])

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

def test_download_book_file_not_found():
    books = db.get_all_books()
    book_id = books[0]["id"]
    response = client.get(f"/opds/download/{book_id}")
    assert response.status_code == 404

def test_download_book_success():
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as tmp:
        tmp.write(b"fake_epub_content")
        tmp_path = tmp.name

    book_id = db.add_book(
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

