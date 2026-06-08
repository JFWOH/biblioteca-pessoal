import pytest
import json
import os
from unittest.mock import patch, MagicMock
from urllib.error import URLError
from src.core.anki_service import AnkiService

@pytest.fixture
def anki_service(tmp_path):
    service = AnkiService()
    service.fallback_file = str(tmp_path / "flashcards_fallback.jsonl")
    return service

@patch("src.core.anki_service.urllib.request.urlopen")
def test_is_available_success(mock_urlopen, anki_service):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"result": 6, "error": None}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_resp
    
    assert anki_service.is_available() == True

@patch("src.core.anki_service.urllib.request.urlopen")
def test_is_available_failure(mock_urlopen, anki_service):
    mock_urlopen.side_effect = URLError("Connection refused")
    assert anki_service.is_available() == False

@patch("src.core.anki_service.urllib.request.urlopen")
def test_add_basic_note_success(mock_urlopen, anki_service):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"result": 123456789, "error": None}).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_resp
    
    note_id = anki_service.add_basic_note("Default", "Front test", "Back test")
    assert note_id == 123456789
    assert not os.path.exists(anki_service.fallback_file)

@patch("src.core.anki_service.urllib.request.urlopen")
def test_add_basic_note_fallback(mock_urlopen, anki_service):
    # Simula AnkiConnect offline
    mock_urlopen.side_effect = URLError("Connection refused")
    
    note_id = anki_service.add_basic_note("Default", "Fallback front", "Fallback back")
    assert note_id is None
    
    # Verifica fallback
    assert os.path.exists(anki_service.fallback_file)
    with open(anki_service.fallback_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["front"] == "Fallback front"
        assert data["back"] == "Fallback back"
