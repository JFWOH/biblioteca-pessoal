import pytest
from src.core.audio.tts_backend import TTSBackend
from src.core.audio.audio_reader_service import AudioReaderService
from tests.test_audio_reader_service import FakeTTSBackend

def test_interface_has_abstract_methods():
    # Verifica se os metodos abstratos speak e stop estao na interface
    assert "speak" in TTSBackend.__abstractmethods__
    assert "stop" in TTSBackend.__abstractmethods__

def test_interface_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        TTSBackend()  # Nao pode instanciar classe abstrata pura

def test_fake_backend_implements_interface_properly():
    backend = FakeTTSBackend()
    assert isinstance(backend, TTSBackend)

def test_service_accepts_any_tts_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    assert service.backend is backend
