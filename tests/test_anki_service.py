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
    
    assert anki_service.is_available() is True

@patch("src.core.anki_service.urllib.request.urlopen")
def test_is_available_failure(mock_urlopen, anki_service):
    mock_urlopen.side_effect = URLError("Connection refused")
    assert anki_service.is_available() is False

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


def _write_queue(service, rows):
    with open(service.fallback_file, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def test_count_pending_fallback(anki_service):
    assert anki_service.count_pending_fallback() == 0
    _write_queue(anki_service, [
        {"deckName": "Default", "front": "a", "back": "1"},
        {"deckName": "Default", "front": "b", "back": "2"},
    ])
    assert anki_service.count_pending_fallback() == 2


def test_flush_fallback_sends_and_clears(anki_service):
    _write_queue(anki_service, [
        {"deckName": "Default", "front": "a", "back": "1", "tags": ["t"]},
        {"deckName": "Default", "front": "b", "back": "2", "tags": ["t"]},
    ])
    with patch.object(anki_service, "is_available", return_value=True), \
         patch.object(anki_service, "_invoke", return_value=111):
        summary = anki_service.flush_fallback_to_anki()
    assert summary["sent"] == 2
    assert summary["kept"] == 0
    assert summary["total"] == 2
    assert anki_service.count_pending_fallback() == 0


def test_flush_fallback_raises_when_unavailable(anki_service):
    _write_queue(anki_service, [{"deckName": "Default", "front": "a", "back": "1"}])
    with patch.object(anki_service, "is_available", return_value=False):
        with pytest.raises(ConnectionError):
            anki_service.flush_fallback_to_anki()
    # Fila intocada
    assert anki_service.count_pending_fallback() == 1


def test_flush_fallback_drops_duplicates_keeps_unknown_errors(anki_service):
    _write_queue(anki_service, [
        {"deckName": "Default", "front": "dup", "back": "1"},
        {"deckName": "Default", "front": "ok", "back": "2"},
        {"deckName": "Default", "front": "boom", "back": "3"},
    ])

    def fake_invoke(action, **params):
        front = params["note"]["fields"]["Front"]
        if front == "dup":
            raise Exception("cannot create note because it is a duplicate")
        if front == "boom":
            raise Exception("erro desconhecido do anki")
        return 222

    with patch.object(anki_service, "is_available", return_value=True), \
         patch.object(anki_service, "_invoke", side_effect=fake_invoke):
        summary = anki_service.flush_fallback_to_anki()

    assert summary["sent"] == 1
    assert summary["duplicates"] == 1
    assert summary["kept"] == 1  # o 'boom' permanece na fila
    # Apenas a nota com erro desconhecido permanece
    assert anki_service.count_pending_fallback() == 1
