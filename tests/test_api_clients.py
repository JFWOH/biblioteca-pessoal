import pytest
from unittest.mock import patch, MagicMock
from src.core.api_clients import MetadataFetcher

@pytest.fixture
def fetcher():
    return MetadataFetcher()

@patch("src.core.api_clients.httpx.Client.get")
def test_search_book_success(mock_get, fetcher):
    # Configura o mock do response
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "volumeInfo": {
                    "title": "O Senhor dos Anéis",
                    "authors": ["J.R.R. Tolkien"],
                    "publisher": "Martins Fontes",
                    "publishedDate": "2001",
                    "pageCount": 1200,
                    "categories": ["Fantasia"],
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9788533613379"}
                    ],
                    "imageLinks": {
                        "thumbnail": "http://example.com/cover.jpg"
                    }
                }
            }
        ]
    }
    mock_get.return_value = mock_response

    metadata = fetcher.search_book("Senhor dos Anéis", "Tolkien")
    
    assert metadata is not None
    assert metadata["title"] == "O Senhor dos Anéis"
    assert metadata["author"] == "J.R.R. Tolkien"
    assert metadata["publisher"] == "Martins Fontes"
    assert metadata["published_year"] == "2001"
    assert metadata["isbn"] == "9788533613379"
    assert metadata["cover_url"] == "https://example.com/cover.jpg"

@patch("src.core.api_clients.httpx.Client.get")
def test_search_book_no_results(mock_get, fetcher):
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response
    
    metadata = fetcher.search_book("Livro Inexistente 123456")
    assert metadata is None

@patch("src.core.api_clients.httpx.Client.get")
def test_download_cover(mock_get, fetcher):
    mock_response = MagicMock()
    mock_response.content = b"fake_image_bytes"
    mock_get.return_value = mock_response
    
    cover_bytes = fetcher.download_cover("https://example.com/cover.jpg")
    
    assert cover_bytes == b"fake_image_bytes"
